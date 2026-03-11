/**
 * NCBI BLAST integration utility
 * Provides functions to open BLAST searches for protein and RNA sequences
 */

export type BlastType = 'protein' | 'rna';

export type ProteinDatabase = 'nr' | 'refseq_protein';
export type RnaDatabase = 'nt' | 'refseq_rna';
export type BlastDatabase = ProteinDatabase | RnaDatabase;

export interface DatabaseOption {
  value: BlastDatabase;
  label: string;
  description: string;
}

/**
 * Available protein databases
 */
export const proteinDatabases: DatabaseOption[] = [
  {
    value: 'nr',
    label: 'nr (Non-redundant)',
    description: 'Includes every known sequence (GenBank, Swiss-Prot, etc.).'
  },
  {
    value: 'refseq_protein',
    label: 'RefSeq Protein',
    description: 'Manually curated and standardized by NCBI.'
  }
];

/**
 * Available RNA databases
 */
export const rnaDatabases: DatabaseOption[] = [
  {
    value: 'nt',
    label: 'nt (Nucleotide database)',
    description: 'All nucleotide sequences including genomic sequences'
  },
  {
    value: 'refseq_rna',
    label: 'RefSeq RNA',
    description: 'Transcribed sequences only (mRNA/cDNA) - less noise'
  }
];

/**
 * Get available databases for a blast type
 */
export function getAvailableDatabases(type: BlastType): DatabaseOption[] {
  return type === 'protein' ? proteinDatabases : rnaDatabases;
}

/**
 * Get default database for a blast type
 */
export function getDefaultDatabase(type: BlastType): BlastDatabase {
  return type === 'protein' ? 'nr' : 'refseq_rna';
}

/**
 * Get BLAST URL and parameters that open the search form with the query prefilled.
 */
export function getBlastConfig(sequence: string, type: BlastType, database?: BlastDatabase) {
  const db = database || getDefaultDatabase(type);
  const program = type === 'protein' ? 'blastp' : 'blastn';
  
  return {
    url: 'https://blast.ncbi.nlm.nih.gov/Blast.cgi',
    params: {
      CMD: 'Web',
      PAGE_TYPE: 'BlastSearch',
      PROGRAM: program,
      BLAST_PROGRAMS: program,
      DATABASE: db,
      QUERY: sequence
    }
  };
}

/**
 * Check if a field key is a blastable sequence field
 */
export function isBlastableSequence(key: string): boolean {
  return key === 'protein_seq' || key === 'rna_seq';
}

/**
 * Get the blast type from field key
 */
export function getBlastType(fieldKey: string): BlastType {
  return fieldKey === 'protein_seq' ? 'protein' : 'rna';
}

/**
 * Open NCBI BLAST in a new tab with the query field prefilled.
 * Uses POST form submission to avoid URL length limits for long sequences.
 */
export function openBlast(fieldType: string, sequence: string, database?: BlastDatabase): void {
  if (!sequence || sequence === '[Loading...]' || sequence === '—' || sequence === '[BLOB]') {
    return;
  }

  const type = getBlastType(fieldType);
  const { url, params } = getBlastConfig(sequence, type, database);

  // Create a hidden form and submit via POST for unlimited sequence length
  const form = document.createElement('form');
  form.method = 'POST';
  form.action = url;
  form.target = '_blank';
  form.style.display = 'none';

  Object.entries(params).forEach(([key, value]) => {
    const input = document.createElement('input');
    input.type = 'hidden';
    input.name = key;
    input.value = value;
    form.appendChild(input);
  });

  document.body.appendChild(form);
  form.submit();
  document.body.removeChild(form);
}
