/**
 * Vue Composable for Clustering Operations
 * 
 * Provides a reactive interface for hierarchical clustering.
 * - Uses backend API for datasets > 100 rows (more efficient)
 * - Uses Web Workers for smaller datasets (no server round-trip)
 * - Falls back to main thread if Web Workers not available
 */

import { ref, computed, watch, onUnmounted } from 'vue';
import { useVisualizationStore } from '@/stores/visualization';
import { 
  hierarchicalCluster, 
  transpose, 
  extractExpressionMatrix,
  type ClusterResult,
  type ClusterMethod,
  type ClusterDistance
} from './clustering';
import type { ClusterWorkerMessage, ClusterWorkerResponse } from './clustering.worker';
import axios from 'axios';
import { API_BASE_URL } from './Config';

// Threshold for using backend vs client-side clustering
const BACKEND_CLUSTERING_THRESHOLD = 100;

// Create worker instance (lazy initialization)
let clusterWorker: Worker | null = null;
let workerSupported = true;

function getClusterWorker(): Worker | null {
  if (!workerSupported) return null;
  
  if (!clusterWorker) {
    try {
      clusterWorker = new Worker(
        new URL('./clustering.worker.ts', import.meta.url),
        { type: 'module' }
      );
    } catch (e) {
      console.warn('Web Workers not supported, falling back to main thread clustering');
      workerSupported = false;
      return null;
    }
  }
  
  return clusterWorker;
}

// Pending requests for worker responses
const pendingRequests = new Map<string, {
  resolve: (response: ClusterWorkerResponse) => void;
  reject: (error: Error) => void;
}>();

// Setup worker message handler
function setupWorkerHandler() {
  const worker = getClusterWorker();
  if (!worker) return;
  
  worker.onmessage = (event: MessageEvent<ClusterWorkerResponse>) => {
    const { requestId, type, error } = event.data;
    const pending = pendingRequests.get(requestId);
    
    if (!pending) return;
    
    if (type === 'error') {
      pending.reject(new Error(error || 'Clustering failed'));
      pendingRequests.delete(requestId);
    } else if (type === 'result') {
      pending.resolve(event.data);
      pendingRequests.delete(requestId);
    }
    // Progress messages are handled separately if needed
  };
  
  worker.onerror = (event) => {
    console.error('Cluster worker error:', event);
    // Reject all pending requests
    pendingRequests.forEach((pending) => {
      pending.reject(new Error('Worker error'));
    });
    pendingRequests.clear();
  };
}

/**
 * Send clustering request to worker
 */
