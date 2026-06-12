export function HeroVideo() {
  return (
    <div aria-hidden className="pointer-events-none absolute inset-x-0 top-0 h-[min(30svh,300px)] overflow-hidden">
      <video
        muted
        loop
        autoPlay
        playsInline
        preload="metadata"
        poster="/hero-poster.jpg"
        className="h-full w-full object-cover motion-reduce:hidden"
      >
        <source src="/hero.mp4" type="video/mp4" />
      </video>
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img
        src="/hero-poster.jpg"
        alt=""
        className="hidden h-full w-full object-cover motion-reduce:block"
      />
      <div className="absolute inset-0 bg-[linear-gradient(180deg,oklch(0.16_0.012_250/0.85),oklch(0.16_0.012_250/0.55)_38%,oklch(0.16_0.012_250/0.72)_62%,oklch(0.175_0.014_65)_96%)]" />
      <div className="absolute inset-0 bg-[linear-gradient(100deg,oklch(0.175_0.014_65/0.75),transparent_55%)]" />
    </div>
  );
}
