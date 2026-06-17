"use client";

import { useCallback, useLayoutEffect, useRef } from "react";

const EASE = "cubic-bezier(0.25,1,0.5,1)";
const DURATION = 480;

function reduceMotion(): boolean {
  return typeof window !== "undefined" && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}

// FLIP: when `flipKey` changes, animate each tracked row from its previous
// position to its new one, leaving expand/collapse untouched.
export function useFlipReorder(flipKey: string) {
  const refs = useRef(new Map<string, HTMLElement>());
  const prev = useRef(new Map<string, number>());
  const lastKey = useRef(flipKey);

  useLayoutEffect(() => {
    const next = new Map<string, number>();
    refs.current.forEach((el, id) => next.set(id, el.getBoundingClientRect().top));

    if (lastKey.current !== flipKey && !reduceMotion()) {
      refs.current.forEach((el, id) => {
        const before = prev.current.get(id);
        const after = next.get(id);
        if (before == null || after == null) return;
        const delta = before - after;
        if (Math.abs(delta) < 1) return;
        el.style.transition = "none";
        el.style.transform = `translateY(${delta}px)`;
        void el.offsetHeight;
        el.style.transition = `transform ${DURATION}ms ${EASE}`;
        el.style.transform = "";
      });
    }
    prev.current = next;
    lastKey.current = flipKey;
  }, [flipKey]);

  return useCallback(
    (id: string) => (el: HTMLElement | null) => {
      if (el) refs.current.set(id, el);
      else refs.current.delete(id);
    },
    [],
  );
}
