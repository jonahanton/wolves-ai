// A text-free atmospheric masthead. Copy never sits on it; the gradient hands
// off to solid night below so the title and graph read on a clean canvas.
export function HeroVideo() {
  return (
    <div aria-hidden className="pointer-events-none relative h-[clamp(112px,18svh,200px)] overflow-hidden">
      <video
        muted
        loop
        autoPlay
        playsInline
        preload="metadata"
        poster="/hero-poster.jpg"
        className="h-full w-full object-cover object-[50%_38%] motion-reduce:hidden"
      >
        <source src="/hero.mp4" type="video/mp4" />
      </video>
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img src="/hero-poster.jpg" alt="" className="hidden h-full w-full object-cover object-[50%_38%] motion-reduce:block" />
      <div className="absolute inset-0 bg-[linear-gradient(180deg,oklch(0.175_0.014_65/0.34),oklch(0.175_0.014_65/0.52)_52%,oklch(0.175_0.014_65/0.9)_86%,oklch(0.175_0.014_65)_100%)]" />
    </div>
  );
}
