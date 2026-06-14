"use client";

import { easeCubicInOut } from "d3-ease";
import type { scaleLinear } from "d3-scale";
import { select } from "d3-selection";
import { area as d3Area, curveMonotoneX } from "d3-shape";
import "d3-transition";
import { useEffect, useRef } from "react";
import type { DistroPoint } from "@/lib/distribution";

const MORPH_MS = 420;

function reduceMotion(): boolean {
  return typeof window !== "undefined" && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}

interface MorphPathProps {
  points: DistroPoint[];
  x: ReturnType<typeof scaleLinear<number, number>>;
  height: number;
  peak: number;
  colour: string;
  width: number;
}

// The one element that morphs: the area stroke. d3 interpolates the d-attr
// across team switches; a shared resample grid keeps point counts identical.
export function MorphPath({ points, x, height, peak, colour, width }: MorphPathProps) {
  const gRef = useRef<SVGGElement>(null);
  const y = scaleY(peak, height);
  const d = width === 0 ? "" : (d3Area<DistroPoint>().x((p) => x(p.x)).y0(height).y1((p) => y(p.y)).curve(curveMonotoneX)(points) ?? "");

  useEffect(() => {
    if (!gRef.current || width === 0) return;
    const path = select(gRef.current)
      .selectAll<SVGPathElement, number>("path")
      .data([0])
      .join((enter) => enter.append("path").attr("fill", "none").attr("stroke-width", 1.6).attr("stroke-linejoin", "round").attr("d", d));
    path.attr("stroke", colour);
    if (reduceMotion()) path.attr("d", d);
    else path.transition("morph").duration(MORPH_MS).ease(easeCubicInOut).attr("d", d);
  }, [d, colour, width]);

  return <g ref={gRef} />;
}

function scaleY(peak: number, height: number) {
  const max = (peak || 1) * 1.1;
  return (v: number) => height - (v / max) * height;
}
