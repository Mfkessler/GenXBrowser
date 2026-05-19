export interface CardBoxSize {
  width: number;
  height: number;
}

export function readCardBoxSize(rect: Pick<DOMRectReadOnly, "width" | "height">): CardBoxSize | null {
  const width = Math.round(rect.width);
  const height = Math.round(rect.height);

  if (width <= 0 || height <= 0) {
    return null;
  }

  return { width, height };
}

export function getMirroredCardStyle(size: CardBoxSize | null): Record<string, string> | undefined {
  if (!size) {
    return undefined;
  }

  return {
    minHeight: `${size.height}px`,
    height: `${size.height}px`,
  };
}