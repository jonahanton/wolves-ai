export function StaleBanner() {
  return (
    <div
      role="status"
      className="wrap flex items-center py-1.5 font-display text-[12px] text-cream-faint"
    >
      Reconnecting. Showing the last published forecast.
    </div>
  );
}
