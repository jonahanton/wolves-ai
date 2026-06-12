import type { ApiError } from "@/lib/api";

const MESSAGES: Record<ApiError["category"], string> = {
  offline: "The forecast service is unreachable.",
  not_found: "Nothing published here yet.",
  forbidden: "Not authorised.",
  upstream: "The forecast service returned an error.",
};

interface ErrorStateProps {
  error: ApiError;
  context?: string;
}

export function ErrorState({ error, context }: ErrorStateProps) {
  return (
    <section className="wrap py-24">
      <div className="kicker mb-[18px]">{context ?? "The Wolves"}</div>
      <h1 className="statement">{MESSAGES[error.category]}</h1>
      <p className="lede mt-[18px]">
        Every number on this site traces to a published run. Until one is reachable, there is nothing honest to show.
      </p>
    </section>
  );
}
