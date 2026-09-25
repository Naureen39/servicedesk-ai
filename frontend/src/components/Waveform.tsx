import { useEffect, useState } from "react";

interface WaveformProps {
  level: number;
  active: boolean;
}

const BAR_COUNT = 24;

export default function Waveform({ level, active }: WaveformProps) {
  const [bars, setBars] = useState<number[]>(() => new Array(BAR_COUNT).fill(0));

  useEffect(() => {
    setBars((prev) => [...prev.slice(1), active ? level : 0]);
  }, [level, active]);

  return (
    <div className="flex h-14 items-end justify-center gap-[3px]" role="img" aria-label={active ? "Listening" : "Idle"}>
      {bars.map((v, i) => (
        <span
          key={i}
          className="w-1 rounded-sm bg-accent transition-[height] duration-75"
          style={{ height: `${Math.max(4, Math.min(1, v * 3) * 48)}px` }}
        />
      ))}
    </div>
  );
}
