"use client";

import { ErrorState } from "@/components/shell/error-state";

interface ErrorProps {
  reset: () => void;
}

export default function Error({ reset }: ErrorProps) {
  return <ErrorState error="unexpected" onRetry={reset} />;
}
