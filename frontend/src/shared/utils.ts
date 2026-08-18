// Formatting rules for common bioinformatics column abbreviations.
// Add new entries here when column names need special formatting.
const column_mappings: Record<string, string> = {
  "Ec Number": "EC Number",
  "Go Term": "GO Term",
  "Ncbi": "NCBI",
  "Gene Id": "Gene ID",
  "Is Tf": "Is TF",
  "Tf Family": "TF Family",
  "Og": "Orthogroup",
  "Rna Seq": "RNA Seq",
  "Protein Seq": "Protein Seq",
};

/**
 * Apply binomial nomenclature formatting: genus is capitalized, species epithet is lowercase.
 * E.g. "Arabidopsis Thaliana" → "Arabidopsis thaliana"
 */
function applyBinomialFormatting(label: string): string {
  const words = label.split(" ");
  if (words.length === 2 && words[0][0] === words[0][0].toUpperCase() && words[1][0] === words[1][0].toUpperCase()) {
    // Likely a binomial name with incorrect capitalization
    return words[0] + " " + words[1].toLowerCase();
  }
  return label;
}

export function beautifyLabel(label: string | null): string {
  if (!label) return "";

  // If label contains spaces, it's already formatted (display_name from config)
  // Return as-is to preserve formatting like "Transcript ID", "GO Term", etc.
  if (label.includes(" ")) {
    return label;
  }

  // Step 1: normalize label with existing rules (for snake_case column_names)
  let beautified = label
    .replace("_col", "")
    .split("_")
    .map((word) =>
      word.length > 0
        ? word.charAt(0).toUpperCase() + word.slice(1).toLowerCase()
        : "",
    )
    .join(" ");

  // Step 2: apply binomial nomenclature formatting (genus Species → genus species)
  beautified = applyBinomialFormatting(beautified);

  // Step 3: replace any mapping matches in the joined string (exact match)
  if (column_mappings[beautified]) {
    return column_mappings[beautified];
  }

  return beautified;
}

export function parseBoolean(value: unknown): boolean | null {
  if (typeof value === "boolean") {
    return value; // already boolean
  }
  if (typeof value === "string") {
    switch (value.toLowerCase()) {
      case "true":
      case "yes":
      case "1":
        return true;
      case "false":
      case "no":
      case "0":
        return false;
      default:
        return false; // or throw error if you want strict validation
    }
  }
  if (typeof value === "number") {
    return value === 1;
  }

  // Returns null if no conversion fitted or value is null
  return null;
}

export function compareValues(
  a: unknown,
  b: unknown,
  order: "asc" | "desc" = "asc",
): number {
  // Handle list metadata by comparing the same normalized set key used for colors.
  if (Array.isArray(a)) {
    a = a.map((entry) => String(entry).trim()).filter(Boolean).sort((x, y) => x.localeCompare(y)).join("|");
  }
  if (Array.isArray(b)) {
    b = b.map((entry) => String(entry).trim()).filter(Boolean).sort((x, y) => x.localeCompare(y)).join("|");
  }

  // Handle booleans with specified rules
  if (typeof a === "boolean" && typeof b === "boolean") {
    if (order === "asc")
      return a === b ? 0 : a ? -1 : 1; // true < false
    else return a === b ? 0 : a ? 1 : -1; // false < true descending
  }

  // For numbers or numeric strings, coerce to number for numeric comparison
  const numA = typeof a === "number" ? a : parseFloat(String(a));
  const numB = typeof b === "number" ? b : parseFloat(String(b));
  const isNumA = !isNaN(numA);
  const isNumB = !isNaN(numB);

  if (isNumA && isNumB) {
    if (numA < numB) return order === "asc" ? -1 : 1;
    if (numA > numB) return order === "asc" ? 1 : -1;
    return 0;
  }

  // Otherwise assume string comparison
  const strA = String(a).toLowerCase();
  const strB = String(b).toLowerCase();
  if (strA < strB) return order === "asc" ? -1 : 1;
  if (strA > strB) return order === "asc" ? 1 : -1;
  return 0;
}

//FISHER EXACT based on https://bioinfo.iric.ca/a-javascript-implementation-of-the-non-central-version-of-fishers-exact-test/
function lngamm(z: number): number {
  let x = 0;
  x += 0.1659470187408462e-6 / (z + 7);
  x += 0.9934937113930748e-5 / (z + 6);
  x -= 0.1385710331296526 / (z + 5);
  x += 12.50734324009056 / (z + 4);
  x -= 176.6150291498386 / (z + 3);
  x += 771.3234287757674 / (z + 2);
  x -= 1259.139216722289 / (z + 1);
  x += 676.5203681218835 / z;
  x += 0.9999999999995183;
  return Math.log(x) - 5.58106146679532777 - z + (z - 0.5) * Math.log(z + 6.5);
}
function lnfact(n: number): number {
  if (n <= 1) return 0;
  return lngamm(n + 1);
}
function lnbico(n: number, k: number): number {
  return lnfact(n) - lnfact(k) - lnfact(n - k);
}
export function exact_nc(
  n11: number,
  n12: number,
  n21: number,
  n22: number,
  w = 1,
): number {
  const x = n11;
  const m1 = n11 + n21;
  const m2 = n12 + n22;
  const n = n11 + n12;
  const x_min = Math.max(0, n - m2);
  const x_max = Math.min(n, m1);
  const l = [];
  for (let y = x_min; y <= x_max; y++) {
    l[y - x_min] = lnbico(m1, y) + lnbico(m2, n - y) + y * Math.log(w);
  }
  const max_l = Math.max(...l);
  const sum_l = Math.log(l.reduce((acc, cur) => acc + Math.exp(cur - max_l), 0));
  const den_sum = Math.log(
    l.slice(x - x_min).reduce((acc, cur) => acc + Math.exp(cur - max_l), 0),
  );
  return Math.exp(den_sum - sum_l);
}

export function jsonToTsv(data: Record<string, unknown>[]): string {
  if (!Array.isArray(data) || data.length === 0) return "";

  const header = Object.keys(data[0]);
  const escape = (val: unknown) => {
    if (Array.isArray(val)) return `"${val.join(",")}"`; // Join arrays with comma, quote for TSV safety
    if (typeof val === "string")
      return val.replace(/\t/g, " ").replace(/\n/g, " ");
    return val == null ? "" : String(val);
  };

  const rows = data.map((row) =>
    header.map((key) => escape(row[key])).join("\t"),
  );
  return [header.join("\t"), ...rows].join("\n");
}

/**
 * Checks if a cell value is completely empty (null, undefined, empty string, or whitespace only)
 * @param value - Cell value to check
 * @returns True if value is empty
 */
export function isCellEmpty(value: unknown): boolean {
  if (value === null || value === undefined) return true;
  if (Array.isArray(value)) return value.length === 0;
  const str = String(value).trim();
  return str === '' || str === 'null' || str === 'undefined';
}
