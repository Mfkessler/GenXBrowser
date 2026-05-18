export type MetadataRow = Record<string, unknown>;
export type MetadataFilterObject = {
  value?: string | boolean | number | [number, number] | unknown[] | null;
  match_mode?: "or" | "and";
  exact?: boolean;
  has_value?: boolean;
};
export type MetadataFilterValue = MetadataFilterObject | string | boolean | number | [number, number] | unknown[] | null | undefined;

function splitFilterTerms(value: unknown): string[] {
  if (Array.isArray(value)) return value.map(String).map((v) => v.trim()).filter(Boolean);
  if (typeof value !== "string") return value === null || value === undefined ? [] : [String(value)];
  return value
    .split(value.includes("|") ? "|" : ",")
    .map((v) => v.trim())
    .filter(Boolean);
}

function cellValues(value: unknown): string[] {
  if (Array.isArray(value)) return value.map(String).map((v) => v.trim());
  if (value === null || value === undefined) return [];
  return [String(value).trim()];
}

const NULL_LIKE_VALUES = new Set(["", "null", "none", "na", "n/a", "nan", "nat"]);

function isNonMissingMetadataValue(value: unknown): boolean {
  if (value === null || value === undefined) return false;
  if (typeof value === "number") return Number.isFinite(value);
  if (typeof value === "string") return !NULL_LIKE_VALUES.has(value.trim().toLowerCase());
  if (Array.isArray(value)) return value.some(isNonMissingMetadataValue);
  return true;
}

function matchesText(value: unknown, terms: string[], matchMode: "or" | "and", exact: boolean): boolean {
  const values = cellValues(value);
  if (terms.length === 0) return true;
  if (values.length === 0) return false;

  if (exact) {
    const valueSet = new Set(values);
    return matchMode === "and"
      ? terms.every((term) => valueSet.has(term))
      : terms.some((term) => valueSet.has(term));
  }

  const loweredValues = values.map((item) => item.toLowerCase());
  return matchMode === "and"
    ? terms.every((term) => loweredValues.some((item) => item.includes(term.toLowerCase())))
    : terms.some((term) => loweredValues.some((item) => item.includes(term.toLowerCase())));
}

function matchesRange(value: unknown, range: unknown[]): boolean {
  if (range.length !== 2) return false;
  const min = Number(range[0]);
  const max = Number(range[1]);
  const current = Number(value);
  return Number.isFinite(min) && Number.isFinite(max) && Number.isFinite(current) && current >= min && current <= max;
}

export function metadataRowMatchesFilter(row: MetadataRow, columnName: string, filter: MetadataFilterValue): boolean {
  if (filter === null || filter === undefined) return true;

  if (typeof filter === "object" && !Array.isArray(filter) && "value" in filter) {
    const spec = filter as MetadataFilterObject;
    const value = spec.value;
    if (spec.has_value && !isNonMissingMetadataValue(row[columnName])) return false;
    if (value === "") return true;
    if (Array.isArray(value) && value.length === 2 && value.every((item) => typeof item === "number")) {
      return matchesRange(row[columnName], value);
    }
    return matchesText(
      row[columnName],
      splitFilterTerms(value),
      spec.match_mode === "and" ? "and" : "or",
      spec.exact !== false,
    );
  }

  if (Array.isArray(filter)) {
    if (filter.length === 2 && filter.every((item) => typeof item === "number")) {
      return matchesRange(row[columnName], filter);
    }
    return matchesText(row[columnName], splitFilterTerms(filter), "or", true);
  }

  if (typeof filter === "boolean") return row[columnName] === filter;
  if (typeof filter === "number") return Number(row[columnName]) === filter;
  return matchesText(row[columnName], splitFilterTerms(filter), "or", true);
}

export function filterMetadataRows(
  rows: MetadataRow[],
  filters: Record<string, MetadataFilterValue>,
  allowedColumns: Set<string>,
): MetadataRow[] {
  return rows.filter((row) =>
    Object.entries(filters).every(([columnName, filter]) =>
      !allowedColumns.has(columnName) || metadataRowMatchesFilter(row, columnName, filter),
    ),
  );
}

export function uniqueMetadataValues(rows: MetadataRow[], columnName: string): string[] {
  return [
    ...new Set(
      rows
        .flatMap((row) => cellValues(row[columnName]))
        .filter(isNonMissingMetadataValue),
    ),
  ].sort();
}