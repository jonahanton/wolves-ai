interface ClampedProseProps {
  title: string;
  text: string;
  mono?: boolean;
}

const CLAMP_CHARS = 600;

export function ClampedProse({ title, text, mono = false }: ClampedProseProps) {
  const body = mono
    ? "whitespace-pre-wrap font-mono text-[13.5px] leading-[1.7] text-cream-dim"
    : "whitespace-pre-line text-[15.5px] font-light leading-[1.65] text-cream-dim";

  return (
    <div>
      <div className="mb-2 font-mono text-[12px] uppercase tracking-[0.14em] text-cream-faint">{title}</div>
      {text.length <= CLAMP_CHARS ? (
        <p className={`max-w-[68ch] ${body}`}>{text}</p>
      ) : (
        <details className="group max-w-[68ch]">
          <summary className="cursor-pointer list-none">
            <p className={`${body} group-open:hidden`}>{`${text.slice(0, breakAt(text)).trimEnd()}…`}</p>
            <span className="mt-2 inline-block border-b border-hairline pb-0.5 font-mono text-[12.5px] text-cream-faint group-open:hidden">
              the full argument
            </span>
          </summary>
          <p className={body}>{text}</p>
        </details>
      )}
    </div>
  );
}

function breakAt(text: string): number {
  const space = text.lastIndexOf(" ", CLAMP_CHARS);
  return space > CLAMP_CHARS / 2 ? space : CLAMP_CHARS;
}
