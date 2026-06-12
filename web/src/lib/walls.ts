// One directory per family; families are never mixed in a wall.
export type WallFamily = "wc" | "euros";

const COUNTS: Record<WallFamily, number> = { wc: 8, euros: 12 };

export interface WallTile {
  src: string;
  span2: boolean;
  rowSpan2: boolean;
}

export function wallTiles(family: WallFamily, count: number): WallTile[] {
  const available = COUNTS[family];
  return Array.from({ length: count }, (_, i) => {
    const n = (i * 5) % available;
    const name = family === "wc" ? `w${String(n + 1).padStart(2, "0")}` : `p${String(n + 1).padStart(2, "0")}`;
    return {
      src: `/walls/${family}/${name}.jpg`,
      span2: i % 7 === 0 || i % 7 === 3,
      rowSpan2: family === "euros" && i % 11 === 0,
    };
  });
}
