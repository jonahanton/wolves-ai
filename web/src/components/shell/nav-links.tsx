"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const LINKS = [
  { href: "/teams", label: "Teams" },
  { href: "/bracket", label: "Bracket" },
  { href: "/market", label: "Market" },
  { href: "/runs", label: "Runs" },
] as const;

interface NavLinksProps {
  inPlay: boolean;
}

export function NavLinks({ inPlay }: NavLinksProps) {
  const pathname = usePathname();
  const active = (href: string) => pathname === href || pathname.startsWith(`${href}/`);

  return (
    <nav className="flex items-center gap-3 font-mono text-[10.5px] uppercase tracking-[0.12em] text-cream-dim sm:gap-6 sm:text-[12.5px] sm:tracking-[0.14em]">
      {LINKS.map((link) => (
        <Link
          key={link.href}
          href={link.href}
          aria-current={active(link.href) ? "page" : undefined}
          className={`transition-colors hover:text-cream ${active(link.href) ? "text-gold" : ""}`}
        >
          {link.label}
        </Link>
      ))}
      <Link href="/live" aria-current={active("/live") ? "page" : undefined} className={`flex items-center gap-2 ${active("/live") ? "text-gold" : "text-cream"}`}>
        {inPlay && <i className="h-[7px] w-[7px] animate-pulse rounded-pill bg-red motion-reduce:animate-none" aria-hidden />}
        Live
      </Link>
    </nav>
  );
}
