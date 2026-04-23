import axios from "axios";
import { API_BASE_URL } from "@/shared/Config";

export interface FeatureFlags {
  assistant_enabled: boolean;
  assistant: {
    enabled: boolean;
    display_name: string;
    model: string | null;
  };
  dataset_count: number;
  project_name: string;
  version: string;
}

export interface ColumnSummary {
  name: string;
  dtype: string;
  non_null_ratio: number;
  is_numeric: boolean;
  is_boolean: boolean;
  numeric?: { min: number; max: number; mean: number; median: number; count: number };
  n_unique?: number;
  top?: Array<{ value: string; count: number }>;
}

export interface SpeciesOverview {
  code: string;
  full_name: string;
  display_name?: string;
  table_name?: string;
  tags: string[];
  n_samples: number;
  n_genes: number;
  layers: string[];
  var_columns: string[];
  obs_columns: string[];
  var_summary: ColumnSummary[];
  obs_summary: ColumnSummary[];
  derived: {
    tissue_distribution?: Array<{ value: string; count: number }>;
    tf_count?: number;
    tf_families?: Array<{ value: string; count: number }>;
    orthogroup_count?: number;
    genes_with_orthogroup?: number;
    qc_metrics?: Record<string, { min: number; max: number; mean: number; median: number; count: number }>;
  };
  annotation_coverage: { var: Record<string, number>; obs: Record<string, number> };
}

export interface OverviewPayload {
  project: { name: string; version: string; description: string };
  global: {
    n_species: number;
    n_samples: number;
    n_genes: number;
    orthogroup_count: number;
    has_orthogroups: boolean;
    gene_tree_count: number;
    tf_total: number;
    tissue_union: Array<{ tissue: string; counts: Record<string, number>; total: number }>;
  };
  species: SpeciesOverview[];
  mtime?: number;
}

export async function fetchFeatures(): Promise<FeatureFlags> {
  const { data } = await axios.get<FeatureFlags>(`${API_BASE_URL}/api/features`);
  return data;
}

export async function fetchOverview(): Promise<OverviewPayload> {
  const { data } = await axios.get<OverviewPayload>(`${API_BASE_URL}/api/overview`);
  return data;
}

export async function fetchOverviewMtime(): Promise<{ mtime: number }> {
  const { data } = await axios.get<{ mtime: number }>(`${API_BASE_URL}/api/overview/mtime`);
  return data;
}
