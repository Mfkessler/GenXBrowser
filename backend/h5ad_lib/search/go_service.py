"""
Gene Ontology service for GO term search and hierarchy.

Provides GO term lookup, search, and hierarchy navigation using
the pronto library to parse OBO files.
"""

import logging
import re
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

try:
    import pronto
    HAS_PRONTO = True
except ImportError:
    HAS_PRONTO = False
    logging.warning("pronto library not installed - GO functionality will be limited")

logger = logging.getLogger(__name__)


# Official GO OBO URL
GO_OBO_URL = "http://purl.obolibrary.org/obo/go.obo"


class GOService:
    """
    Service for Gene Ontology data access and search.
    
    Provides:
    - GO term lookup by ID
    - Fuzzy search by name
    - Hierarchy navigation (parents/children)
    
    Example:
        # Initialize with auto-download
        go = GOService(auto_download=True)
        
        # Or use local file
        go = GOService(obo_path="/data/go.obo")
        
        # Search for terms
        results = go.search_terms("flower development", limit=10)
        
        # Get specific term
        term = go.get_term("GO:0009908")
        
        # Get parent terms
        parents = go.get_parents("GO:0009908")
    """
    
    def __init__(
        self,
        obo_path: Optional[str] = None,
        auto_download: bool = True,
    ):
        """
        Initialize GO service.
        
        Args:
            obo_path: Path to local OBO file. If None and auto_download=True,
                     downloads from the official GO source.
            auto_download: If True, downloads GO OBO if no local file.
        """
        self.ontology: Optional[Any] = None
        self.go_index: Dict[str, Dict[str, Any]] = {}
        self.name_index: Dict[str, List[str]] = defaultdict(list)
        self.definition_index: Dict[str, List[str]] = defaultdict(list)
        self.loaded = False
        
        if not HAS_PRONTO:
            logger.error("pronto not available - GO service will not function")
            return
        
        self._load_ontology(obo_path, auto_download)
    
    def _load_ontology(self, obo_path: Optional[str], auto_download: bool) -> None:
        """Load ontology from file or URL."""
        try:
            if obo_path and Path(obo_path).exists():
                logger.info(f"Loading GO ontology from {obo_path}")
                self.ontology = pronto.Ontology(obo_path)
            elif auto_download:
                logger.info("Downloading GO ontology from official source...")
                self.ontology = pronto.Ontology(GO_OBO_URL)
            else:
                logger.warning("No GO ontology source provided")
                return
            
            self._build_indexes()
            self.loaded = True
            logger.info(f"GO service initialized with {len(self.go_index)} terms")
            
        except Exception as e:
            logger.error(f"Failed to initialize GO service: {e}")
            self.loaded = False
    
    def _build_indexes(self) -> None:
        """Build search indexes from ontology."""
        if not self.ontology:
            return
        
        for term in self.ontology.terms():
            # Skip obsolete terms
            if term.obsolete:
                continue
            
            go_id = term.id
            name = term.name
            namespace = getattr(term, "namespace", None)
            definition = term.definition if hasattr(term, "definition") else ""
            
            # Store in main index
            self.go_index[go_id] = {
                "id": go_id,
                "name": name,
                "namespace": namespace,
                "definition": str(definition) if definition else "",
                "is_obsolete": term.obsolete,
            }
            
            # Build case-insensitive word indexes for name and definition search.
            if name:
                words = re.findall(r"\w+", name.lower())
                for word in words:
                    if len(word) >= 3:  # Only index words with 3+ chars
                        self.name_index[word].append(go_id)
            if definition:
                words = re.findall(r"\w+", str(definition).lower())
                for word in words:
                    if len(word) >= 3:
                        self.definition_index[word].append(go_id)
    
    def search_terms(
        self,
        query: str,
        limit: int = 20,
        candidate_ids: Optional[Set[str]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Search GO terms by name.
        
        Args:
            query: Search query (case-insensitive)
            limit: Maximum number of results
            candidate_ids: Optional GO IDs to restrict results to
            
        Returns:
            List of matching GO terms with id, name, namespace, definition
        """
        if not self.loaded or not query:
            return []
        
        query_lower = query.lower().strip()
        if len(query_lower) < 2:
            return []

        candidates = set(self.go_index)
        if candidate_ids is not None:
            candidates.intersection_update(candidate_ids)
        
        matching_ids: Set[str] = set()
        
        # 1. Exact GO ID match (e.g., "GO:0009908")
        if query_lower.startswith("go:"):
            go_id_upper = query.upper().strip()
            if go_id_upper in candidates:
                return [self._format_term(go_id_upper)]
        
        # 2. Word-based search
        query_words = re.findall(r"\w+", query_lower)
        if query_words:
            word_sets = [
                set(self.name_index.get(word, [])) | set(self.definition_index.get(word, []))
                for word in query_words
                if len(word) >= 3
            ]
            
            if word_sets:
                # Intersection: terms that match all words
                matching_ids = (
                    set.intersection(*word_sets)
                    if len(word_sets) > 1
                    else word_sets[0]
                )
                matching_ids.intersection_update(candidates)
        
        # 3. Substring match fallback
        if not matching_ids:
            for go_id in candidates:
                data = self.go_index[go_id]
                if (
                    query_lower in data["name"].lower()
                    or query_lower in data["definition"].lower()
                ):
                    matching_ids.add(go_id)
        
        # Format and rank results
        results = [self._format_term(go_id) for go_id in matching_ids]
        results = self._rank_results(results, query_lower)
        
        return results[:limit]
    
    def _rank_results(
        self, results: List[Dict[str, Any]], query: str
    ) -> List[Dict[str, Any]]:
        """
        Rank search results by relevance.
        
        Prioritizes: exact match > starts with > contains
        """
        def rank_key(term: Dict[str, Any]) -> tuple:
            name_lower = term["name"].lower()
            definition_lower = term["definition"].lower()
            
            if name_lower == query:
                return (0, name_lower)
            if name_lower.startswith(query):
                return (1, name_lower)
            if query in name_lower:
                return (2, name_lower)
            if query in definition_lower:
                return (3, name_lower)
            return (4, name_lower)
        
        return sorted(results, key=rank_key)
    
    def _format_term(self, go_id: str) -> Dict[str, Any]:
        """Format GO term for API response."""
        if go_id not in self.go_index:
            return {}
        
        data = self.go_index[go_id]
        return {
            "id": data["id"],
            "name": data["name"],
            "namespace": data["namespace"],
            "definition": data["definition"],
            "label": f"{data['id']} ({data['name']})",
        }
    
    def get_term(self, go_id: str) -> Optional[Dict[str, Any]]:
        """
        Get details for a specific GO term.
        
        Args:
            go_id: GO identifier (e.g., "GO:0009908")
            
        Returns:
            GO term details or None
        """
        if not self.loaded:
            return None
        
        go_id = go_id.upper().strip()
        if go_id not in self.go_index:
            return None
        
        return self._format_term(go_id)
    
    def get_parents(self, go_id: str) -> List[Dict[str, Any]]:
        """
        Get parent terms (is_a relationships).
        
        Args:
            go_id: GO identifier
            
        Returns:
            List of parent GO terms
        """
        if not self.loaded or not self.ontology:
            return []
        
        try:
            term = self.ontology[go_id.upper().strip()]
            parents = []
            for parent in term.superclasses(distance=1, with_self=False):
                if not parent.obsolete:
                    parents.append(self._format_term(parent.id))
            return parents
        except Exception as e:
            logger.error(f"Error getting parents for {go_id}: {e}")
            return []
    
    def get_children(self, go_id: str) -> List[Dict[str, Any]]:
        """
        Get child terms (inverse is_a relationships).
        
        Args:
            go_id: GO identifier
            
        Returns:
            List of child GO terms
        """
        if not self.loaded or not self.ontology:
            return []
        
        try:
            term = self.ontology[go_id.upper().strip()]
            children = []
            for child in term.subclasses(distance=1, with_self=False):
                if not child.obsolete:
                    children.append(self._format_term(child.id))
            return children
        except Exception as e:
            logger.error(f"Error getting children for {go_id}: {e}")
            return []
    
    def get_ancestors(
        self, go_id: str, max_distance: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Get all ancestor terms up to a given distance.
        
        Args:
            go_id: GO identifier
            max_distance: Maximum distance (None = all ancestors)
            
        Returns:
            List of ancestor GO terms
        """
        if not self.loaded or not self.ontology:
            return []
        
        try:
            term = self.ontology[go_id.upper().strip()]
            ancestors = []
            for ancestor in term.superclasses(distance=max_distance, with_self=False):
                if not ancestor.obsolete:
                    ancestors.append(self._format_term(ancestor.id))
            return ancestors
        except Exception as e:
            logger.error(f"Error getting ancestors for {go_id}: {e}")
            return []
    
    def get_descendants(
        self, go_id: str, max_distance: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Get all descendant terms up to a given distance.
        
        Args:
            go_id: GO identifier
            max_distance: Maximum distance (None = all descendants)
            
        Returns:
            List of descendant GO terms
        """
        if not self.loaded or not self.ontology:
            return []
        
        try:
            term = self.ontology[go_id.upper().strip()]
            descendants = []
            for descendant in term.subclasses(distance=max_distance, with_self=False):
                if not descendant.obsolete:
                    descendants.append(self._format_term(descendant.id))
            return descendants
        except Exception as e:
            logger.error(f"Error getting descendants for {go_id}: {e}")
            return []
    
    def get_namespace(self, go_id: str) -> Optional[str]:
        """
        Get the namespace of a GO term.
        
        Args:
            go_id: GO identifier
            
        Returns:
            Namespace string or None
        """
        term = self.get_term(go_id)
        return term.get("namespace") if term else None
    
    def is_available(self) -> bool:
        """Check if GO service is available."""
        return self.loaded and HAS_PRONTO
    
    def get_term_count(self) -> int:
        """Get total number of indexed GO terms."""
        return len(self.go_index)
    
    def reload(
        self, obo_path: Optional[str] = None, auto_download: bool = True
    ) -> bool:
        """
        Reload the GO ontology.
        
        Args:
            obo_path: Path to OBO file
            auto_download: If True, download if no local file
            
        Returns:
            True if successful
        """
        self.go_index.clear()
        self.name_index.clear()
        self.loaded = False
        self.ontology = None
        
        self._load_ontology(obo_path, auto_download)
        return self.loaded
