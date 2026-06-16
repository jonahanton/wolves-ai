import type { ApiError } from "@/lib/api";

const MESSAGES: Record<ApiError["category"], string> = {
  offline: "The forecast service is unreachable.",
  not_found: "Nothing published here yet.",
  forbidden: "Not authorised.",
  upstream: "The forecast service returned an error.",
};

interface ErrorStateProps {
  error: ApiError;
}

export function ErrorState({ error }: ErrorStateProps) {
  return (
    <section className="wrap py-24">
      <h1 className="statement">{MESSAGES[error.category]}</h1>
    </section>
  );
}
