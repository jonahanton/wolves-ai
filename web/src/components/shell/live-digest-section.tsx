import { LiveDigest } from "@/components/shell/live-digest";
import { orNull } from "@/lib/api";
import { loadAgentImpact } from "@/lib/impact";
import { loadLiveState } from "@/lib/live";

export async function LiveDigestSection() {
  const [live, impact] = await Promise.all([loadLiveState(), loadAgentImpact()]);
  return <LiveDigest initialLive={orNull(live)} initialImpact={orNull(impact)} />;
}
