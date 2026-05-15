/**
 * Hierarchical Clustering Utility for Gene Expression Heatmaps
 * 
 * Implements agglomerative hierarchical clustering with:
 * - Average linkage (UPGMA) - recommended for gene expression data
 * - Complete linkage
 * - Ward's method
 * 
 * Distance metrics:
 * - Pearson correlation distance (1 - r) - best for expression patterns
 * - Euclidean distance
 * 
 * Includes Optimal Leaf Ordering (OLO) for improved visualization.
 */

import { agnes } from 'ml-hclust';

export type ClusterMethod = 'average' | 'complete' | 'ward';
export type ClusterDistance = 'correlation' | 'euclidean';

export interface ClusterResult {
  order: number[];           // Optimal leaf ordering indices
  dendrogram: ClusterNode;   // Tree structure for optional rendering
}

export interface ClusterNode {
  index?: number;           // Leaf index (for leaf nodes)
  height: number;           // Merge height
  children?: ClusterNode[]; // Child nodes (for internal nodes)
  size: number;             // Number of leaves in subtree
}

interface HClusterNode {
  isLeaf: boolean;
  index?: number;
  height: number;
  children?: HClusterNode[];
}

/**
 * Compute Pearson correlation coefficient between two vectors
 */
function pearsonCorrelation(x: number[], y: number[]): number {
  const n = x.length;
  if (n === 0) return 0;
  
  let sumX = 0, sumY = 0, sumXY = 0, sumX2 = 0, sumY2 = 0;
  
  for (let i = 0; i < n; i++) {
    sumX += x[i];
    sumY += y[i];
    sumXY += x[i] * y[i];
    sumX2 += x[i] * x[i];
    sumY2 += y[i] * y[i];
  }
  
  const num = n * sumXY - sumX * sumY;
  const den = Math.sqrt((n * sumX2 - sumX * sumX) * (n * sumY2 - sumY * sumY));
  
  if (den === 0) return 0;
  return num / den;
}

/**
 * Compute correlation distance (1 - r)
 */
function correlationDistance(x: number[], y: number[]): number {
  return 1 - pearsonCorrelation(x, y);
}

/**
 * Compute Euclidean distance between two vectors
 */
function euclideanDistance(x: number[], y: number[]): number {
  let sum = 0;
  for (let i = 0; i < x.length; i++) {
    const diff = x[i] - y[i];
    sum += diff * diff;
  }
  return Math.sqrt(sum);
}

/**
 * Compute pairwise distance matrix
 */
function computeDistanceMatrix(
  data: number[][],
  distanceMetric: ClusterDistance
): number[][] {
  const n = data.length;
  const distMatrix: number[][] = new Array(n);
  
  for (let i = 0; i < n; i++) {
    distMatrix[i] = new Array(n).fill(0);
  }
  
  const distFn = distanceMetric === 'correlation' 
    ? correlationDistance 
    : euclideanDistance;
  
  for (let i = 0; i < n; i++) {
    for (let j = i + 1; j < n; j++) {
      const d = distFn(data[i], data[j]);
      distMatrix[i][j] = d;
      distMatrix[j][i] = d;
    }
  }
  
  return distMatrix;
}

/**
 * Convert ml-hclust tree to our ClusterNode format
 */
function convertToClusterNode(tree: HClusterNode): ClusterNode {
  if (tree.isLeaf) {
    return {
      index: tree.index ?? 0,
      height: 0,
      size: 1
    };
  }
  
  const children = (tree.children ?? []).map((child) => convertToClusterNode(child));
  const size = children.reduce((sum: number, c: ClusterNode) => sum + c.size, 0);
  
  return {
    height: tree.height,
    children,
    size
  };
}

/**
 * Extract leaf order from dendrogram using depth-first traversal
 * This provides a natural ordering where similar items are adjacent
 */
function extractLeafOrder(node: ClusterNode): number[] {
  if (node.index !== undefined) {
    return [node.index];
  }
  
  if (!node.children) return [];
  
  const orders: number[][] = node.children.map(child => extractLeafOrder(child));
  return orders.flat();
}

/**
 * Optimal Leaf Ordering (OLO) - Bar-Joseph et al. 2001
 * Reorders leaves to minimize the sum of distances between adjacent leaves
 * 
 * This is a simplified greedy approach for efficiency.
 * Full OLO is O(n^3) which may be too slow for large datasets.
 */
