import type { RiverGeometry } from "@/lib/river";

interface RiverProps {
  geometry: RiverGeometry;
  id: string;
}

export function River({ geometry, id }: RiverProps) {
  const focus = geometry.bands.find((band) => band.glow);
  const rest = geometry.bands.filter((band) => !band.glow);

  return (
    <svg
      viewBox={`0 0 ${geometry.width} ${geometry.height}`}
      role="img"
      aria-label="Probability mass flowing through the knockout bracket"
      className="w-full"
    >
      <defs>
        <filter id={`${id}-glow`} x="-30%" y="-30%" width="160%" height="160%">
          <feGaussianBlur stdDeviation="7" />
        </filter>
      </defs>
      {geometry.stations.map((station, r) => (
        <g key={station.name}>
          <line
            x1={station.x}
            y1="38"
            x2={station.x}
            y2={geometry.height - 8}
            className="stroke-hairline"
            strokeWidth="1"
          />
          <text
            x={r === 5 ? station.x + 6 : station.x}
            y="16"
            textAnchor={r === 5 ? "end" : r === 0 ? "start" : "middle"}
            className={`font-mono ${r === 5 ? "fill-gold text-[13px]" : "fill-cream-dim text-[13px]"} uppercase tracking-[0.12em]`}
          >
            {station.name}
          </text>
          <text
            x={r === 5 ? station.x + 6 : station.x}
            y="32"
            textAnchor={r === 5 ? "end" : r === 0 ? "start" : "middle"}
            className="fill-cream-faint font-mono text-[11px]"
          >
            {station.dates}
          </text>
        </g>
      ))}
      {rest
        .filter((band) => band.teamId === null)
        .map((band) => (
          <path key="field" d={band.path} fill={band.fill} stroke={band.bank} strokeWidth="1" />
        ))}
      {rest
        .filter((band) => band.teamId !== null)
        .map((band) => (
          <g key={band.teamId}>
            <path d={band.path} fill={band.fill} />
            <path d={band.corePath} fill={band.core} />
            <path d={band.bankPath} fill="none" stroke={band.bank} strokeWidth="1" />
          </g>
        ))}
      {focus && (
        <g>
          <path d={focus.path} fill="oklch(0.69 0.19 25 / 0.5)" filter={`url(#${id}-glow)`} />
          <path d={focus.path} fill={focus.fill} />
          <path d={focus.corePath} fill={focus.core} />
          <path d={focus.bankPath} fill="none" stroke={focus.bank} strokeWidth="1" />
        </g>
      )}
      {geometry.bands.map((band) => (
        <text
          key={`label-${band.teamId ?? "field"}`}
          x="128"
          y={band.labelY}
          textAnchor="end"
          className={`font-mono text-[14px] ${
            band.glow ? "fill-red font-medium" : band.teamId === null ? "fill-cream-faint" : "fill-cream-dim"
          }`}
        >
          {band.name}
        </text>
      ))}
      {geometry.focusRoad.map((road) => (
        <text key={road.x} x={road.x} y={road.y} textAnchor="middle" className="fill-red font-mono text-[12.5px]">
          {road.label}
        </text>
      ))}
    </svg>
  );
}
