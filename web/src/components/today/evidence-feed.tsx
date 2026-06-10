import type { LedgerEntryOut } from "@/lib/snapshot";

const STATUS_STYLES: Record<string, string> = {
  confirmed: "bg-[var(--state-complete-bg)] text-[var(--state-complete)]",
  probable: "bg-[var(--state-working-bg)] text-[var(--state-working)]",
  rumour: "bg-secondary text-muted-foreground",
};

function sourceHost(url: string): string | null {
  try {
    return new URL(url).hostname.replace(/^www\./, "");
  } catch {
    return null;
  }
}

interface EvidenceFeedProps {
  entries: LedgerEntryOut[];
}

export function EvidenceFeed({ entries }: EvidenceFeedProps) {
  if (entries.length === 0) return null;

  return (
    <section aria-label="Evidence feed">
      <h2 className="mb-2 text-xs font-semibold tracking-wide text-muted-foreground uppercase">
        What the agent is reading
      </h2>
      <div className="divide-y rounded-xl border bg-card">
        {entries.map((entry) => {
          const host = sourceHost(entry.source_url);
          return (
            <article key={entry.id} className="px-3.5 py-2.5">
              <p className="text-sm">{entry.claim}</p>
              <p className="mt-1 flex items-center gap-2 text-xs text-muted-foreground">
                <span
                  className={`rounded-full px-1.5 py-0.5 text-[10px] font-medium capitalize ${
                    STATUS_STYLES[entry.status] ?? STATUS_STYLES.rumour
                  }`}
                >
                  {entry.status}
                </span>
                {host && (
                  <a
                    href={entry.source_url}
                    target="_blank"
                    rel="noreferrer"
                    className="underline underline-offset-2 hover:text-foreground"
                  >
                    {host}
                  </a>
                )}
              </p>
            </article>
          );
        })}
      </div>
    </section>
  );
}
