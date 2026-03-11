export interface PhyloRouteTarget {
  name: 'phylogenetic analysis';
  params: {
    table_names: string;
  };
  query: Record<string, string>;
}

export function buildPhyloRouteTarget(
  routeTableNames: string | string[] | undefined,
  fallbackTableName: string,
  orthogroup: string,
  currentQuery: Record<string, unknown> = {},
): PhyloRouteTarget {
  const nextTableNames = typeof routeTableNames === 'string' && routeTableNames.trim().length > 0
    ? routeTableNames
    : Array.isArray(routeTableNames) && routeTableNames.length > 0
      ? routeTableNames.join(',')
      : fallbackTableName;

  const nextQuery = Object.fromEntries(
    Object.entries(currentQuery)
      .filter(([, value]) => value !== undefined && value !== null)
      .map(([key, value]) => [key, String(value)])
  );

  nextQuery.orthogroup = orthogroup;

  return {
    name: 'phylogenetic analysis',
    params: {
      table_names: nextTableNames,
    },
    query: nextQuery,
  };
}