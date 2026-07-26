import type { KnockoutSlot } from "@/lib/fixtures";
import { formatPctBare } from "@/lib/format";

interface CandidateListProps {
  label: string;
  candidates: KnockoutSlot["home"]["candidates"];
}

function CandidateList({ label, candidates }: CandidateListProps) {
  return (
    <div className="grid grid-cols-[3rem_repeat(3,minmax(0,1fr))] items-baseline gap-x-2 sm:gap-x-3">
      <span className="truncate font-mono text-[13px] text-cream-faint">{label}</span>
      {candidates.map((candidate) => (
        <span key={candidate.teamId} className="truncate font-display text-[14.5px]">
          <span className="font-semibold text-cream">{candidate.code}</span>
          <span className="ml-1.5 font-mono text-[12.5px] tabular-nums text-cream-faint">
            {formatPctBare(candidate.prob)}%
          </span>
        </span>
      ))}
    </div>
  );
}

interface FixtureSlotDetailProps {
  slot: KnockoutSlot;
}

export function FixtureSlotDetail({ slot }: FixtureSlotDetailProps) {
  return (
    <div className="space-y-2">
      <CandidateList label={slot.home.label} candidates={slot.home.candidates} />
      <CandidateList label={slot.away.label} candidates={slot.away.candidates} />
    </div>
  );
}
