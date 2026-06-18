const LIP_FILL = "oklch(0.17 0.025 248 / 0.985)";
const LIP_CAP_W = 28;
const LIP_CAP_L = "M0 0 C0 15 7 24 18 24 L28 24 L28 0 Z";
const LIP_CAP_R = "M28 0 C28 15 21 24 10 24 L0 24 L0 0 Z";

export function LiveDigestSkeleton() {
  return (
    <section aria-label="Live results digest" aria-busy className="relative z-10 flex justify-center px-4">
      <div className="w-[min(500px,calc(100vw_-_32px))]">
        <div className="relative -mt-px mx-auto flex min-h-6 w-full items-center justify-center px-8 py-1">
          <span aria-hidden className="absolute inset-0 -z-10 flex">
            <svg viewBox={`0 0 ${LIP_CAP_W} 24`} preserveAspectRatio="none" className="h-full" style={{ width: LIP_CAP_W }}>
              <path d={LIP_CAP_L} fill={LIP_FILL} />
            </svg>
            <span className="h-full flex-1" style={{ backgroundColor: LIP_FILL }} />
            <svg viewBox={`0 0 ${LIP_CAP_W} 24`} preserveAspectRatio="none" className="h-full" style={{ width: LIP_CAP_W }}>
              <path d={LIP_CAP_R} fill={LIP_FILL} />
            </svg>
          </span>
          <span className="h-[11px] w-44 rounded-full bg-cream/10 shimmer-cream" />
        </div>
      </div>
    </section>
  );
}
