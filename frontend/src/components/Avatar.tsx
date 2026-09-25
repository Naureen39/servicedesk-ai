const COLORS = ["#2563EB", "#16A34A", "#F59E0B", "#DC2626", "#1E3A5F"];

export default function Avatar({ name, size = 96 }: { name: string; size?: number }) {
  const initials = name
    .split(" ")
    .map((p) => p[0])
    .join("")
    .slice(0, 2)
    .toUpperCase();
  let hash = 0;
  for (let i = 0; i < name.length; i++) hash = (hash * 31 + name.charCodeAt(i)) >>> 0;
  const color = COLORS[hash % COLORS.length];

  return (
    <svg width={size} height={size} viewBox="0 0 96 96" role="img" aria-label={name}>
      <circle cx="48" cy="48" r="48" fill={color} />
      <text x="48" y="58" textAnchor="middle" fontFamily="Manrope, sans-serif" fontWeight="800" fontSize="32" fill="white">
        {initials}
      </text>
    </svg>
  );
}
