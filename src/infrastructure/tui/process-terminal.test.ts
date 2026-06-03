import { afterEach, describe, expect, jest, test } from "@jest/globals";
import { ProcessTerminal } from "@mariozechner/pi-tui";
import "./pi-tui-compat.js";

const execSyncMock = jest.fn();

jest.unstable_mockModule("child_process", () => ({
  execSync: execSyncMock,
}));

describe("pi-tui ProcessTerminal keyboard protocol patch", () => {
  const originalStdoutWrite = process.stdout.write;
  const originalStdinOn = process.stdin.on;
  const originalStdinEmit = process.stdin.emit;

  afterEach(() => {
    process.stdout.write = originalStdoutWrite;
    process.stdin.on = originalStdinOn;
    process.stdin.emit = originalStdinEmit;
    execSyncMock.mockReset();
    jest.restoreAllMocks();
  });

  test("does not enable Kitty keyboard or xterm modifyOtherKeys", () => {
    const writes: string[] = [];
    process.stdout.write = ((data: string | Uint8Array) => {
      writes.push(typeof data === "string" ? data : Buffer.from(data).toString("utf8"));
      return true;
    }) as typeof process.stdout.write;
    process.stdin.on = jest.fn() as unknown as typeof process.stdin.on;
    const setRawMode = jest.fn((_: boolean) => process.stdin);
    const originalIsTTY = process.stdin.isTTY;
    const originalSetRawMode = process.stdin.setRawMode;
    Object.defineProperty(process.stdin, "isTTY", { configurable: true, value: true });
    process.stdin.setRawMode = setRawMode;

    const terminal = new ProcessTerminal();
    const runtime = terminal as unknown as {
      queryAndEnableKittyProtocol: () => void;
      _kittyProtocolActive: boolean;
      _modifyOtherKeysActive: boolean;
    };

    runtime.queryAndEnableKittyProtocol();

    expect(process.stdin.on).toHaveBeenCalledWith("data", expect.any(Function));
    expect(writes).toContain("\x1b[<u");
    expect(writes).toContain("\x1b[>4;0m");
    expect(writes).not.toContain("\x1b[?u");
    expect(writes).not.toContain("\x1b[>7u");
    expect(writes).not.toContain("\x1b[>4;2m");
    expect(runtime._kittyProtocolActive).toBe(false);
    expect(runtime._modifyOtherKeysActive).toBe(false);
    expect(setRawMode).not.toHaveBeenCalledWith(false);
    expect(execSyncMock).not.toHaveBeenCalled();

    Object.defineProperty(process.stdin, "isTTY", { configurable: true, value: originalIsTTY });
    process.stdin.setRawMode = originalSetRawMode;
  });

  test("keeps bracketed paste enabled after start", () => {
    const writes: string[] = [];
    process.stdout.write = ((data: string | Uint8Array) => {
      writes.push(typeof data === "string" ? data : Buffer.from(data).toString("utf8"));
      return true;
    }) as typeof process.stdout.write;
    process.stdin.on = jest.fn() as unknown as typeof process.stdin.on;
    const originalStdoutOn = process.stdout.on;
    const setRawMode = jest.fn((_: boolean) => process.stdin);
    const resume = jest.fn(() => process.stdin);
    const setEncoding = jest.fn(() => process.stdin);
    const originalIsTTY = process.stdin.isTTY;
    const originalSetRawMode = process.stdin.setRawMode;
    const originalResume = process.stdin.resume;
    const originalSetEncoding = process.stdin.setEncoding;
    const originalKill = process.kill;
    Object.defineProperty(process.stdin, "isTTY", { configurable: true, value: true });
    process.stdin.setRawMode = setRawMode;
    process.stdin.resume = resume as typeof process.stdin.resume;
    process.stdin.setEncoding = setEncoding as typeof process.stdin.setEncoding;
    process.stdout.on = jest.fn() as unknown as typeof process.stdout.on;
    process.kill = jest.fn() as unknown as typeof process.kill;

    const terminal = new ProcessTerminal();
    terminal.start(() => {}, () => {});

    expect(writes).toContain("\x1b[?2004h");
    const enableIndex = writes.lastIndexOf("\x1b[?2004h");
    const disableIndex = writes.lastIndexOf("\x1b[?2004l");
    expect(disableIndex).toBeLessThan(enableIndex);

    Object.defineProperty(process.stdin, "isTTY", { configurable: true, value: originalIsTTY });
    process.stdin.setRawMode = originalSetRawMode;
    process.stdin.resume = originalResume;
    process.stdin.setEncoding = originalSetEncoding;
    process.stdout.on = originalStdoutOn;
    process.kill = originalKill;
  });

  test("consumes TTY read EIO errors during restart instead of throwing", () => {
    process.stdout.write = jest.fn(() => true) as unknown as typeof process.stdout.write;
    const error = Object.assign(new Error("read EIO"), { code: "EIO" });

    expect(() => {
      process.stdin.emit("error", error);
    }).not.toThrow();
  });
});
