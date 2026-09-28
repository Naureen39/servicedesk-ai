import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import Button from "./Button";

describe("Button", () => {
  it("renders its children", () => {
    render(<Button>Book now</Button>);
    expect(screen.getByRole("button", { name: "Book now" })).toBeInTheDocument();
  });

  it("calls onClick when clicked", async () => {
    const user = userEvent.setup();
    const onClick = vi.fn();
    render(<Button onClick={onClick}>Submit</Button>);

    await user.click(screen.getByRole("button", { name: "Submit" }));

    expect(onClick).toHaveBeenCalledTimes(1);
  });

  it("does not call onClick when disabled", async () => {
    const user = userEvent.setup();
    const onClick = vi.fn();
    render(
      <Button onClick={onClick} disabled>
        Submit
      </Button>,
    );

    await user.click(screen.getByRole("button", { name: "Submit" }));

    expect(onClick).not.toHaveBeenCalled();
  });

  it("applies the danger variant class", () => {
    render(<Button variant="danger">Delete</Button>);
    expect(screen.getByRole("button", { name: "Delete" }).className).toContain("bg-danger");
  });
});
