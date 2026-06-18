import { WolfIcon } from "@/components/shell/wolf-icon";

export function LiveDetailLoader() {
  return (
    <div
      className="flex h-[134px] flex-col items-center justify-center gap-2 text-cream-faint"
      role="status"
      aria-live="polite"
    >
      <WolfIcon size={26} className="text-cream-dim" headClassName="howl motion-reduce:animate-none" />
      <span className="font-display text-[12.5px] shimmer-cream">Reading the live picture</span>
    </div>
  );
}
