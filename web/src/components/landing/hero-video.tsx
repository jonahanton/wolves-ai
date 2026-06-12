export function HeroVideo() {
  return (
    <div aria-hidden className="pointer-events-none absolute inset-x-0 top-0 h-[min(70svh,660px)] overflow-hidden">
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
      <div className="absolute inset-0 bg-[linear-gradient(180deg,oklch(0.16_0.012_250/0.72),oklch(0.16_0.012_250/0.34)_38%,oklch(0.16_0.012_250/0.6)_62%,oklch(0.175_0.014_65)_96%)]" />
    </div>
  );
}
