export interface CatalogMeta {
  count: number;
  description: string;
  table_name: string;
  tags: string[];
  photo?: string;  // Optional photo filename
  has_orthogroups?: boolean;
  _default_trait_count?: number;
  _species_code?: string;  // Short species code (e.g., "AT", "SL", "OS")
}
