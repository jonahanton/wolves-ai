import Link from "next/link";
import { ErrorState } from "@/components/shell/error-state";
import { Kicker } from "@/components/shell/kicker";
import { formatPct1 } from "@/lib/format";
import { loadLatestSnapshot } from "@/lib/load-snapshot";

interface TeamsPageProps {
  searchParams: Promise<{ group?: string }>;
}

export default async function TeamsPage({ searchParams }: TeamsPageProps) {
  const [result, params] = await Promise.all([loadLatestSnapshot(), searchParams]);
  if (!result.ok) return <ErrorState error={result.error} context="Teams" />;
  const snapshot = result.data;
  const focusId = snapshot.focus.team_id;

  const groups = [...new Set(snapshot.teams.map((t) => t.group))].sort();
  const selected = params.group?.toUpperCase();
  const teams = snapshot.teams
    .filter((t) => !selected || t.group === selected)
    .sort((a, b) => (b.champion_prob ?? 0) - (a.champion_prob ?? 0));
  const barMax = Math.max(0.02, ...teams.map((t) => t.champion_prob ?? 0)) * 1.1;

  return (
    <section className="wrap py-16">
      <Kicker>The field · run {snapshot.run.run_id}</Kicker>
      <h1 className="statement">
        Forty-eight teams.
        <br />
        <b className="font-medium">One trophy.</b>
      </h1>
      <nav className="mt-8 flex flex-wrap gap-x-4 gap-y-2 font-mono text-[12.5px] uppercase tracking-[0.12em]">
        <Link href="/teams" className={selected ? "text-cream-faint" : "text-gold"}>
          All
        </Link>
        {groups.map((group) => (
          <Link
            key={group}
            href={`/teams?group=${group}`}
            className={selected === group ? "text-gold" : "text-cream-faint hover:text-cream-dim"}
          >
            {group}
          </Link>
        ))}
      </nav>
      <div className="mt-8 max-w-[880px] border-t border-hairline">
        {teams.map((team, index) => (
          <Link
            key={team.team_id}
            href={`/teams/${team.team_id}`}
            className="grid grid-cols-[34px_1fr_auto_auto] items-baseline gap-x-[clamp(12px,2.6vw,26px)] border-b border-hairline py-3.5"
          >
            <span className="font-mono text-[13px] text-cream-faint">{String(index + 1).padStart(2, "0")}</span>
            <span className={`text-[clamp(17px,2.4vw,21px)] ${team.team_id === focusId ? "font-medium text-red" : ""}`}>
              {team.name}
            </span>
            <span className="font-mono text-[12px] uppercase text-cream-faint">{team.group}</span>
            <span className="font-mono text-[clamp(17px,2.4vw,21px)]">{formatPct1(team.champion_prob ?? 0)}</span>
            <span className="relative col-span-full mt-1.5 h-[2px] rounded-pill bg-hairline">
              <i
                className={`absolute inset-y-0 left-0 rounded-pill ${team.team_id === focusId ? "bg-red" : "bg-cream-dim"}`}
                style={{ width: `${Math.min(100, ((team.champion_prob ?? 0) / barMax) * 100).toFixed(1)}%` }}
              />
            </span>
          </Link>
        ))}
      </div>
    </section>
  );
}
