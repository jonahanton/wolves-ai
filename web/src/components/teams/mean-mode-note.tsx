"use client";

import { useState } from "react";

export function MeanModeNote() {
  const [open, setOpen] = useState(false);
  return (
    <button
      type="button"
      onClick={() => setOpen((v) => !v)}
      aria-expanded={open}
      className="group mt-6 block text-left font-display text-[12.5px] italic leading-relaxed text-cream-faint transition-colors hover:text-cream-dim"
    >
      {open ? (
        <span>
          On any team&rsquo;s outcome chart,{" "}
          <span className="font-semibold not-italic text-cream-dim">mode</span>{" "}
          is the tallest bar and the likeliest exit point for that team.{" "}
          <span className="font-semibold not-italic text-cream-dim">Mean</span>{" "}
          is the average exit point over the simulated runs. The two diverge
          when the distribution is skewed: deep runs into the tournament pull
          the mean past the mode.{" "}
          <span className="not-italic text-cream-faint group-hover:text-cream">
            Show less
          </span>
        </span>
      ) : (
        <span>
          <span className="bg-gradient-to-r from-cream-faint to-cream-faint/20 bg-clip-text text-transparent">
            Mode is the likeliest exit, mean the average
          </span>
          <span className="text-cream-faint/20">…</span>{" "}
          <span className="not-italic text-cream-dim group-hover:text-cream">
            Read more
          </span>
        </span>
      )}
    </button>
  );
}
