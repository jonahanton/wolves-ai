import Link from "next/link";
import { orNull } from "@/lib/api";
import { loadLiveState } from "@/lib/live";
import { NavLinks } from "@/components/shell/nav-links";

export async function SiteNav() {
  const live = orNull(await loadLiveState());
  const inPlay = (live?.live_match_count ?? 0) > 0;

  return (
    <header className="sticky top-0 z-20 border-b border-hairline bg-night/82 backdrop-blur-md">
      <div className="wrap flex items-center justify-between gap-3 py-4">
        <Link href="/" className="whitespace-nowrap text-[16px] font-semibold tracking-tight sm:text-[17px]">
          The Wolves
        </Link>
        <NavLinks inPlay={inPlay} />
      </div>
    </header>
  );
}
