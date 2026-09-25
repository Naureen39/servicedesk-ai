import type { ButtonHTMLAttributes } from "react";
import { cn } from "../../lib/cn";

type Variant = "primary" | "secondary" | "outline" | "ghost" | "danger";
type Size = "sm" | "md" | "lg";

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
  size?: Size;
}

const VARIANTS: Record<Variant, string> = {
  primary: "bg-accent text-white hover:bg-blue-700 focus-visible:ring-accent",
  secondary: "bg-navy text-white hover:bg-steel focus-visible:ring-navy",
  outline: "border border-slate-300 text-slate-900 hover:bg-slate-50 focus-visible:ring-accent",
  ghost: "text-slate-700 hover:bg-slate-100 focus-visible:ring-accent",
  danger: "bg-danger text-white hover:bg-red-700 focus-visible:ring-danger",
};

const SIZES: Record<Size, string> = {
  sm: "text-sm px-3 py-1.5 rounded-[var(--radius-input)]",
  md: "text-base px-4 py-2.5 rounded-[var(--radius-input)]",
  lg: "text-lg px-6 py-3.5 rounded-[var(--radius-input)]",
};

export default function Button({ variant = "primary", size = "md", className, ...props }: ButtonProps) {
  return (
    <button
      className={cn(
        "inline-flex items-center justify-center gap-2 font-semibold transition-colors duration-150 disabled:opacity-50 disabled:cursor-not-allowed focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-offset-2",
        VARIANTS[variant],
        SIZES[size],
        className,
      )}
      {...props}
    />
  );
}
