/**
 * Web Worker for Hierarchical Clustering
 * 
 * Performs clustering computations off the main thread to prevent UI blocking.
 * Uses postMessage for communication with the main thread.
 */

import { 
  hierarchicalCluster, 
  transpose, 
  type ClusterMethod, 
  type ClusterDistance,
  type ClusterResult 
} from './clustering';

export interface ClusterWorkerMessage {
  type: 'clusterRows' | 'clusterCols' | 'clusterBoth';
  data: number[][];
  method: ClusterMethod;
  distance: ClusterDistance;
  requestId: string;
}

export interface ClusterWorkerResponse {
  type: 'result' | 'error' | 'progress';
  requestId: string;
  rowResult?: ClusterResult;
  colResult?: ClusterResult;
  error?: string;
  progress?: number;
}

// Handle incoming messages
self.onmessage = (event: MessageEvent<ClusterWorkerMessage>) => {
  const { type, data, method, distance, requestId } = event.data;
  
  try {
    let rowResult: ClusterResult | undefined;
    let colResult: ClusterResult | undefined;
    
    // Report start
    self.postMessage({
      type: 'progress',
      requestId,
      progress: 0
    } as ClusterWorkerResponse);
    
    if (type === 'clusterRows' || type === 'clusterBoth') {
      rowResult = hierarchicalCluster(data, method, distance);
      
      self.postMessage({
        type: 'progress',
        requestId,
        progress: type === 'clusterBoth' ? 50 : 100
      } as ClusterWorkerResponse);
    }
    
    if (type === 'clusterCols' || type === 'clusterBoth') {
      // Transpose data for column clustering
      const transposedData = transpose(data);
      colResult = hierarchicalCluster(transposedData, method, distance);
      
      self.postMessage({
        type: 'progress',
        requestId,
        progress: 100
      } as ClusterWorkerResponse);
    }
    
    // Send final result
    self.postMessage({
      type: 'result',
      requestId,
      rowResult,
      colResult
    } as ClusterWorkerResponse);
    
  } catch (error) {
    self.postMessage({
      type: 'error',
      requestId,
      error: error instanceof Error ? error.message : 'Unknown clustering error'
    } as ClusterWorkerResponse);
  }
};

// Export types for TypeScript
export {};
