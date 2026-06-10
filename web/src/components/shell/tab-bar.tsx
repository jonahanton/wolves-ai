"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Ellipsis, GitMerge, Radio, Route, Sunrise } from "lucide-react";
import { cn } from "@/lib/utils";

const TABS = [
  { href: "/", label: "Today", icon: Sunrise },
  { href: "/path", label: "Path", icon: Route },
  { href: "/bracket", label: "Bracket", icon: GitMerge },
  { href: "/live", label: "Live", icon: Radio },
  { href: "/more", label: "More", icon: Ellipsis },
] as const;

export function TabBar() {
  const pathname = usePathname();
  return (
    <nav
      className={cn(
        "fixed inset-x-0 bottom-0 z-40 border-t bg-background",
        "pb-[max(env(safe-area-inset-bottom),0.5rem)]",
      )}
    >
      <div className="mx-auto flex max-w-md">
        {TABS.map(({ href, label, icon: Icon }) => {
          const active = pathname === href;
          return (
            <Link
              key={href}
              href={href}
              aria-current={active ? "page" : undefined}
              className={cn(
                "flex flex-1 flex-col items-center gap-0.5 pt-2 pb-1 text-[11px] font-medium",
                "transition-colors duration-150",
                active ? "text-gold" : "text-muted-foreground hover:text-foreground",
              )}
            >
              <Icon size={20} strokeWidth={active ? 2.4 : 2} />
              {label}
            </Link>
          );
        })}
      </div>
    </nav>
  );
}
