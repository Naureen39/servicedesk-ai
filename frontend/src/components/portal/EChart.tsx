import { useRef } from "react";
import ReactECharts from "echarts-for-react";
import type { EChartsOption } from "echarts";
import Button from "../ui/Button";

/** Section 8.3: "Apache ECharts, shared theme matching design tokens" -- every chart on the
 * portal renders through this wrapper so tooltip/legend-toggle/PNG-export (Section 8's DoD)
 * behave identically everywhere instead of being re-implemented per chart. */

const PALETTE = ["#2563EB", "#16A34A", "#F59E0B", "#DC2626", "#1E3A5F", "#0B1F3A", "#94A3B8"];

export default function EChart({
  option, height = 320, title,
}: {
  // Callers build chart-type-specific option objects (bar/line/pie/heatmap/gauge/...) as
  // plain object literals; TypeScript can't narrow a literal `type: "line"` string to
  // ECharts' discriminated union without `as const` sprinkled through every call site, so this
  // accepts a loose shape and leans on ECharts' own runtime validation instead.
  option: Record<string, unknown>;
  height?: number;
  title?: string;
}) {
  const ref = useRef<ReactECharts | null>(null);

  const mergedOption: EChartsOption = {
    color: PALETTE,
    textStyle: { fontFamily: "Inter, system-ui, sans-serif" },
    tooltip: { trigger: "axis", confine: true },
    legend: { top: 0, textStyle: { fontSize: 11 } },
    grid: { left: 48, right: 16, top: title ? 56 : 36, bottom: 32, containLabel: true },
    ...option,
  };

  const exportPng = () => {
    const instance = ref.current?.getEchartsInstance();
    if (!instance) return;
    const url = instance.getDataURL({ type: "png", pixelRatio: 2, backgroundColor: "#fff" });
    const a = document.createElement("a");
    a.href = url;
    a.download = `${(title ?? "chart").toLowerCase().replace(/\s+/g, "-")}.png`;
    a.click();
  };

  return (
    <div>
      {title && (
        <div className="mb-1 flex items-center justify-between">
          <h3 className="text-sm font-semibold text-slate-700">{title}</h3>
          <Button variant="ghost" size="sm" onClick={exportPng} className="text-xs">
            Export PNG
          </Button>
        </div>
      )}
      <ReactECharts ref={ref} option={mergedOption} style={{ height }} notMerge />
    </div>
  );
}
