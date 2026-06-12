import Link from "next/link";
import { orNull } from "@/lib/api";
import { loadLiveState } from "@/lib/live";

const LINKS = [
  { href: "/teams", label: "Teams" },
  { href: "/bracket", label: "Bracket" },
  { href: "/market", label: "Market" },
  { href: "/runs", label: "Runs" },
] as const;

export async function SiteNav() {
  const live = orNull(await loadLiveState());
  const inPlay = (live?.live_match_count ?? 0) > 0;

  return (
    <header className="sticky top-0 z-20 border-b border-hairline bg-night/82 backdrop-blur-md">
      <div className="wrap flex items-center justify-between gap-3 py-4">
        <Link href="/" className="whitespace-nowrap text-[16px] font-semibold tracking-tight sm:text-[17px]">
          The Wolves
        </Link>
        <nav className="flex items-center gap-3 font-mono text-[10.5px] uppercase tracking-[0.12em] text-cream-dim sm:gap-6 sm:text-[12.5px] sm:tracking-[0.14em]">
          {LINKS.map((link) => (
            <Link key={link.href} href={link.href} className="transition-colors hover:text-cream">
              {link.label}
            </Link>
          ))}
          <Link href="/live" className="flex items-center gap-2 text-cream">
            {inPlay && <i className="h-[7px] w-[7px] animate-pulse rounded-pill bg-red" aria-hidden />}
            Live
          </Link>
        </nav>
      </div>
    </header>
  );
}
