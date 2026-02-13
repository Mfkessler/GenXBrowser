"""
Filter configuration storage.

Persists filter configurations as JSON files with hash-based deduplication.
This is the recommended storage backend for filter sharing URLs.
"""

import hashlib
import json
import logging
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class FilterStore:
    """
    Persists filter configurations as JSON files.
    
    Uses SHA256 hashing for:
    - Content-based deduplication (same config = same ID)
    - Idempotent writes (safe for concurrent access)
    - Short, shareable URLs
    
    Example:
        store = FilterStore("/data/filters")
        
        # Store a configuration
        hash_id = store.store({
            "species": "AC",
            "columns": ["gene_id", "description"],
            "filters": {"og": ("eq", "OG0001")}
        })
        
        # Retrieve later
        config = store.get(hash_id)
        
        # Create shareable URL
        url = f"https://app.example.com/share/{hash_id}"
    """
    
    def __init__(
        self,
        path: str,
        hash_length: int = 16,
        create_dir: bool = True,
    ):
        """
        Initialize filter store.
        
        Args:
            path: Directory path for storing filter files
            hash_length: Length of hash ID (default: 16 chars)
            create_dir: If True, create directory if it doesn't exist
        """
        self._path = Path(path)
        self._hash_length = hash_length
        
        if create_dir:
            self._path.mkdir(parents=True, exist_ok=True)
    
    def store(self, data: Dict[str, Any]) -> str:
        """
        Store filter configuration and return hash ID.
        
        The same data will always produce the same ID (idempotent).
        
        Args:
            data: Filter configuration dict
            
        Returns:
            Hash ID for retrieval
        """
        # Serialize with sorted keys for consistent hashing
        content = json.dumps(data, sort_keys=True, separators=(",", ":"))
        
        # Generate hash
        hash_id = hashlib.sha256(content.encode()).hexdigest()[:self._hash_length]
        
        # Write atomically using temp file + rename
        file_path = self._path / f"{hash_id}.json"
        temp_path = file_path.with_suffix(".tmp")
        
        try:
            temp_path.write_text(content)
            temp_path.rename(file_path)
            logger.debug(f"Stored filter config: {hash_id}")
        except Exception as e:
            # Clean up temp file on failure
            temp_path.unlink(missing_ok=True)
            logger.error(f"Failed to store filter config: {e}")
            raise
        
        return hash_id
    
    def get(self, hash_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve filter configuration by hash ID.
        
        Args:
            hash_id: Hash ID from store()
            
        Returns:
            Filter configuration or None if not found
        """
        # Sanitize hash_id to prevent path traversal
        safe_id = "".join(c for c in hash_id if c.isalnum())[:self._hash_length]
        
        file_path = self._path / f"{safe_id}.json"
        
        if not file_path.exists():
            return None
        
        try:
            content = file_path.read_text()
            return json.loads(content)
        except Exception as e:
            logger.error(f"Failed to read filter config {hash_id}: {e}")
            return None
    
    def exists(self, hash_id: str) -> bool:
        """
        Check if a filter configuration exists.
        
        Args:
            hash_id: Hash ID to check
            
        Returns:
            True if exists
        """
        safe_id = "".join(c for c in hash_id if c.isalnum())[:self._hash_length]
        file_path = self._path / f"{safe_id}.json"
        return file_path.exists()
    
    def delete(self, hash_id: str) -> bool:
        """
        Delete a filter configuration.
        
        Args:
            hash_id: Hash ID to delete
            
        Returns:
            True if deleted, False if not found
        """
        safe_id = "".join(c for c in hash_id if c.isalnum())[:self._hash_length]
        file_path = self._path / f"{safe_id}.json"
        
        if file_path.exists():
            try:
                file_path.unlink()
                logger.debug(f"Deleted filter config: {hash_id}")
                return True
            except Exception as e:
                logger.error(f"Failed to delete filter config {hash_id}: {e}")
                return False
        
        return False
    
    def list_all(self) -> List[str]:
        """
        List all stored filter IDs.
        
        Returns:
            List of hash IDs
        """
        return [f.stem for f in self._path.glob("*.json")]
    
    def cleanup(self, max_age_days: int = 30) -> int:
        """
        Remove filter configs older than max_age_days.
        
        Args:
            max_age_days: Maximum age in days
            
        Returns:
            Number of configs deleted
        """
        cutoff = time.time() - (max_age_days * 86400)
        deleted = 0
        
        for file_path in self._path.glob("*.json"):
            try:
                if file_path.stat().st_mtime < cutoff:
                    file_path.unlink()
                    deleted += 1
                    logger.debug(f"Cleaned up old filter config: {file_path.stem}")
            except Exception as e:
                logger.error(f"Failed to clean up {file_path}: {e}")
        
        if deleted:
            logger.info(f"Cleaned up {deleted} old filter configs")
        
        return deleted
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get storage statistics.
        
        Returns:
            Dict with count, size_bytes, oldest, newest
        """
        files = list(self._path.glob("*.json"))
        
        if not files:
            return {
                "count": 0,
                "size_bytes": 0,
                "oldest": None,
                "newest": None,
            }
        
        stats = [f.stat() for f in files]
        
        return {
            "count": len(files),
            "size_bytes": sum(s.st_size for s in stats),
            "oldest": min(s.st_mtime for s in stats),
            "newest": max(s.st_mtime for s in stats),
        }
    
    @property
    def path(self) -> Path:
        """Storage directory path."""
        return self._path