async function clusterWithWorker(
  data: number[][],
  method: ClusterMethod,
  distance: ClusterDistance,
  type: 'clusterRows' | 'clusterCols' | 'clusterBoth'
): Promise<ClusterWorkerResponse> {
  const worker = getClusterWorker();
  
  if (!worker) {
    // Fallback to main thread
    return clusterOnMainThread(data, method, distance, type);
  }
  
  setupWorkerHandler();
  
  const requestId = `cluster-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
  
  return new Promise((resolve, reject) => {
    pendingRequests.set(requestId, { resolve, reject });
    
    const message: ClusterWorkerMessage = {
      type,
      data,
      method,
      distance,
      requestId
    };
    
    worker.postMessage(message);
    
    // Timeout after 60 seconds
    setTimeout(() => {
      if (pendingRequests.has(requestId)) {
        pendingRequests.delete(requestId);
        reject(new Error('Clustering timeout'));
      }
    }, 60000);
  });
}

/**
 * Fallback: cluster on main thread
 */
function clusterOnMainThread(
  data: number[][],
  method: ClusterMethod,
  distance: ClusterDistance,
  type: 'clusterRows' | 'clusterCols' | 'clusterBoth'
): ClusterWorkerResponse {
  let rowResult: ClusterResult | undefined;
  let colResult: ClusterResult | undefined;
  
  if (type === 'clusterRows' || type === 'clusterBoth') {
    rowResult = hierarchicalCluster(data, method, distance);
  }
  
  if (type === 'clusterCols' || type === 'clusterBoth') {
    const transposedData = transpose(data);
    colResult = hierarchicalCluster(transposedData, method, distance);
  }
  
  return {
    type: 'result',
    requestId: 'main-thread',
    rowResult,
    colResult
  };
}

/**
 * Vue composable for clustering
 */
export function useClustering() {
  const visualizationStore = useVisualizationStore();
  
  const isComputing = ref(false);
  const error = ref<string | null>(null);
  
  /**
   * Perform clustering via backend API (for large datasets)
   */
  async function performBackendClustering(
    tableName: string,
    filters: Record<string, any>,
    sampleFilters: Record<string, any>,
    clusterRows: boolean,
    clusterCols: boolean,
    method: ClusterMethod,
    distance: ClusterDistance
  ): Promise<{ rowOrder: number[] | null; colOrder: number[] | null }> {
    const response = await axios.post(`${API_BASE_URL}/api/cluster`, {
      table_name: tableName,
      filters,
      sample_filters: sampleFilters,
      transform: visualizationStore.expressionDisplay.transform,
      layer: visualizationStore.expressionDisplay.layer,
      cluster_rows: clusterRows,
      cluster_cols: clusterCols,
      method,
      distance
    });
    
    return {
      rowOrder: response.data.row_order,
      colOrder: response.data.col_order
    };
  }

  /**
   * Perform clustering on the given data
   * 
   * @param rows - Array of row objects (genes/transcripts)
   * @param dataColumns - Names of columns containing expression values
   * @param tableName - Optional table name for backend clustering
   * @param filters - Optional filters for backend clustering
   * @param sampleFilters - Optional sample filters for backend clustering
   * @returns Promise that resolves when clustering is complete
   */
  async function performClustering(
    rows: Record<string, any>[],
    dataColumns: string[],
    tableName?: string,
    filters?: Record<string, any>,
    sampleFilters?: Record<string, any>
  ): Promise<void> {
    const { clusterRows, clusterCols, method, distance } = visualizationStore.clustering;
    
    // Nothing to cluster
    if (!clusterRows && !clusterCols) {
      visualizationStore.setClusterRowOrder(null);
      visualizationStore.setClusterColOrder(null);
      return;
    }
    
    // Skip if data is too small
    if (rows.length < 2 || dataColumns.length < 2) {
      console.warn('Not enough data for clustering');
      return;
    }
    
    isComputing.value = true;
    visualizationStore.setClusteringComputing(true);
    error.value = null;
    
    try {
      // Use backend for large datasets (> 100 rows)
      if (rows.length > BACKEND_CLUSTERING_THRESHOLD && tableName) {
        console.log(`Using backend clustering for ${rows.length} rows`);
        
        const result = await performBackendClustering(
          tableName,
          filters || {},
          sampleFilters || {},
          clusterRows,
          clusterCols,
          method,
          distance
        );
        
        if (result.rowOrder && clusterRows) {
          visualizationStore.setClusterRowOrder(result.rowOrder);
        }
        if (result.colOrder && clusterCols) {
          visualizationStore.setClusterColOrder(result.colOrder);
        }
        
        return;
      }
      
      // Client-side clustering for smaller datasets
      console.log(`Using client-side clustering for ${rows.length} rows`);
      
      // Check limits for client-side
      const maxRows = 5000;
      const maxCols = 500;
      
      if (rows.length > maxRows) {
        console.warn(`Too many rows for client-side clustering (${rows.length} > ${maxRows}).`);
        error.value = `Dataset too large for clustering (${rows.length} rows). Maximum is ${maxRows}.`;
        return;
      }
      
      if (dataColumns.length > maxCols) {
        console.warn(`Too many columns for client-side clustering (${dataColumns.length} > ${maxCols}).`);
        error.value = `Too many columns for clustering (${dataColumns.length}). Maximum is ${maxCols}.`;
        return;
      }
      // Extract numeric expression matrix
      const expressionMatrix = extractExpressionMatrix(rows, dataColumns);
      
      // Determine what to cluster
      let type: 'clusterRows' | 'clusterCols' | 'clusterBoth';
      if (clusterRows && clusterCols) {
        type = 'clusterBoth';
      } else if (clusterRows) {
        type = 'clusterRows';
      } else {
        type = 'clusterCols';
      }
      
      // Perform clustering (worker or main thread)
      const result = await clusterWithWorker(expressionMatrix, method, distance, type);
      
      // Update store with results
      if (result.rowResult && clusterRows) {
        visualizationStore.setClusterRowOrder(result.rowResult.order);
      }
      
      if (result.colResult && clusterCols) {
        visualizationStore.setClusterColOrder(result.colResult.order);
      }
      
    } catch (e) {
      const errorMessage = e instanceof Error ? e.message : 'Clustering failed';
      console.error('Clustering error:', errorMessage);
      error.value = errorMessage;
      
      // Clear cluster orders on error
      visualizationStore.setClusterRowOrder(null);
      visualizationStore.setClusterColOrder(null);
    } finally {
      isComputing.value = false;
      visualizationStore.setClusteringComputing(false);
    }
  }
  
  /**
   * Clear all clustering results
   */
  function clearClustering() {
    visualizationStore.setClusterRowOrder(null);
    visualizationStore.setClusterColOrder(null);
    visualizationStore.setClusterRows(false);
    visualizationStore.setClusterCols(false);
  }
  
  // Cleanup worker on unmount
  onUnmounted(() => {
    // Don't terminate shared worker, just clear pending requests
    pendingRequests.clear();
  });
  
  return {
    performClustering,
    clearClustering,
    isComputing: computed(() => isComputing.value),
    error: computed(() => error.value)
  };
}
