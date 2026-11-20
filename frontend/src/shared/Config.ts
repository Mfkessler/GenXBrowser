interface CorporateIdentity {
  logo: string;
  company_name: string;
  about: string;
  llm_name: string;
  cc_by: string;
}

interface Access {
  data: boolean;
  download: boolean;
}

interface Visualization {
  id_column: string;
  hide_columns: string[];
}

export interface Config {
  corporate_identity: CorporateIdentity;
  access: Access;
  visualization: Visualization;
}

export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "";
