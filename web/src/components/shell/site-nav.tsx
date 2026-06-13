import Link from "next/link";

export function SiteNav() {
  return (
    <header className="sticky top-0 z-20 flex h-10 items-center bg-night/30 backdrop-blur-md">
      <div className="wrap flex w-full items-center">
        <Link
          href="/"
          className="font-display text-[15px] font-semibold tracking-[-0.01em] text-cream transition-colors hover:text-cream-dim"
        >
          WWC26 Superforecaster
        </Link>
      </div>
    </header>
  );
}
