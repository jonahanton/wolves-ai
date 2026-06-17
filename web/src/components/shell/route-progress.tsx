"use client";

import { usePathname } from "next/navigation";
import { useEffect, useRef, useState } from "react";

export function RouteProgress() {
  const pathname = usePathname();
  const [visible, setVisible] = useState(false);
  const [width, setWidth] = useState(0);
  const first = useRef(true);

  useEffect(() => {
    if (first.current) {
      first.current = false;
      return;
    }
    setVisible(true);
    setWidth(0);
    const ramp = window.setTimeout(() => setWidth(80), 20);
    const done = window.setTimeout(() => setWidth(100), 220);
    const hide = window.setTimeout(() => setVisible(false), 480);
    return () => {
      window.clearTimeout(ramp);
      window.clearTimeout(done);
      window.clearTimeout(hide);
    };
  }, [pathname]);

  return (
    <div aria-hidden className="pointer-events-none fixed inset-x-0 top-0 z-50 h-0.5">
      <div
        className="h-full bg-gold transition-[width,opacity] duration-200 ease-out"
        style={{ width: `${width}%`, opacity: visible ? 1 : 0 }}
      />
    </div>
  );
}
