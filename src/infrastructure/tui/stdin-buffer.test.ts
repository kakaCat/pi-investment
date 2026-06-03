import { describe, expect, test } from "@jest/globals";
import { Editor, StdinBuffer, type EditorTheme, type TUI } from "@mariozechner/pi-tui";
import "./pi-tui-compat.js";

describe("pi-tui StdinBuffer", () => {
  function createEditor(): Editor {
    const tui = { terminal: { rows: 24, columns: 80 }, requestRender() {} } as unknown as TUI;
    const plain = (text: string) => text;
    const theme: EditorTheme = {
      borderColor: plain,
      selectList: {
        selectedPrefix: plain,
        selectedText: plain,
        description: plain,
        scrollInfo: plain,
        noMatch: plain,
      },
    };
    return new Editor(tui, theme);
  }

  test("deduplicates Kitty printable CSI-u events followed by the same Unicode character", async () => {
    const buffer = new StdinBuffer({ timeout: 10 });
    const events: string[] = [];
    buffer.on("data", (sequence: string) => events.push(sequence));

    buffer.process(`\x1b[20320u你\x1b[21704u哈dc`);
    await new Promise((resolve) => setTimeout(resolve, 20));

    expect(events).toEqual(["\x1b[20320u", "\x1b[21704u", "d", "c"]);
  });

  test("deduplicates IME space-confirmed Unicode after Kitty printable CSI-u", async () => {
    const buffer = new StdinBuffer({ timeout: 10 });
    const events: string[] = [];
    buffer.on("data", (sequence: string) => events.push(sequence));

    buffer.process(`\x1b[20320u 你`);
    await new Promise((resolve) => setTimeout(resolve, 20));

    expect(events).toEqual(["\x1b[20320u", " "]);
  });

  test("deduplicates Kitty printable CSI-u with explicit plain modifier", async () => {
    const buffer = new StdinBuffer({ timeout: 10 });
    const events: string[] = [];
    buffer.on("data", (sequence: string) => events.push(sequence));

    buffer.process(`\x1b[20320;1u你`);
    await new Promise((resolve) => setTimeout(resolve, 20));

    expect(events).toEqual(["\x1b[20320;1u"]);
  });

  test("normalizes Kitty functional arrow keys before they reach the editor", async () => {
    const buffer = new StdinBuffer({ timeout: 10 });
    const editor = createEditor();

    for (const sequence of ["h", "i", " ", "\x1b[20320u", "\x1b[22909u"]) {
      editor.handleInput(sequence);
    }
    buffer.on("data", (sequence: string) => editor.handleInput(sequence));

    buffer.process("\x1b[57417u");
    await new Promise((resolve) => setTimeout(resolve, 20));
    editor.handleInput("!");

    expect(editor.getText()).toBe("hi 你!好");
  });

  test("submits Chinese text when Kitty printable input is followed by Enter", async () => {
    const buffer = new StdinBuffer({ timeout: 10 });
    const editor = createEditor();
    const submitted: string[] = [];
    editor.onSubmit = (text) => submitted.push(text);
    buffer.on("data", (sequence: string) => editor.handleInput(sequence));

    buffer.process("\x1b[20320u你\x1b[22909u好\x1b[13u");
    await new Promise((resolve) => setTimeout(resolve, 20));

    expect(submitted).toEqual(["你好"]);
    expect(editor.getText()).toBe("");
  });

  test("submits raw IME Chinese text when followed by carriage return", async () => {
    const buffer = new StdinBuffer({ timeout: 10 });
    const editor = createEditor();
    const submitted: string[] = [];
    editor.onSubmit = (text) => submitted.push(text);
    buffer.on("data", (sequence: string) => editor.handleInput(sequence));

    buffer.process("你好\r");
    await new Promise((resolve) => setTimeout(resolve, 20));

    expect(submitted).toEqual(["你好"]);
    expect(editor.getText()).toBe("");
  });

  test("treats bare line feed as Enter submit instead of inserting a newline", async () => {
    const buffer = new StdinBuffer({ timeout: 10 });
    const editor = createEditor();
    const submitted: string[] = [];
    editor.onSubmit = (text) => submitted.push(text);
    buffer.on("data", (sequence: string) => editor.handleInput(sequence));

    buffer.process("你好\n");
    await new Promise((resolve) => setTimeout(resolve, 20));

    expect(submitted).toEqual(["你好"]);
    expect(editor.getText()).toBe("");
  });

  test("normalizes stray SS3 arrow tails caused by split terminal input", async () => {
    const buffer = new StdinBuffer({ timeout: 10 });
    const events: string[] = [];
    buffer.on("data", (sequence: string) => events.push(sequence));

    buffer.process("OD");

    expect(events).toEqual(["\x1b[D"]);
  });

  test("waits longer for split escape arrow sequences before flushing", async () => {
    const buffer = new StdinBuffer({ timeout: 10 });
    const events: string[] = [];
    buffer.on("data", (sequence: string) => events.push(sequence));

    buffer.process("\x1b");
    await new Promise((resolve) => setTimeout(resolve, 25));
    buffer.process("OD");
    await new Promise((resolve) => setTimeout(resolve, 120));

    expect(events).toEqual(["\x1bOD"]);
  });

  test("does not insert Kitty arrow release events as visible text", async () => {
    const buffer = new StdinBuffer({ timeout: 10 });
    const events: string[] = [];
    buffer.on("data", (sequence: string) => events.push(sequence));

    buffer.process("\x1b[1;1:3D");
    await new Promise((resolve) => setTimeout(resolve, 20));

    expect(events).toEqual([]);
  });

  test("keeps astral Unicode characters intact when splitting non-escape input", async () => {
    const buffer = new StdinBuffer({ timeout: 10 });
    const events: string[] = [];
    buffer.on("data", (sequence: string) => events.push(sequence));

    buffer.process("𠮷");

    expect(events).toEqual(["𠮷"]);
  });
});
