export function getHeatmapGridTemplate(columnCount: number): string {
  if (columnCount <= 1) {
    return 'minmax(0, 1fr)';
  }

  return 'repeat(auto-fit, minmax(min(100%, 30rem), 1fr))';
}

export function getHeatmapCardMinHeight(columnCount: number): string {
  return columnCount <= 2 ? '0' : '28rem';
}