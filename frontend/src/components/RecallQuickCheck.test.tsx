import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import RecallQuickCheck from "./RecallQuickCheck";
import * as api from "../lib/api";

function renderWithRouter(ui: React.ReactElement) {
  return render(<MemoryRouter>{ui}</MemoryRouter>);
}

afterEach(() => {
  vi.restoreAllMocks();
});

describe("RecallQuickCheck", () => {
  it("disables make and model selects until a year (and then a make) is chosen", () => {
    renderWithRouter(<RecallQuickCheck />);
    expect(screen.getByLabelText("Make")).toBeDisabled();
    expect(screen.getByLabelText("Model")).toBeDisabled();
  });

  it("loads makes for the selected year, then models for the selected make", async () => {
    const user = userEvent.setup();
    vi.spyOn(api, "liveNhtsaMakes").mockResolvedValue(["Honda", "Toyota"]);
    vi.spyOn(api, "liveNhtsaModels").mockResolvedValue(["Civic", "Accord"]);

    renderWithRouter(<RecallQuickCheck />);

    await user.selectOptions(screen.getByLabelText("Year"), "2022");
    await waitFor(() => expect(screen.getByLabelText("Make")).not.toBeDisabled());
    expect(api.liveNhtsaMakes).toHaveBeenCalledWith(2022);

    await user.selectOptions(screen.getByLabelText("Make"), "Honda");
    await waitFor(() => expect(screen.getByLabelText("Model")).not.toBeDisabled());
    expect(api.liveNhtsaModels).toHaveBeenCalledWith(2022, "Honda");
  });

  it("shows a validation error when checking recalls without a full year/make/model", async () => {
    const user = userEvent.setup();
    renderWithRouter(<RecallQuickCheck />);

    await user.click(screen.getByRole("button", { name: "Check for Recalls" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("Please select a year, make, and model.");
  });

  it("shows results and calls onChecked after a successful recall check", async () => {
    const user = userEvent.setup();
    vi.spyOn(api, "liveNhtsaMakes").mockResolvedValue(["Honda"]);
    vi.spyOn(api, "liveNhtsaModels").mockResolvedValue(["Civic"]);
    vi.spyOn(api, "liveNhtsaRecalls").mockResolvedValue([
      {
        campaign_number: "24V123",
        report_date: "2024-03-01",
        component: "Fuel system",
        summary: "Possible fuel leak.",
      },
    ] as never);
    const onChecked = vi.fn();

    renderWithRouter(<RecallQuickCheck onChecked={onChecked} />);

    await user.selectOptions(screen.getByLabelText("Year"), "2022");
    await waitFor(() => expect(screen.getByLabelText("Make")).not.toBeDisabled());
    await user.selectOptions(screen.getByLabelText("Make"), "Honda");
    await waitFor(() => expect(screen.getByLabelText("Model")).not.toBeDisabled());
    await user.selectOptions(screen.getByLabelText("Model"), "Civic");

    await user.click(screen.getByRole("button", { name: "Check for Recalls" }));

    expect(await screen.findByText("Fuel system")).toBeInTheDocument();
    expect(onChecked).toHaveBeenCalledWith({ year: 2022, make: "Honda", model: "Civic" });
  });

  it("shows a guidance message when VIN mode is used", async () => {
    const user = userEvent.setup();
    renderWithRouter(<RecallQuickCheck />);

    await user.click(screen.getByRole("button", { name: "VIN" }));
    await user.click(screen.getByRole("button", { name: "Check for Recalls" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(/VIN decoding uses the same live NHTSA lookup/);
  });
});
