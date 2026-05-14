export function getHeatmapGridTemplate(columnCount: number): string {
  if (columnCount <= 1) {
    return 'minmax(0, 1fr)';
  }

  return 'repeat(auto-fit, minmax(min(100%, 36rem), 1fr))';
}

export function getHeatmapCardMinHeight(columnCount: number): string {
  if (columnCount <= 1) return 'clamp(30rem, 74vh, 52rem)';
  if (columnCount === 2) return 'clamp(30rem, 68vh, 46rem)';
  return '34rem';
}