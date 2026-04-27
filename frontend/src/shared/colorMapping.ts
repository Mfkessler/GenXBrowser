import * as d3 from "d3";
import { getCategoricalColors } from "@/shared/Colorscales";

export type ColorMapping = Record<string, any> & { getColor?: (value: number) => string; colorScale?: d3.ScaleSequential<string>; bins?: any[] };

/**
 * Create color mapping for side colors based on visible unique values.
 * Ensures colors are maximally distinct for the provided data.
 */
export function createVisibleColorMapping(
  column_name: string,
  colType: string,
  visibleUniqueValues: (string | number | boolean | null)[],
): ColorMapping {
  if (colType === "double precision" || colType === "bigint") {
    const numericValues = visibleUniqueValues
      .filter((v): v is number => typeof v === "number" && !isNaN(v));

    if (numericValues.length === 0) {
      return { getColor: () => "#eeeeee" } as ColorMapping;
    }

    const domainMin = Math.min(...numericValues);
    const domainMax = Math.max(...numericValues);

    const colorScale = d3
      .scaleSequential(d3.interpolateBlues)
      .domain([domainMin, domainMax]);

    return {
      colorScale,
      getColor: (value: number) => {
        if (value === null || value === undefined || isNaN(value)) return "#eeeeee";
        return colorScale(value);
      },
    } as ColorMapping;
  } else if (colType === "boolean") {
    const terms = [true, false, null];
    const range = ["#36a2eb", "#e74c3c", "#ccc"];
    const scale = d3.scaleOrdinal<boolean | null, string>().domain(terms).range(range);

    const mapping: ColorMapping = {} as ColorMapping;
    terms.forEach((term) => {
      mapping[String(term)] = scale(term);
    });
    return mapping;
  } else {
    const uniqueTerms = [
      ...new Set(
        visibleUniqueValues
          .filter((v) => v !== null && v !== undefined && v !== "")
          .map((v) => String(v)),
      ),
    ].sort();

    const colors = getCategoricalColors(uniqueTerms.length);
    const scale = d3.scaleOrdinal<string, string>().domain(uniqueTerms).range(colors);

    const mapping: ColorMapping = {} as ColorMapping;
    uniqueTerms.forEach((term) => {
      mapping[term] = scale(term);
    });
    return mapping;
  }
}

/**
 * Create a unified color mapping across multiple plots.
 * Collects all unique values from all data sets and assigns colors once,
 * guaranteeing that the same value always maps to the same color.
 */
export function createUnifiedColorMapping(
  columnName: string,
  colType: string,
  allValuesAcrossPlots: (string | number | boolean | null)[],
): ColorMapping {
  return createVisibleColorMapping(columnName, colType, allValuesAcrossPlots);
}

/**
 * Global color registry keyed by "columnName" -> mapping.
 * Multiple plot instances register their values, then the registry
 * provides a consistent mapping across all plots.
 */
export class SharedColorRegistry {
  private registeredValues: Map<string, Set<string>> = new Map();
  private cachedMappings: Map<string, ColorMapping> = new Map();
  private colTypes: Map<string, string> = new Map();

  /**
   * Register values from a specific plot for a given column.
   * Call this from each plot instance with its own attribute values.
   */
  registerValues(columnName: string, colType: string, values: (string | number | boolean | null)[]): void {
    this.colTypes.set(columnName, colType);

    if (!this.registeredValues.has(columnName)) {
      this.registeredValues.set(columnName, new Set());
    }
    const existing = this.registeredValues.get(columnName)!;
    values.forEach((v) => {
      if (v !== null && v !== undefined && v !== "") {
        existing.add(String(v));
      }
    });

    // Invalidate cached mapping since values changed
    this.cachedMappings.delete(columnName);
  }

  /**
   * Get the unified color mapping for a column.
   * Returns the same mapping for all callers sharing this registry.
   */
  getMapping(columnName: string): ColorMapping | null {
    if (this.cachedMappings.has(columnName)) {
      return this.cachedMappings.get(columnName)!;
    }

    const values = this.registeredValues.get(columnName);
    const colType = this.colTypes.get(columnName);
    if (!values || !colType) return null;

    const allValues = [...values] as (string | number | boolean | null)[];
    const mapping = createUnifiedColorMapping(columnName, colType, allValues);
    this.cachedMappings.set(columnName, mapping);
    return mapping;
  }

  /** Clear all registered values and cached mappings. */
  clear(): void {
    this.registeredValues.clear();
    this.cachedMappings.clear();
    this.colTypes.clear();
  }

  // ---------------------------------------------------------------------
  // Cross-instance row-color click pulse
  // ---------------------------------------------------------------------
  /** Event broadcast when a user clicks a row-color cell in any heatmap. */
  // Using a plain function list instead of an EventTarget to keep this
  // tree-shakeable and to allow synchronous fanout.
  private clickSubscribers: Array<
    (event: { column: string; value: string | number | boolean | null }) => void
  > = [];

  /**
   * Subscribe to row-color click events from any heatmap sharing this registry.
   * Returns an unsubscribe function. Subscribers receive the same payload
   * synchronously every time `broadcastClick` is invoked.
   */
  subscribeClick(
    fn: (event: { column: string; value: string | number | boolean | null }) => void,
  ): () => void {
    this.clickSubscribers.push(fn);
    return () => {
      const i = this.clickSubscribers.indexOf(fn);
      if (i >= 0) this.clickSubscribers.splice(i, 1);
    };
  }

  /** Notify every subscriber that a row-color cell was clicked. */
  broadcastClick(
    column: string,
    value: string | number | boolean | null,
  ): void {
    const evt = { column, value };
    for (const fn of [...this.clickSubscribers]) {
      try {
        fn(evt);
      } catch {
        // Subscribers must not break the broadcast loop
      }
    }
  }
}
