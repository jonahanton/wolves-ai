"use client";

import { useState } from "react";

const LEAD =
  "Each component (competing view) is a Gaussian posterior over team strengths.";

export function MechanismNote() {
  const [open, setOpen] = useState(false);
  return (
    <button
      type="button"
      onClick={() => setOpen((v) => !v)}
      aria-expanded={open}
      className="group mb-2 mt-3 block text-left font-display text-[12px] italic leading-relaxed text-cream-faint transition-colors hover:text-cream-dim"
    >
      {open ? (
        <span>
          {LEAD} The agent prices evidence it sees (e.g. an injury, a
          suspension, a market signal, etc.) and shifts the affected
          teams&rsquo; posterior means, and where an effect&rsquo;s size is
          itself uncertain it widens their variance. We take 200 samples of
          those modified team strengths and run the whole tournament 250 times
          for each (50k simulations in total), for each mixture component. A
          team&rsquo;s probability is how often it wins these tournaments. The
          spread across the 200 samples is the curve above.{" "}
          <span className="not-italic text-cream-faint group-hover:text-cream">
            Show less
          </span>
        </span>
      ) : (
        <span>
          {LEAD}{" "}
          <span className="bg-gradient-to-r from-cream-faint to-cream-faint/20 bg-clip-text text-transparent">
            The agent prices the evidence it sees and shifts
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
