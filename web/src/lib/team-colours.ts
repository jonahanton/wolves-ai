export interface TeamColours {
  primary: string;
  secondary: string;
}

// Kit colours lifted into the 0.6-0.8 lightness band for the night background; England's primary is the site accent.
const TEAM_COLOURS: Record<string, TeamColours> = {
  algeria: { primary: "oklch(0.66 0.13 150)", secondary: "oklch(0.78 0.02 95)" },
  argentina: { primary: "oklch(0.78 0.09 230)", secondary: "oklch(0.8 0.13 88)" },
  australia: { primary: "oklch(0.8 0.15 90)", secondary: "oklch(0.62 0.12 150)" },
  austria: { primary: "oklch(0.64 0.2 27)", secondary: "oklch(0.78 0.02 95)" },
  belgium: { primary: "oklch(0.63 0.2 27)", secondary: "oklch(0.8 0.14 90)" },
  "bosnia-and-herzegovina": { primary: "oklch(0.62 0.12 260)", secondary: "oklch(0.8 0.14 90)" },
  brazil: { primary: "oklch(0.8 0.16 95)", secondary: "oklch(0.62 0.13 150)" },
  "cabo-verde": { primary: "oklch(0.62 0.13 255)", secondary: "oklch(0.65 0.18 25)" },
  canada: { primary: "oklch(0.66 0.2 25)", secondary: "oklch(0.78 0.02 95)" },
  colombia: { primary: "oklch(0.8 0.16 95)", secondary: "oklch(0.6 0.13 262)" },
  "congo-dr": { primary: "oklch(0.62 0.14 250)", secondary: "oklch(0.65 0.18 25)" },
  "cote-d-ivoire": { primary: "oklch(0.74 0.16 55)", secondary: "oklch(0.64 0.12 150)" },
  croatia: { primary: "oklch(0.64 0.19 25)", secondary: "oklch(0.62 0.12 260)" },
  curacao: { primary: "oklch(0.62 0.14 255)", secondary: "oklch(0.8 0.15 95)" },
  czechia: { primary: "oklch(0.65 0.18 25)", secondary: "oklch(0.65 0.12 255)" },
  ecuador: { primary: "oklch(0.8 0.16 95)", secondary: "oklch(0.6 0.13 262)" },
  egypt: { primary: "oklch(0.62 0.2 25)", secondary: "oklch(0.78 0.02 95)" },
  england: { primary: "oklch(0.69 0.19 25)", secondary: "oklch(0.78 0.02 95)" },
  france: { primary: "oklch(0.65 0.14 260)", secondary: "oklch(0.65 0.18 25)" },
  germany: { primary: "oklch(0.78 0.02 95)", secondary: "oklch(0.66 0.12 150)" },
  ghana: { primary: "oklch(0.78 0.02 95)", secondary: "oklch(0.78 0.14 88)" },
  haiti: { primary: "oklch(0.62 0.13 260)", secondary: "oklch(0.65 0.18 25)" },
  iraq: { primary: "oklch(0.63 0.13 150)", secondary: "oklch(0.78 0.02 95)" },
  "ir-iran": { primary: "oklch(0.78 0.02 95)", secondary: "oklch(0.65 0.18 25)" },
  japan: { primary: "oklch(0.6 0.13 265)", secondary: "oklch(0.78 0.02 95)" },
  jordan: { primary: "oklch(0.62 0.19 25)", secondary: "oklch(0.78 0.02 95)" },
  "korea-republic": { primary: "oklch(0.64 0.2 20)", secondary: "oklch(0.7 0.04 250)" },
  mexico: { primary: "oklch(0.65 0.14 150)", secondary: "oklch(0.65 0.18 25)" },
  morocco: { primary: "oklch(0.62 0.19 25)", secondary: "oklch(0.65 0.13 150)" },
  netherlands: { primary: "oklch(0.72 0.17 50)", secondary: "oklch(0.62 0.12 260)" },
  "new-zealand": { primary: "oklch(0.78 0.02 95)", secondary: "oklch(0.65 0.03 250)" },
  norway: { primary: "oklch(0.64 0.2 27)", secondary: "oklch(0.62 0.12 260)" },
  panama: { primary: "oklch(0.64 0.2 25)", secondary: "oklch(0.62 0.12 260)" },
  paraguay: { primary: "oklch(0.64 0.18 25)", secondary: "oklch(0.62 0.12 260)" },
  portugal: { primary: "oklch(0.61 0.2 25)", secondary: "oklch(0.64 0.13 150)" },
  qatar: { primary: "oklch(0.6 0.16 15)", secondary: "oklch(0.78 0.02 95)" },
  "saudi-arabia": { primary: "oklch(0.64 0.14 150)", secondary: "oklch(0.78 0.02 95)" },
  scotland: { primary: "oklch(0.62 0.12 265)", secondary: "oklch(0.78 0.02 95)" },
  senegal: { primary: "oklch(0.66 0.14 150)", secondary: "oklch(0.8 0.14 90)" },
  "south-africa": { primary: "oklch(0.8 0.14 95)", secondary: "oklch(0.62 0.13 150)" },
  spain: { primary: "oklch(0.63 0.21 27)", secondary: "oklch(0.78 0.13 85)" },
  sweden: { primary: "oklch(0.8 0.15 95)", secondary: "oklch(0.62 0.12 255)" },
  switzerland: { primary: "oklch(0.66 0.21 27)", secondary: "oklch(0.78 0.02 95)" },
  tunisia: { primary: "oklch(0.63 0.2 25)", secondary: "oklch(0.78 0.02 95)" },
  turkiye: { primary: "oklch(0.63 0.21 25)", secondary: "oklch(0.78 0.02 95)" },
  uruguay: { primary: "oklch(0.72 0.11 235)", secondary: "oklch(0.78 0.02 95)" },
  usa: { primary: "oklch(0.63 0.12 262)", secondary: "oklch(0.66 0.19 25)" },
  uzbekistan: { primary: "oklch(0.78 0.02 95)", secondary: "oklch(0.7 0.1 235)" },
};

const FALLBACK: TeamColours = { primary: "oklch(0.6 0.06 250)", secondary: "oklch(0.7 0.03 250)" };

export function teamColour(teamId: string): TeamColours {
  return TEAM_COLOURS[teamId] ?? FALLBACK;
}

const CREAM = "oklch(0.965 0.008 95)";

// England's kit colour is the site red, which clashes with the accent; on the
// forecast it reads as cream instead.
export function chartColour(teamId: string): string {
  return teamId === "england" ? CREAM : teamColour(teamId).primary;
}
