import { RetryButton } from "@/components/shell/retry-button";
import type { ApiError } from "@/lib/api";

const MESSAGES: Record<ApiError["category"], string> = {
  offline: "We could not reach the forecast just now.",
  not_found: "Nothing published here yet.",
  forbidden: "Not authorised.",
  upstream: "The forecast is taking a moment to come back.",
};

const TRANSIENT: ReadonlySet<ApiError["category"]> = new Set(["offline", "upstream"]);

interface ErrorStateProps {
  error: ApiError;
  onRetry?: () => void;
}

export function ErrorState({ error, onRetry }: ErrorStateProps) {
  return (
    <section className="wrap py-24">
      <h1 className="statement">{MESSAGES[error.category]}</h1>
      {TRANSIENT.has(error.category) && (
        <div className="mt-6">
          <RetryButton onRetry={onRetry} />
        </div>
      )}
    </section>
  );
}
