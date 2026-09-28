import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import KpiCard from "./KpiCard";

describe("KpiCard", () => {
  it("renders the label and value", () => {
    render(<KpiCard label="Revenue" value="$42,000" />);
    expect(screen.getByText("Revenue")).toBeInTheDocument();
    expect(screen.getByText("$42,000")).toBeInTheDocument();
  });

  it("shows a placeholder when no delta is given", () => {
    render(<KpiCard label="Revenue" value="$42,000" />);
    expect(screen.getByText("No previous period selected")).toBeInTheDocument();
  });

  it("shows an upward arrow and formatted percentage for a positive delta", () => {
    render(<KpiCard label="Revenue" value="$42,000" delta={0.125} />);
    expect(screen.getByText("↑ 12.5% vs previous period")).toBeInTheDocument();
  });

  it("shows a downward arrow for a negative delta", () => {
    render(<KpiCard label="Revenue" value="$42,000" delta={-0.083} />);
    expect(screen.getByText("↓ 8.3% vs previous period")).toBeInTheDocument();
  });

  it("treats a zero delta as positive (up arrow)", () => {
    render(<KpiCard label="Revenue" value="$42,000" delta={0} />);
    expect(screen.getByText("↑ 0.0% vs previous period")).toBeInTheDocument();
  });

  it("renders a sparkline only when there are at least two points", () => {
    const { container, rerender } = render(<KpiCard label="Revenue" value="$1" sparkline={[1]} />);
    expect(container.querySelector("svg")).not.toBeInTheDocument();

    rerender(<KpiCard label="Revenue" value="$1" sparkline={[1, 2, 3]} />);
    expect(container.querySelector("svg")).toBeInTheDocument();
  });
});
