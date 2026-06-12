import { type WallFamily, wallTiles } from "@/lib/walls";

interface PhotoWallProps {
  family: WallFamily;
  count?: number;
}

export function PhotoWall({ family, count = 20 }: PhotoWallProps) {
  return (
    <div
      aria-hidden
      className="absolute inset-0 z-0 grid grid-flow-dense auto-rows-fr grid-cols-3 gap-0 overflow-hidden sm:grid-cols-6"
    >
      {wallTiles(family, count).map((tile, index) => (
        // eslint-disable-next-line @next/next/no-img-element
        <img
          key={index}
          src={tile.src}
          alt=""
          loading="lazy"
          className={`h-full w-full object-cover saturate-[1.05] contrast-[1.02] ${tile.span2 ? "col-span-2" : ""}`}
        />
      ))}
      <div className="absolute inset-0 z-[3] bg-[linear-gradient(180deg,oklch(0.175_0.014_65/0.93),oklch(0.175_0.014_65/0.82)_30%,oklch(0.175_0.014_65/0.88)_70%,oklch(0.175_0.014_65/0.97))]" />
    </div>
  );
}
