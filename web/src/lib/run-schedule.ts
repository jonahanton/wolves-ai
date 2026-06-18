interface AgentRunWindow {
  utcHour: number;
  utcMinute: number;
  // Exclusive upper bound; null is open-ended.
  untilIso: string | null;
}

// Mirrors agent_schedule_windows in infra/envs/prod/variables.tf, pinned by a parity test.
export const AGENT_RUN_WINDOWS: AgentRunWindow[] = [
  { utcHour: 6, utcMinute: 30, untilIso: "2026-06-24T00:00:00Z" },
  { utcHour: 10, utcMinute: 0, untilIso: "2026-07-14T00:00:00Z" },
  { utcHour: 6, utcMinute: 30, untilIso: null },
];

function windowFor(instant: Date): AgentRunWindow {
  for (const window of AGENT_RUN_WINDOWS) {
    if (window.untilIso === null || instant < new Date(window.untilIso)) return window;
  }
  return AGENT_RUN_WINDOWS[AGENT_RUN_WINDOWS.length - 1];
}

export function nextAgentRunIso(now: Date): string {
  const day = new Date(now);
  for (let i = 0; i < 3; i += 1) {
    const window = windowFor(day);
    const run = new Date(day);
    run.setUTCHours(window.utcHour, window.utcMinute, 0, 0);
    if (run > now) return run.toISOString();
    day.setUTCDate(day.getUTCDate() + 1);
  }
  return day.toISOString();
}
