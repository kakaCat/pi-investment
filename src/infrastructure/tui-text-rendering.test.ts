import { describe, expect, test } from "@jest/globals";
import { Text } from "@mariozechner/pi-tui";
import "./tui/pi-tui-compat.js";

describe("pi-tui Text rendering patch", () => {
  test("truncates oversized text before wrapping to avoid call stack overflows", () => {
    const text = new Text("a".repeat(125_000), 0, 0);

    expect(() => text.render(1)).not.toThrow();

    const rendered = text.render(80).join("\n");
    expect(rendered).toContain("TUI output truncated");
    expect(rendered).toContain("chars omitted");
  });
});
