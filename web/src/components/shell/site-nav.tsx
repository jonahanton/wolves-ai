import { ShieldHalf, Ticket } from "lucide-react";
import Link from "next/link";
import { CrystalBallIcon } from "@/components/shell/crystal-ball-icon";
import { EtClock } from "@/components/shell/et-clock";

export function SiteNav() {
  return (
    <header className="sticky top-0 z-20 flex h-10 items-center bg-night/30 backdrop-blur-md">
      <div className="wrap flex w-full items-center justify-between">
        <div className="flex items-baseline gap-2.5">
          <Link
            href="/"
            className="whitespace-nowrap font-display text-[15px] font-semibold tracking-[-0.01em] text-cream transition-colors hover:text-cream-dim"
          >
            WWC26 Superforecaster
          </Link>
          <span className="hidden sm:flex">
            <EtClock />
          </span>
        </div>
        <nav className="flex items-center gap-5">
          <Link
            href="/forecast"
            aria-label="Forecasts"
            className="flex items-center gap-1.5 font-display text-[13px] font-semibold tracking-[-0.01em] text-cream-faint transition-colors hover:text-cream"
          >
            <CrystalBallIcon size={15} className="shrink-0" />
            <span className="hidden sm:inline">Forecasts</span>
          </Link>
          <Link
            href="/teams"
            aria-label="Teams"
            className="flex items-center gap-1.5 font-display text-[13px] font-semibold tracking-[-0.01em] text-cream-faint transition-colors hover:text-cream"
          >
            <ShieldHalf size={15} className="shrink-0" />
            <span className="hidden sm:inline">Teams</span>
          </Link>
          <Link
            href="/fixtures"
            aria-label="Fixtures"
            className="flex items-center gap-1.5 font-display text-[13px] font-semibold tracking-[-0.01em] text-cream-faint transition-colors hover:text-cream"
          >
            <Ticket size={15} className="shrink-0" />
            <span className="hidden sm:inline">Fixtures</span>
          </Link>
        </nav>
      </div>
    </header>
  );
}
