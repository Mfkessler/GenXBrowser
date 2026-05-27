export function mean(values: number[]): number {
  if (values.length === 0) return 0;
  const sum = values.reduce((accumulator, value) => accumulator + value, 0);
  return sum / values.length;
}

export function median(values: number[]): number {
  if (values.length === 0) return 0;
  const sortedValues = [...values].sort((left, right) => left - right);
  const midpoint = Math.floor(sortedValues.length / 2);
  return sortedValues.length % 2
    ? sortedValues[midpoint]
    : (sortedValues[midpoint - 1] + sortedValues[midpoint]) / 2;
}