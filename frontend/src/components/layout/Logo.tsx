export default function Logo({ className, dark }: { className?: string; dark?: boolean }) {
  const fg = dark ? "#F8FAFC" : "#0B1F3A";
  const accent = "#2563EB";
  return (
    <svg viewBox="0 0 280 40" height="28" className={className} role="img" aria-label="Meridian Auto Group">
      <path d="M4 30 L14 8 L20 22 L26 8 L36 30" fill="none" stroke={accent} strokeWidth="4" strokeLinecap="round" strokeLinejoin="round" />
      <text x="46" y="18" fontFamily="Manrope, sans-serif" fontWeight="800" fontSize="15" fill={fg} letterSpacing="0.5">
        MERIDIAN
      </text>
      <text x="46" y="33" fontFamily="Manrope, sans-serif" fontWeight="700" fontSize="11" fill={accent} letterSpacing="2">
        AUTO GROUP
      </text>
    </svg>
  );
}
