import { type BoardRow, titleBoard } from "@/lib/derive";
import type { RunRecord } from "@/lib/runs";
import type { AgentBlock, MarketsBlock, MatchProbs, Snapshot } from "@/lib/snapshot";

const STAGE_ORDER = ["group", "r32", "r16", "qf", "sf", "third_place", "final"] as const;
const STAGE_LABEL: Record<string, string> = {
  group: "Groups",
  r32: "Round of 32",
  r16: "Round of 16",
  qf: "Quarter-finals",
  sf: "Semi-finals",
  third_place: "Third-place play-off",
  final: "Final",
};

// Played matches carry no date in the snapshot, so only the stage is derivable, not a calendar day.
export function tournamentPhase(runIso: string, matches: MatchProbs[], playedStages: string[]): string | null {
  const runTs = Date.parse(runIso);
  const seen = new Set<string>(playedStages);
  for (const m of matches) {
    if (Date.parse(m.date) <= runTs) seen.add(m.stage);
  }
  let stage: string | null = null;
  for (const key of STAGE_ORDER) {
    if (seen.has(key)) stage = key;
  }
  return stage ? (STAGE_LABEL[stage] ?? null) : null;
}

export interface ForecastIndexRow {
  runId: string;
  createdAt: string;
  cost: number | null;
  top: BoardRow[];
  totalTeams: number;
}

export function forecastIndexRows(
  snapshots: Snapshot[],
  records: RunRecord[] | null,
  topN = 4,
): ForecastIndexRow[] {
  const costByRun = new Map<string, number>();
  for (const r of records ?? []) if (r.cost > 0) costByRun.set(r.runId, r.cost);
  return snapshots
    .map((s) => ({
      runId: s.run.run_id,
      createdAt: s.run.created_at,
      cost: costByRun.get(s.run.run_id) ?? null,
      top: titleBoard(s, topN),
      totalTeams: s.teams.filter((t) => t.champion_prob !== undefined).length,
    }))
    .sort((a, b) => Date.parse(b.createdAt) - Date.parse(a.createdAt));
}

export interface Mover {
  teamId: string;
  name: string;
  direction: "up" | "down";
  ourProb: number | null;
  marketProb: number | null;
  gapPp: number | null;
  summary: string;
  why: string;
}

export function featuredMovers(
  agent: AgentBlock,
  markets: MarketsBlock | null | undefined,
  publishedProbs: Record<string, number>,
  names: Record<string, string>,
): Mover[] {
  const stories = agent.narrative.team_stories ?? {};
  const market = markets?.market_probs ?? {};
  const seen = new Set<string>();
  const movers: Mover[] = [];
  for (const entry of agent.escalations ?? []) {
    const match = entry.trim().match(/^(\S+)\s+([+-])/);
    if (!match) continue;
    const teamId = match[1];
    const story = stories[teamId];
    if (!story || seen.has(teamId)) continue;
    seen.add(teamId);
    const ourProb = publishedProbs[teamId] ?? null;
    const marketProb = market[teamId] ?? null;
    const gapPp = ourProb !== null && marketProb !== null ? (ourProb - marketProb) * 100 : null;
    const direction = gapPp !== null ? (gapPp >= 0 ? "up" : "down") : match[2] === "-" ? "down" : "up";
    movers.push({
      teamId,
      name: names[teamId] ?? teamId,
      direction,
      ourProb,
      marketProb,
      gapPp,
      summary: stripIds(story.summary),
      why: stripIds(story.why),
    });
  }
  return movers;
}

export interface ReadingItem {
  title: string;
  hostname: string;
  url: string;
  tier: number | null;
  cited: boolean;
}

export function readingList(agent: AgentBlock): ReadingItem[] {
  const ranked = (agent.sources ?? []).slice().sort((a, b) => {
    const ac = a.cited ?? false;
    const bc = b.cited ?? false;
    if (ac !== bc) return ac ? -1 : 1;
    const ar = a.ranked ?? false;
    const br = b.ranked ?? false;
    if (ar !== br) return ar ? -1 : 1;
    return (a.tier ?? 99) - (b.tier ?? 99);
  });
  const byUrl = new Map<string, ReadingItem>();
  for (const s of ranked) {
    if (!s.url || byUrl.has(s.url) || s.url.startsWith("internal://")) continue;
    byUrl.set(s.url, {
      title: s.title ?? s.hostname ?? s.url,
      hostname: (s.hostname ?? "").replace(/^www\./, ""),
      url: s.url,
      tier: s.tier ?? null,
      cited: s.cited ?? false,
    });
  }
  return [...byUrl.values()];
}

function formatDuration(seconds: number): string {
  if (seconds < 60) return `${Math.round(seconds)}s runtime`;
  const m = Math.floor(seconds / 60);
  const s = Math.round(seconds % 60);
  return s === 0 ? `${m}m runtime` : `${m}m ${s}s runtime`;
}

export function runMeta(durationS: number | null, cost: number | null): string[] {
  const out: string[] = [];
  if (durationS && durationS > 0) out.push(formatDuration(durationS));
  if (cost && cost > 0) out.push(`$${cost.toFixed(2)}`);
  return out;
}

export interface Working {
  title: string;
  summary: string;
  findings: string[];
}

const WORKING_TITLES: Record<string, string> = {
  "quant-sim-anchor": "Audit against our own ratings",
  "quant-market-anchor": "Audit against the betting market",
  "quant-mixture": "Combining the competing worlds",
  "quant-reprice": "Re-pricing after challenge",
};

// Upstream findings are sometimes hard-truncated mid-sentence; flag those with an ellipsis.
function markIfClipped(text: string): string {
  const trimmed = text.trim();
  if (trimmed.length === 0 || /[.!?][")\]%]?$/.test(trimmed) || trimmed.endsWith("…")) return trimmed;
  return `${trimmed.replace(/[,;:]?$/, "")}…`;
}

export function cleanWorkings(agent: AgentBlock): Working[] {
  return (agent.quant_findings ?? []).map((q, i) => ({
    title: WORKING_TITLES[q.node_id] ?? `Step ${i + 1}`,
    summary: markIfClipped(stripIds(q.summary)),
    findings: q.findings.map((f) => markIfClipped(stripIds(f))),
  }));
}

export function stripIds(text: string): string {
  return text
    .replace(/\b(quant-[\w-]+|mixture-\d+|led-\d+|scn-\d+)\b/g, "")
    .replace(/\b\w+_(camp|collapse|base|world)\b/g, "this scenario")
    .replace(/\s{2,}/g, " ")
    .trim();
}
