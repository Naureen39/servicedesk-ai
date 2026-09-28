import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import FaqAccordion from "./FaqAccordion";

const items = [
  { question: "How long does an oil change take?", answer: "About 30 minutes for most vehicles." },
  { question: "Do you offer loaner cars?", answer: "Yes, for service appointments over four hours." },
];

describe("FaqAccordion", () => {
  it("renders every question", () => {
    render(<FaqAccordion items={items} />);
    for (const item of items) {
      expect(screen.getByText(item.question)).toBeInTheDocument();
    }
  });

  it("hides answers until their question is expanded", async () => {
    const user = userEvent.setup();
    render(<FaqAccordion items={items} />);

    expect(screen.queryByText(items[0].answer)).not.toBeInTheDocument();

    await user.click(screen.getByText(items[0].question));

    expect(await screen.findByText(items[0].answer)).toBeInTheDocument();
    expect(screen.queryByText(items[1].answer)).not.toBeInTheDocument();
  });

  it("collapses the previous answer when a different question is expanded", async () => {
    const user = userEvent.setup();
    render(<FaqAccordion items={items} />);

    await user.click(screen.getByText(items[0].question));
    expect(await screen.findByText(items[0].answer)).toBeInTheDocument();

    await user.click(screen.getByText(items[1].question));
    expect(await screen.findByText(items[1].answer)).toBeInTheDocument();
    expect(screen.queryByText(items[0].answer)).not.toBeInTheDocument();
  });

  it("renders no questions when given an empty list", () => {
    render(<FaqAccordion items={[]} />);
    expect(screen.queryAllByRole("button").length).toBe(0);
  });
});
