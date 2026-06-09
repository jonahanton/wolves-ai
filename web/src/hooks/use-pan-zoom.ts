"use client";

import { useCallback, useEffect, useRef } from "react";

interface PanZoomOptions {
  contentWidth: number;
  contentHeight: number;
  maxScale?: number;
}

interface Transform {
  x: number;
  y: number;
  scale: number;
}

const DOUBLE_TAP_MS = 300;
const TAP_SLOP_PX = 8;
const DOUBLE_TAP_SCALE = 1.4;

export function usePanZoom({ contentWidth, contentHeight, maxScale = 2.5 }: PanZoomOptions) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const contentRef = useRef<SVGSVGElement | null>(null);
  const transform = useRef<Transform>({ x: 0, y: 0, scale: 1 });
  const pointers = useRef(new Map<number, { x: number; y: number }>());
  const pinchStart = useRef<{ distance: number; scale: number } | null>(null);
  const lastTap = useRef<{ time: number; x: number; y: number } | null>(null);
  const dragDistance = useRef(0);
  const frame = useRef(0);

  const minScale = useCallback(() => {
    const container = containerRef.current;
    if (!container) return 0.1;
    return Math.min(container.clientWidth / contentWidth, container.clientHeight / contentHeight);
  }, [contentWidth, contentHeight]);

  const clamp = useCallback(
    (next: Transform): Transform => {
      const container = containerRef.current;
      if (!container) return next;
      const scale = Math.min(maxScale, Math.max(minScale(), next.scale));
      const scaledW = contentWidth * scale;
      const scaledH = contentHeight * scale;
      const clampAxis = (value: number, viewport: number, content: number) =>
        content <= viewport
          ? (viewport - content) / 2
          : Math.min(0, Math.max(viewport - content, value));
      return {
        scale,
        x: clampAxis(next.x, container.clientWidth, scaledW),
        y: clampAxis(next.y, container.clientHeight, scaledH),
      };
    },
    [contentWidth, contentHeight, maxScale, minScale],
  );

  // Transform-only updates on the SVG element keep panning off the React render path.
  const apply = useCallback(() => {
    cancelAnimationFrame(frame.current);
    frame.current = requestAnimationFrame(() => {
      const { x, y, scale } = transform.current;
      if (contentRef.current) {
        contentRef.current.style.transform = `translate(${x}px, ${y}px) scale(${scale})`;
      }
    });
  }, []);

  const setTransform = useCallback(
    (next: Transform) => {
      transform.current = clamp(next);
      apply();
    },
    [clamp, apply],
  );

  const zoomAt = useCallback(
    (clientX: number, clientY: number, nextScale: number) => {
      const container = containerRef.current;
      if (!container) return;
      const rect = container.getBoundingClientRect();
      const px = clientX - rect.left;
      const py = clientY - rect.top;
      const { x, y, scale } = transform.current;
      const ratio = Math.min(maxScale, Math.max(minScale(), nextScale)) / scale;
      setTransform({ x: px - (px - x) * ratio, y: py - (py - y) * ratio, scale: scale * ratio });
    },
    [maxScale, minScale, setTransform],
  );

  const focusOn = useCallback(
    (contentX: number, contentY: number, scale: number) => {
      const container = containerRef.current;
      if (!container) return;
      const clamped = Math.min(maxScale, Math.max(minScale(), scale));
      setTransform({
        x: container.clientWidth / 2 - contentX * clamped,
        y: container.clientHeight / 2 - contentY * clamped,
        scale: clamped,
      });
    },
    [maxScale, minScale, setTransform],
  );

  const fit = useCallback(() => {
    focusOn(contentWidth / 2, contentHeight / 2, minScale());
  }, [contentWidth, contentHeight, focusOn, minScale]);

  const zoomBy = useCallback(
    (factor: number) => {
      const container = containerRef.current;
      if (!container) return;
      const rect = container.getBoundingClientRect();
      zoomAt(rect.left + rect.width / 2, rect.top + rect.height / 2, transform.current.scale * factor);
    },
    [zoomAt],
  );

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    const onPointerDown = (e: PointerEvent) => {
      container.setPointerCapture(e.pointerId);
      pointers.current.set(e.pointerId, { x: e.clientX, y: e.clientY });
      dragDistance.current = 0;
      if (pointers.current.size === 2) {
        const [a, b] = [...pointers.current.values()];
        pinchStart.current = { distance: Math.hypot(a.x - b.x, a.y - b.y), scale: transform.current.scale };
      }
    };

    const onPointerMove = (e: PointerEvent) => {
      const previous = pointers.current.get(e.pointerId);
      if (!previous) return;
      pointers.current.set(e.pointerId, { x: e.clientX, y: e.clientY });

      if (pointers.current.size === 2 && pinchStart.current) {
        const [a, b] = [...pointers.current.values()];
        const distance = Math.hypot(a.x - b.x, a.y - b.y);
        const midX = (a.x + b.x) / 2;
        const midY = (a.y + b.y) / 2;
        zoomAt(midX, midY, pinchStart.current.scale * (distance / pinchStart.current.distance));
        dragDistance.current = Infinity;
        return;
      }

      const dx = e.clientX - previous.x;
      const dy = e.clientY - previous.y;
      dragDistance.current += Math.hypot(dx, dy);
      const { x, y, scale } = transform.current;
      setTransform({ x: x + dx, y: y + dy, scale });
    };

    const onPointerUp = (e: PointerEvent) => {
      pointers.current.delete(e.pointerId);
      if (pointers.current.size < 2) pinchStart.current = null;

      const isTap = dragDistance.current < TAP_SLOP_PX;
      if (!isTap) {
        lastTap.current = null;
        return;
      }
      const now = performance.now();
      const previous = lastTap.current;
      lastTap.current = { time: now, x: e.clientX, y: e.clientY };
      if (
        previous &&
        now - previous.time < DOUBLE_TAP_MS &&
        Math.hypot(e.clientX - previous.x, e.clientY - previous.y) < TAP_SLOP_PX * 3
      ) {
        lastTap.current = null;
        const zoomedIn = transform.current.scale > minScale() * 1.5;
        if (zoomedIn) fit();
        else zoomAt(e.clientX, e.clientY, DOUBLE_TAP_SCALE);
      }
    };

    const onWheel = (e: WheelEvent) => {
      e.preventDefault();
      zoomAt(e.clientX, e.clientY, transform.current.scale * Math.exp(-e.deltaY * 0.0015));
    };

    container.addEventListener("pointerdown", onPointerDown);
    container.addEventListener("pointermove", onPointerMove);
    container.addEventListener("pointerup", onPointerUp);
    container.addEventListener("pointercancel", onPointerUp);
    container.addEventListener("wheel", onWheel, { passive: false });
    return () => {
      container.removeEventListener("pointerdown", onPointerDown);
      container.removeEventListener("pointermove", onPointerMove);
      container.removeEventListener("pointerup", onPointerUp);
      container.removeEventListener("pointercancel", onPointerUp);
      container.removeEventListener("wheel", onWheel);
      cancelAnimationFrame(frame.current);
    };
  }, [fit, minScale, setTransform, zoomAt]);

  const wasDrag = useCallback(() => dragDistance.current >= TAP_SLOP_PX, []);

  return { containerRef, contentRef, focusOn, fit, zoomBy, wasDrag };
}
