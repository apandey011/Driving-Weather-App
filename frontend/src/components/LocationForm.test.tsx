import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { forwardRef } from "react";
import LocationForm from "./LocationForm";

vi.mock("./PlaceAutocomplete", () => ({
  default: forwardRef(function MockPlaceAutocomplete(props: any, ref: any) {
    return (
      <input
        ref={ref}
        placeholder={props.placeholder}
        required={props.required}
        data-testid={props.placeholder}
      />
    );
  }),
}));

describe("LocationForm", () => {
  it("renders origin input, destination input, datetime input, and submit button", () => {
    render(<LocationForm onSubmit={vi.fn()} loading={false} />);
    expect(screen.getByTestId("Starting location")).toBeInTheDocument();
    expect(screen.getByTestId("Destination")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /get route weather/i })).toBeInTheDocument();
    // datetime-local input
    const datetimeInput = document.querySelector('input[type="datetime-local"]');
    expect(datetimeInput).toBeInTheDocument();
  });

  it("shows 'Loading...' on submit button when loading is true", () => {
    render(<LocationForm onSubmit={vi.fn()} loading={true} />);
    expect(screen.getByRole("button", { name: /loading/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /loading/i })).toBeDisabled();
  });

  it("shows validation error when both fields are empty", async () => {
    render(<LocationForm onSubmit={vi.fn()} loading={false} />);
    const form = screen.getByRole("button", { name: /get route weather/i }).closest("form");
    expect(form).toBeTruthy();

    fireEvent.submit(form!);

    await waitFor(() => {
      expect(screen.getByText("Please enter both origin and destination.")).toBeInTheDocument();
    });
  });

  it("shows validation error when origin equals destination", async () => {
    const user = userEvent.setup();
    render(<LocationForm onSubmit={vi.fn()} loading={false} />);

    const originInput = screen.getByTestId("Starting location");
    const destInput = screen.getByTestId("Destination");
    await user.type(originInput, "San Francisco");
    await user.type(destInput, "San Francisco");
    await user.click(screen.getByRole("button", { name: /get route weather/i }));

    await waitFor(() => {
      expect(screen.getByText("Origin and destination must be different.")).toBeInTheDocument();
    });
  });

  it("calls onSubmit with correct arguments on valid submission", async () => {
    const user = userEvent.setup();
    const onSubmit = vi.fn();
    render(<LocationForm onSubmit={onSubmit} loading={false} />);

    const originInput = screen.getByTestId("Starting location");
    const destInput = screen.getByTestId("Destination");
    await user.type(originInput, "San Francisco");
    await user.type(destInput, "Los Angeles");
    await user.click(screen.getByRole("button", { name: /get route weather/i }));

    await waitFor(() => {
      expect(onSubmit).toHaveBeenCalledTimes(1);
    });
    // First arg is origin (or originQueryRef fallback), second is destination
    expect(onSubmit.mock.calls[0][0]).toBe("San Francisco");
    expect(onSubmit.mock.calls[0][1]).toBe("Los Angeles");
  });

  it("swaps origin and destination values when swap button is clicked", async () => {
    const user = userEvent.setup();
    render(<LocationForm onSubmit={vi.fn()} loading={false} />);

    const originInput = screen.getByTestId("Starting location") as HTMLInputElement;
    const destInput = screen.getByTestId("Destination") as HTMLInputElement;

    await user.type(originInput, "San Francisco");
    await user.type(destInput, "Los Angeles");

    const swapButton = screen.getByTitle("Swap origin and destination");
    await user.click(swapButton);

    expect(originInput.value).toBe("Los Angeles");
    expect(destInput.value).toBe("San Francisco");
  });

  it("shows 'Get Route Weather' when not loading", () => {
    render(<LocationForm onSubmit={vi.fn()} loading={false} />);
    expect(screen.getByRole("button", { name: /get route weather/i })).toHaveTextContent("Get Route Weather");
  });

  it("clears validation error on valid submit", async () => {
    const user = userEvent.setup();
    const onSubmit = vi.fn();
    render(<LocationForm onSubmit={onSubmit} loading={false} />);

    // First trigger a validation error
    const form = screen.getByRole("button", { name: /get route weather/i }).closest("form");
    expect(form).toBeTruthy();
    fireEvent.submit(form!);

    await waitFor(() => {
      expect(screen.getByText("Please enter both origin and destination.")).toBeInTheDocument();
    });

    // Now fill in valid values and submit again
    const originInput = screen.getByTestId("Starting location");
    const destInput = screen.getByTestId("Destination");
    await user.type(originInput, "San Francisco");
    await user.type(destInput, "Los Angeles");
    await user.click(screen.getByRole("button", { name: /get route weather/i }));

    await waitFor(() => {
      expect(screen.queryByText("Please enter both origin and destination.")).not.toBeInTheDocument();
    });
  });
});
