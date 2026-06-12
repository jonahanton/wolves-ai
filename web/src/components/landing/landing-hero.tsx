"use client";

import { LiveHero } from "@/components/live/live-hero";
import { useLiveState } from "@/hooks/use-live-state";
import { featuredLiveFixture, isStale, type LiveState } from "@/lib/live";

interface LandingHeroProps {
  initialLive: LiveState | null;
  focusId: string;
  names: Record<string, string>;
  restHero: React.ReactNode;
}

export function LandingHero({ initialLive, focusId, names, restHero }: LandingHeroProps) {
  const live = useLiveState(initialLive);
  const fixture = live && !isStale(live) ? featuredLiveFixture(live, focusId) : null;
  if (!live || !fixture) return <>{restHero}</>;
  return <LiveHero state={live} fixture={fixture} focusId={focusId} names={names} />;
}
