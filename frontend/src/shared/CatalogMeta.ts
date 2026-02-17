export interface CatalogMeta {
  count: number;
  description: string;
  table_name: string;
  tags: string[];
  photo?: string;  // Optional photo filename
  _tissue_count?: number;
}
