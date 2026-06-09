import { Mountain, Thermometer, Umbrella } from "lucide-react";
import type { VenueTraits } from "@/lib/venues";

interface VenueChipsProps {
  traits: VenueTraits;
}

export function VenueChips({ traits }: VenueChipsProps) {
  const chips = [
    traits.roof && { icon: Umbrella, label: "Roof" },
    traits.heat && { icon: Thermometer, label: "Hot" },
    traits.altitude && { icon: Mountain, label: "Altitude" },
  ].filter((c): c is { icon: typeof Umbrella; label: string } => Boolean(c));

  if (chips.length === 0) return null;
  return (
    <span className="inline-flex gap-1.5">
      {chips.map(({ icon: Icon, label }) => (
        <span
          key={label}
          className="inline-flex items-center gap-0.5 rounded-full bg-secondary px-1.5 py-0.5 text-[10px] text-muted-foreground"
        >
          <Icon size={11} />
          {label}
        </span>
      ))}
    </span>
  );
}
