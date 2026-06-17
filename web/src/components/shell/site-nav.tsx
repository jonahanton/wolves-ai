"use client";

import { ShieldHalf, Ticket } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { CrystalBallIcon } from "@/components/shell/crystal-ball-icon";
import { EtClock } from "@/components/shell/et-clock";
import { NavLink } from "@/components/shell/nav-link";

const TABS = [
  { href: "/forecast", label: "Forecasts", Icon: CrystalBallIcon },
  { href: "/teams", label: "Teams", Icon: ShieldHalf },
  { href: "/fixtures", label: "Fixtures", Icon: Ticket },
];

export function SiteNav() {
  const pathname = usePathname();
  return (
    <header className="sticky top-0 z-20 flex min-h-11 items-center bg-night/90 py-1 sm:py-0">
      <div className="wrap flex w-full items-center justify-between">
        <div className="flex items-baseline gap-2.5">
          <Link
            href="/"
            className="whitespace-nowrap font-display text-[14px] font-semibold tracking-[-0.01em] text-cream transition-colors hover:text-cream-dim sm:text-[16px]"
          >
            WWC26 Superforecaster
          </Link>
          <span className="hidden sm:flex">
            <EtClock />
          </span>
        </div>
        <nav className="flex items-center gap-3.5 sm:gap-5">
          {TABS.map(({ href, label, Icon }) => {
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
        </nav>
      </div>
    </header>
  );
}
