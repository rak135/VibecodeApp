import { render } from "@testing-library/react";
import { HomeScreen } from "./HomeScreen";

describe("HomeScreen", () => {
  it("renders the title", () => {
    const { getByText } = render(<HomeScreen title="Hello" />);
    expect(getByText("Hello")).toBeTruthy();
  });
});
