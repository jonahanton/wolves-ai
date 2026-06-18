"use client";

import { useRouter } from "next/navigation";
import { useTransition } from "react";

interface RetryButtonProps {
  onRetry?: () => void;
}

export function RetryButton({ onRetry }: RetryButtonProps) {
  const router = useRouter();
  const [pending, startTransition] = useTransition();
  return (
    <button
      type="button"
      onClick={() => startTransition(() => (onRetry ? onRetry() : router.refresh()))}
      disabled={pending}
      className="rounded-full border border-hairline/70 px-4 py-1.5 font-display text-[13px] font-semibold text-cream-dim transition-colors hover:border-cream/50 hover:text-cream disabled:opacity-60"
    >
      {pending ? "Retrying..." : "Try again"}
    </button>
  );
}
