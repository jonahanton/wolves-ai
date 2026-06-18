import Image from "next/image";
import { type WallFamily, wallTiles } from "@/lib/walls";

interface FestivalBandProps {
  family: WallFamily;
  tag: string;
}

// Span-2 tiles cover two columns, so size for the wide case to avoid upscaling.
const TILE_SIZES = "(min-width: 1024px) 17vw, (min-width: 640px) 23vw, 40vw";

export function FestivalBand({ family, tag }: FestivalBandProps) {
  return (
    <div className="relative overflow-hidden border-t border-hairline">
      <div className="grid grid-flow-dense auto-rows-[clamp(56px,8vw,96px)] grid-cols-5 sm:grid-cols-9 lg:grid-cols-12">
        {wallTiles(family, 36).map((tile, index) => (
          <div
            key={index}
            className={`relative ${tile.span2 ? "col-span-2" : ""} ${tile.rowSpan2 ? "row-span-2" : ""}`}
          >
            <Image src={tile.src} alt="" fill sizes={TILE_SIZES} quality={75} className="object-cover" />
          </div>
        ))}
      </div>
      <span className="absolute bottom-7 left-[clamp(20px,4vw,44px)] z-[4] rounded-pill bg-night/80 px-3.5 py-2 font-mono text-[11.5px] uppercase tracking-[0.14em] backdrop-blur-sm">
        {tag}
      </span>
    </div>
  );
}
