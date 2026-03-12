type SpeciesCodeMap = Record<string, string>;

type GeneMetrics = Record<string, unknown>;

type MetricsByTable = Record<string, GeneMetrics>;

export interface PhyloLeafDatasetMatch {
  tableName: string;
  geneId: string;
  matchedPrefix: string;
}

export interface ResolvedPhyloLeafMatch extends PhyloLeafDatasetMatch {
  matchedKey: string;
}

function unique(values: string[]): string[] {
  const seen = new Set<string>();
  return values.filter((value) => {
    const trimmed = value.trim();
    if (!trimmed || seen.has(trimmed)) {
      return false;
    }
    seen.add(trimmed);
    return true;
  });
}

function toSentenceCaseTableName(tableName: string): string {
  return tableName ? tableName.charAt(0).toUpperCase() + tableName.slice(1) : tableName;
}

function buildDatasetPrefixes(tableNames: string[], speciesCodeMap: SpeciesCodeMap): Array<{ prefix: string; tableName: string }> {
  const prefixes = tableNames.flatMap((tableName) => {
    const speciesCode = speciesCodeMap[tableName]?.trim();
    return [
      { prefix: tableName, tableName },
      { prefix: toSentenceCaseTableName(tableName), tableName },
      ...(speciesCode ? [{ prefix: speciesCode, tableName }] : []),
    ];
  });

  return prefixes.sort((left, right) => right.prefix.length - left.prefix.length);
}

function findMatchingKey(genesObj: GeneMetrics | undefined, candidateKeys: string[]): string | null {
  if (!genesObj) {
    return null;
  }

  for (const candidate of candidateKeys) {
    if (candidate in genesObj) {
      return candidate;
    }
  }

  return null;
}

export function buildPhyloMetricKeys(tableName: string, geneId: string, speciesCode?: string): string[] {
  const trimmedTableName = tableName.trim();
  const trimmedGeneId = geneId.trim();
  const trimmedSpeciesCode = speciesCode?.trim();

  return unique([
    trimmedGeneId,
    trimmedSpeciesCode ? `${trimmedSpeciesCode}_${trimmedGeneId}` : "",
    trimmedTableName ? `${trimmedTableName}_${trimmedGeneId}` : "",
    trimmedTableName ? `${toSentenceCaseTableName(trimmedTableName)}_${trimmedGeneId}` : "",
  ]);
}

export function matchLeafToDataset(
  leafName: string,
  tableNames: string[],
  speciesCodeMap: SpeciesCodeMap = {},
): PhyloLeafDatasetMatch | null {
  const trimmedLeafName = leafName.trim();
  const lowerLeafName = trimmedLeafName.toLowerCase();

  for (const { prefix, tableName } of buildDatasetPrefixes(tableNames, speciesCodeMap)) {
    if (!lowerLeafName.startsWith(`${prefix.toLowerCase()}_`)) {
      continue;
    }

    return {
      tableName,
      geneId: trimmedLeafName.slice(prefix.length + 1),
      matchedPrefix: prefix,
    };
  }

  return null;
}

export function resolvePhyloLeafMatch(
  leafName: string,
  metrics: MetricsByTable,
  speciesCodeMap: SpeciesCodeMap = {},
): ResolvedPhyloLeafMatch | null {
  const tableNames = Object.keys(metrics);
  const datasetMatch = matchLeafToDataset(leafName, tableNames, speciesCodeMap);

  if (datasetMatch) {
    const matchedKey = findMatchingKey(
      metrics[datasetMatch.tableName],
      unique([
        leafName,
        ...buildPhyloMetricKeys(
          datasetMatch.tableName,
          datasetMatch.geneId,
          speciesCodeMap[datasetMatch.tableName],
        ),
      ]),
    );

    if (matchedKey) {
      return {
        ...datasetMatch,
        matchedKey,
      };
    }
  }

  const fallbackMatches = tableNames.flatMap((tableName) => {
    const matchedKey = findMatchingKey(
      metrics[tableName],
      buildPhyloMetricKeys(tableName, leafName, speciesCodeMap[tableName]),
    );

    if (!matchedKey) {
      return [];
    }

    return [{
      tableName,
      geneId: leafName,
      matchedPrefix: '',
      matchedKey,
    }];
  });

  return fallbackMatches.length === 1 ? fallbackMatches[0] : null;
}