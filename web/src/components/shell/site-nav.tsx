import { ShieldHalf } from "lucide-react";
import Link from "next/link";

export function SiteNav() {
  return (
    <header className="sticky top-0 z-20 flex h-10 items-center bg-night/30 backdrop-blur-md">
      <div className="wrap flex w-full items-center justify-between">
        <Link
          href="/"
          className="font-display text-[15px] font-semibold tracking-[-0.01em] text-cream transition-colors hover:text-cream-dim"
        >
          WWC26 Superforecaster
        </Link>
        <Link
          href="/teams"
          aria-label="Teams"
          className="flex items-center gap-1.5 font-display text-[13px] font-semibold tracking-[-0.01em] text-cream-faint transition-colors hover:text-cream"
        >
          <ShieldHalf size={15} className="shrink-0" />
          <span className="hidden sm:inline">Teams</span>
        </Link>
      </div>
    </header>
  );
}
