import { WolfMascot } from "@/components/mascot/wolf-mascot";

export function DailyStory() {
  return (
    <section className="rounded-xl border border-dashed bg-card/50 p-4" aria-label="Daily story">
      <h2 className="text-xs font-semibold tracking-wide text-muted-foreground uppercase">Daily story</h2>
      <div className="mt-3 flex items-center gap-3">
        <WolfMascot mood="neutral" size={44} />
        <p className="text-sm text-muted-foreground">
          The agent&apos;s daily story lands here once the morning forecast run is live. Numbers first, narrative
          next.
        </p>
      </div>
    </section>
  );
}
