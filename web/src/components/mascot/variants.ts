export type WolfVariant = "idle" | "juggle" | "howl" | "pace";

export interface WolfVariantConfig {
  className: string;
  label: string;
  showBall: boolean;
  showHowlMarks: boolean;
}

export const WOLF_VARIANTS: Record<WolfVariant, WolfVariantConfig> = {
  idle: {
    className: "v-idle",
    label: "Idle",
    showBall: false,
    showHowlMarks: false,
  },
  juggle: {
    className: "v-juggle",
    label: "Ball juggle",
    showBall: true,
    showHowlMarks: false,
  },
  howl: {
    className: "v-howl",
    label: "Howl celebration",
    showBall: false,
    showHowlMarks: true,
  },
  pace: {
    className: "v-pace",
    label: "Anxious pacing",
    showBall: false,
    showHowlMarks: false,
  },
};

export type WolfMood = "neutral" | "happy" | "worried";

export const MOOD_VARIANTS: Record<WolfMood, WolfVariant> = {
  neutral: "idle",
  happy: "howl",
  worried: "pace",
};