function optimalLeafOrdering(
  node: ClusterNode,
  distMatrix: number[][]
): number[] {
  // For small trees, use the simple DFS order
  if (node.size <= 3) {
    return extractLeafOrder(node);
  }
  
  // For leaf nodes
  if (node.index !== undefined) {
    return [node.index];
  }
  
  if (!node.children || node.children.length < 2) {
    return extractLeafOrder(node);
  }
  
  // Recursively get optimized orders for children
  const leftOrder = optimalLeafOrdering(node.children[0], distMatrix);
  const rightOrder = optimalLeafOrdering(node.children[1], distMatrix);
  
  // Try all 4 possible orderings and pick the one with minimum adjacent distance
  const orderings = [
    [...leftOrder, ...rightOrder],
    [...leftOrder, ...rightOrder.slice().reverse()],
    [...leftOrder.slice().reverse(), ...rightOrder],
    [...leftOrder.slice().reverse(), ...rightOrder.slice().reverse()]
  ];
  
  let bestOrdering = orderings[0];
  let minDistance = Infinity;
  
  for (const ordering of orderings) {
    // Calculate sum of adjacent distances
    let totalDist = 0;
    for (let i = 0; i < ordering.length - 1; i++) {
      totalDist += distMatrix[ordering[i]][ordering[i + 1]];
    }
    
    if (totalDist < minDistance) {
      minDistance = totalDist;
      bestOrdering = ordering;
    }
  }
  
  return bestOrdering;
}

/**
 * Main clustering function
 * 
 * @param data - 2D array where each row is a sample and each column is a feature
 *               For row clustering: rows = genes, columns = samples
 *               For column clustering: transpose the data first
 * @param method - Linkage method: 'average' (UPGMA), 'complete', or 'ward'
 * @param distance - Distance metric: 'correlation' or 'euclidean'
 * @returns ClusterResult with optimal leaf ordering and dendrogram
 */
export function hierarchicalCluster(
  data: number[][],
  method: ClusterMethod = 'average',
  distance: ClusterDistance = 'correlation'
): ClusterResult {
  if (data.length === 0) {
    return { order: [], dendrogram: { height: 0, size: 0 } };
  }
  
  if (data.length === 1) {
    return { 
      order: [0], 
      dendrogram: { index: 0, height: 0, size: 1 } 
    };
  }
  
  // Compute distance matrix
  const distMatrix = computeDistanceMatrix(data, distance);
  
  // Perform hierarchical clustering using ml-hclust
  const tree = agnes(distMatrix, { 
    method: method === 'average' ? 'upgma' : method,
    isDistanceMatrix: true 
  });
  
  // Convert to our format
  const dendrogram = convertToClusterNode(tree);
  
  // Apply optimal leaf ordering
  const order = optimalLeafOrdering(dendrogram, distMatrix);
  
  return { order, dendrogram };
}

/**
 * Transpose a 2D matrix
 * Use this to cluster columns instead of rows
 */
export function transpose(matrix: number[][]): number[][] {
  if (matrix.length === 0) return [];
  const rows = matrix.length;
  const cols = matrix[0].length;
  
  const result: number[][] = new Array(cols);
  for (let j = 0; j < cols; j++) {
    result[j] = new Array(rows);
    for (let i = 0; i < rows; i++) {
      result[j][i] = matrix[i][j];
    }
  }
  
  return result;
}

/**
 * Extract numeric expression data from row data
 * 
 * @param rows - Array of row objects with mixed data
 * @param dataColumns - Names of columns containing numeric expression data
 * @returns 2D array suitable for clustering
 */
export function extractExpressionMatrix(
  rows: Record<string, unknown>[],
  dataColumns: string[]
): number[][] {
  return rows.map(row => {
    return dataColumns.map(col => {
      const val = row[col];
      if (typeof val === 'number' && !isNaN(val)) {
        return val;
      }
      return 0; // Default for missing/non-numeric values
    });
  });
}

/**
 * Apply cluster ordering to an array
 * 
 * @param items - Original array of items
 * @param order - New index order from clustering
 * @returns Reordered array
 */
export function applyClusterOrder<T>(items: T[], order: number[]): T[] {
  if (order.length !== items.length) {
    console.warn('Cluster order length mismatch, returning original order');
    return items;
  }
  return order.map(i => items[i]);
}
