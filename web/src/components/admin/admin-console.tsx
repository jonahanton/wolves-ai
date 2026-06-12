"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import type { RunRecord } from "@/lib/runs";

interface ScheduleState {
  enabled: boolean;
  cron: string;
}

interface ActiveRun {
  taskArn: string;
  lastStatus: string;
  startedAt: string | null;
}

interface AdminConsoleProps {
  schedule: ScheduleState | null;
  active: ActiveRun[] | null;
  records: RunRecord[];
}

type RunMode = "daily" | "agent" | "live";

export function AdminConsole({ schedule, active, records }: AdminConsoleProps) {
  const router = useRouter();
  const [message, setMessage] = useState<string | null>(null);
  const [mode, setMode] = useState<RunMode>("daily");
  const [ceiling, setCeiling] = useState("");
  const [confirmStop, setConfirmStop] = useState<string | null>(null);

  const call = async (path: string, body?: unknown) => {
    setMessage(null);
    const response = await fetch(`/api/admin/${path}`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: body === undefined ? undefined : JSON.stringify(body),
    });
    const payload = (await response.json().catch(() => ({}))) as { error?: string };
    setMessage(response.ok ? "done" : (payload.error ?? `failed (${response.status})`));
    if (response.ok) router.refresh();
  };

  return (
    <div className="max-w-[760px] space-y-12">
      {message && <p className="font-mono text-[13px] text-gold">{message}</p>}

      <section>
        <SectionHead text="Active runs" />
        {active === null && <p className="font-mono text-[14px] text-cream-faint">task listing unavailable here</p>}
        {active?.length === 0 && <p className="font-mono text-[14px] text-cream-faint">nothing running</p>}
        {(active ?? []).map((run) => (
          <div key={run.taskArn} className="flex items-baseline justify-between gap-4 border-b border-hairline py-3">
            <span className="truncate font-mono text-[13px] text-cream-dim">
              {run.taskArn.split("/").pop()} · {run.lastStatus}
            </span>
            {confirmStop === run.taskArn ? (
              <span className="flex gap-3">
                <ActionButton label="confirm stop" tone="danger" onClick={() => call("stop", { taskArn: run.taskArn })} />
                <ActionButton label="keep" onClick={() => setConfirmStop(null)} />
              </span>
            ) : (
              <ActionButton label="stop" tone="danger" onClick={() => setConfirmStop(run.taskArn)} />
            )}
          </div>
        ))}
      </section>

      <section>
        <SectionHead text="Run now" />
        <div className="flex flex-wrap items-center gap-3">
          {(["daily", "agent", "live"] as const).map((option) => (
            <button
              key={option}
              type="button"
              onClick={() => setMode(option)}
              className={`rounded-pill border px-4 py-1.5 font-mono text-[12px] uppercase tracking-[0.1em] ${
                mode === option ? "border-gold text-gold" : "border-hairline text-cream-faint"
              }`}
            >
              {option}
            </button>
          ))}
          {mode === "agent" && (
            <input
              type="number"
              min="0.01"
              max="8"
              step="0.5"
              value={ceiling}
              onChange={(event) => setCeiling(event.target.value)}
              placeholder="ceiling $ (calendar if blank)"
              className="w-56 border border-hairline bg-night-2 px-3 py-1.5 font-mono text-[13px] text-cream outline-none focus:border-gold"
            />
          )}
          <ActionButton
            label="launch"
            onClick={() =>
              call("run-now", {
                mode,
                ...(mode === "agent" && ceiling ? { ceilingUsd: Number(ceiling) } : {}),
              })
            }
          />
        </div>
      </section>

      <section>
        <SectionHead text="Daily schedule" />
        {schedule ? (
          <div className="flex flex-wrap items-baseline justify-between gap-3">
            <span className="font-mono text-[14px] text-cream-dim">
              {schedule.enabled ? "enabled" : "disabled"} · {schedule.cron}
            </span>
            <ActionButton
              label={schedule.enabled ? "disable" : "enable"}
              onClick={() => call("schedule", { enabled: !schedule.enabled })}
            />
          </div>
        ) : (
          <p className="font-mono text-[14px] text-cream-faint">schedule unavailable here</p>
        )}
      </section>

      <section>
        <SectionHead text="Run history" />
        {records.length === 0 && <p className="font-mono text-[14px] text-cream-faint">no run records (local index empty)</p>}
        {records.slice(0, 12).map((record) => (
          <div
            key={record.runId}
            className="grid grid-cols-[1fr_auto_auto] items-baseline gap-x-4 border-b border-hairline py-2.5 font-mono text-[13px]"
          >
            <span className="truncate text-cream-dim">{record.runId}</span>
            <span className={record.status === "failed" ? "text-red" : "text-cream-faint"}>{record.status}</span>
            <span className="text-cream-dim">${record.cost.toFixed(2)}</span>
          </div>
        ))}
      </section>

      <button
        type="button"
        onClick={async () => {
          await fetch("/api/admin-session", { method: "DELETE" });
          router.refresh();
        }}
        className="font-mono text-[12px] uppercase tracking-[0.12em] text-cream-faint hover:text-cream-dim"
      >
        lock console
      </button>
    </div>
  );
}

function SectionHead({ text }: { text: string }) {
  return <div className="mb-3 font-mono text-[12px] uppercase tracking-[0.14em] text-gold">{text}</div>;
}

interface ActionButtonProps {
  label: string;
  onClick: () => void;
  tone?: "default" | "danger";
}

function ActionButton({ label, onClick, tone = "default" }: ActionButtonProps) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`rounded-pill border px-4 py-1.5 font-mono text-[12px] uppercase tracking-[0.1em] ${
        tone === "danger" ? "border-red/60 text-red hover:border-red" : "border-hairline text-cream-dim hover:border-gold hover:text-cream"
      }`}
    >
      {label}
    </button>
  );
}
