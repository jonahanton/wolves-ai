export interface SparklineGeometry {
  path: string | null;
  endPoint: { x: number; y: number };
}

export function sparklineGeometry(
  values: number[],
  width: number,
  height: number,
  pad = 2,
): SparklineGeometry | null {
  if (values.length === 0) return null;

  const min = Math.min(...values);
  const max = Math.max(...values);
  const span = max - min || 1;
  const innerW = width - pad * 2;
  const innerH = height - pad * 2;

  const point = (value: number, index: number) => ({
    x: values.length === 1 ? width / 2 : pad + (index / (values.length - 1)) * innerW,
    y: pad + (1 - (value - min) / span) * innerH,
  });

  const points = values.map(point);
  const endPoint = points[points.length - 1];
  if (points.length === 1) return { path: null, endPoint };

  const path = points
    .map((p, i) => `${i === 0 ? "M" : "L"}${p.x.toFixed(1)},${p.y.toFixed(1)}`)
    .join(" ");
  return { path, endPoint };
}
