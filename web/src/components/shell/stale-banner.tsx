export function StaleBanner() {
  return (
    <div
      role="status"
      className="wrap flex items-center gap-2 py-1.5 font-display text-[12px] text-cream-faint"
    >
      <span className="inline-block size-1.5 shrink-0 rounded-full bg-gold/80" />
      Reconnecting. Showing the last published forecast.
    </div>
  );
}
