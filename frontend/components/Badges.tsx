import { DATA_CLASS_STYLE, LEVEL_ICON, LEVEL_STYLE } from "@/lib/format";
import type { DataClass, Level } from "@/lib/types";

export function LevelBadge({ level, size = "md" }: { level: Level; size?: "sm" | "md" | "lg" }) {
  const style = LEVEL_STYLE[level];
  const sizing = size === "lg" ? "px-3.5 py-1.5 text-base" : size === "sm" ? "px-2 py-0.5 text-xs" : "px-2.5 py-1 text-sm";
  return (
    <span className={`inline-flex items-center gap-1.5 rounded-full font-semibold ${style.bg} ${style.fg} ${sizing}`}>
      <span aria-hidden className="font-mono text-[0.8em] opacity-80">
        {LEVEL_ICON[level]}
      </span>
      {style.label}
    </span>
  );
}

export function DataClassBadge({ dataClass }: { dataClass: DataClass | null | undefined }) {
  if (!dataClass) return null;
  const style = DATA_CLASS_STYLE[dataClass];
  return <span className={`inline-flex items-center rounded-md border px-1.5 py-0.5 text-[11px] font-medium ${style.className}`}>{style.label}</span>;
}

export function DemoBadge() {
  return <span className="inline-flex items-center rounded-md border border-fuchsia-300 bg-fuchsia-50 px-1.5 py-0.5 text-[11px] font-bold text-fuchsia-800">DEMO</span>;
}
