import { type CatalogMeta } from "./CatalogMeta";

export interface OverlayConfig {
  title: (entry: CatalogMeta) => string;
  endpoint: string;
  filters: (entry: CatalogMeta) => Record<string, string | string[]>;
}
