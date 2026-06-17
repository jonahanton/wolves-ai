"use client";

import { useLinkStatus } from "next/link";

interface NavLinkProps {
  active: boolean;
  children: React.ReactNode;
}

export function NavLink({ active, children }: NavLinkProps) {
  const { pending } = useLinkStatus();
  return (
    <span className="relative flex flex-col items-center gap-0.5 py-1 sm:flex-row sm:gap-1.5">
      {children}
      <span
        aria-hidden
        className={`absolute -bottom-px left-0 h-px w-full origin-left rounded-full bg-cream transition-[opacity,transform] duration-200 ${
          active ? "opacity-100" : "opacity-0"
        } ${pending ? "animate-pulse opacity-100" : ""}`}
      />
    </span>
  );
}
