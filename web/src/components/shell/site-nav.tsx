"use client";

import { ShieldHalf, Ticket } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { GithubLink } from "@/components/shell/github-link";
import { NavLink } from "@/components/shell/nav-link";
import { WolfIcon } from "@/components/shell/wolf-icon";

const TABS = [
  { section: "forecast", label: "Forecasts", Icon: WolfIcon },
  { section: "teams", label: "Teams", Icon: ShieldHalf },
  { section: "fixtures", label: "Fixtures", Icon: Ticket },
];

function archiveBase(pathname: string): string | null {
  const match = /^\/archive\/(\d{4}-\d{2}-\d{2})/.exec(pathname);
  return match ? `/archive/${match[1]}` : null;
}

export function SiteNav() {
  const pathname = usePathname();
  const base = archiveBase(pathname);
  return (
    <header className="flex min-h-11 items-center py-1 sm:py-0">
      <div className="wrap flex w-full items-center justify-between">
        <div className="flex items-baseline">
          <Link
            href={base ?? "/"}
            className="whitespace-nowrap font-display text-[17px] font-semibold tracking-[-0.01em] text-cream transition-colors hover:text-cream-dim sm:text-[16px]"
          >
            WWC26<span className="hidden sm:inline"> Superforecaster</span>
          </Link>
        </div>
        <nav className="flex items-center gap-3.5 sm:gap-5">
          {TABS.map(({ section, label, Icon }) => {
            const href = base ? `${base}/${section}` : `/${section}`;
            const active = pathname === href || pathname.startsWith(`${href}/`);
            return (
              <Link
                key={href}
                href={href}
                aria-label={label}
                aria-current={active ? "page" : undefined}
                className={`font-display font-semibold tracking-[-0.01em] transition-colors ${
                  active ? "text-cream" : "text-cream-faint hover:text-cream"
                }`}
              >
                <NavLink active={active}>
                  <Icon size={16} className="shrink-0" />
                  <span className="text-[10px] sm:text-[14px]">{label}</span>
                </NavLink>
              </Link>
            );
          })}
          <span aria-hidden className="mt-1 h-4 w-px self-start bg-hairline sm:mt-0 sm:h-3.5 sm:self-center" />
          <GithubLink />
        </nav>
      </div>
    </header>
  );
}
