import { type WallFamily, wallTiles } from "@/lib/walls";

interface FestivalBandProps {
  family: WallFamily;
  tag: string;
}

export function FestivalBand({ family, tag }: FestivalBandProps) {
  return (
    <div className="relative overflow-hidden border-t border-hairline">
      <div className="grid grid-flow-dense auto-rows-[clamp(100px,15vw,200px)] grid-cols-3 sm:grid-cols-6">
        {wallTiles(family, 16).map((tile, index) => (
          // eslint-disable-next-line @next/next/no-img-element
          <img
            key={index}
            src={tile.src}
            alt=""
            loading="lazy"
            className={`h-full w-full object-cover ${tile.span2 ? "col-span-2" : ""} ${tile.rowSpan2 ? "row-span-2" : ""}`}
          />
        ))}
      </div>
      <span className="absolute bottom-7 left-[clamp(20px,4vw,44px)] z-[4] rounded-pill bg-night/80 px-3.5 py-2 font-mono text-[11.5px] uppercase tracking-[0.14em] backdrop-blur-sm">
        {tag}
      </span>
    </div>
  );
}
