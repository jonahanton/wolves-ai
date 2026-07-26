import { RetryButton } from "@/components/shell/retry-button";

interface ErrorStateProps {
  error: "missing" | "corrupt" | "unexpected";
  onRetry?: () => void;
}

export function ErrorState({ error, onRetry }: ErrorStateProps) {
  const message = error === "missing" ? "Nothing published here yet." : "The archive could not be read.";
  return (
    <section className="wrap py-24">
      <h1 className="statement">{message}</h1>
      {error !== "missing" && (
        <div className="mt-6">
          <RetryButton onRetry={onRetry} />
        </div>
      )}
    </section>
  );
}
