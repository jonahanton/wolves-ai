import type { ReactNode } from "react";

interface HeroVideoProps {
  children: ReactNode;
}

export function HeroVideo({ children }: HeroVideoProps) {
  return (
    <section className="relative isolate overflow-hidden">
      <div aria-hidden className="pointer-events-none absolute inset-0 -z-10">
        <video
          muted
          loop
          autoPlay
          playsInline
          preload="metadata"
          poster="/hero-poster.jpg"
          className="h-full w-full object-cover object-[50%_30%] motion-reduce:hidden"
        >
          <source src="/hero.mp4" type="video/mp4" />
        </video>
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img src="/hero-poster.jpg" alt="" className="hidden h-full w-full object-cover object-[50%_30%] motion-reduce:block" />
        <div className="absolute inset-0 bg-[radial-gradient(105%_85%_at_50%_42%,oklch(0.215_0.022_255)_40%,oklch(0.215_0.022_255/0.84)_64%,oklch(0.215_0.022_255/0.55)_84%,oklch(0.215_0.022_255/0.32)_100%)]" />
      </div>
      <div className="pt-[clamp(20px,3vh,40px)] pb-[clamp(24px,4vh,52px)]">{children}</div>
    </section>
  );
}
