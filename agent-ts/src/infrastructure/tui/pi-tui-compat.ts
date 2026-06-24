import { ProcessTerminal, setKittyProtocolActive, StdinBuffer, Text } from "@mariozechner/pi-tui";
import { execSync } from "child_process";
import { appendFileSync, mkdirSync } from "fs";
import { dirname, join } from "path";

const ESC = "\x1b";
const BRACKETED_PASTE_START = "\x1b[200~";
const BRACKETED_PASTE_END = "\x1b[201~";
const PATCH_FLAG = Symbol.for("pi-investment.pi-tui.stdin-buffer-dedupe-patch");
const TERMINAL_PATCH_FLAG = Symbol.for("pi-investment.pi-tui.disable-enhanced-keyboard-patch");
const TERMINAL_SAFETY_FLAG = Symbol.for("pi-investment.terminal-safety-net");
const TEXT_RENDER_PATCH_FLAG = Symbol.for("pi-investment.pi-tui.text-render-truncation-patch");
const MAX_TUI_TEXT_RENDER_CHARS = 80_000;

type PatchedStdinBuffer = StdinBuffer & {
  [PATCH_FLAG]?: boolean;
  __piPendingKittyPrintableCodepoint?: number;
  __piPendingKittyPrintableTimer?: NodeJS.Timeout;
};

type StdinBufferRuntime = {
  [PATCH_FLAG]?: boolean;
  __piPendingKittyPrintableCodepoint?: number;
  __piPendingKittyPrintableTimer?: NodeJS.Timeout;
  buffer: string;
  timeout: NodeJS.Timeout | null;
  timeoutMs: number;
  pasteMode: boolean;
  pasteBuffer: string;
  emit: RawEmit;
  process: (data: string | Buffer) => void;
  flush: () => string[];
  clear: () => void;
  destroy: () => void;
};

type StdinBufferConstructor = {
  prototype: StdinBufferRuntime;
};

type RawEmit = (this: StdinBufferRuntime, eventName: string | symbol, ...args: unknown[]) => boolean;

type TextRuntime = {
  [TEXT_RENDER_PATCH_FLAG]?: boolean;
  text: string;
  cachedText?: string;
  cachedWidth?: number;
  cachedLines?: string[];
  render: (width: number) => string[];
};

type TextConstructor = {
  prototype: TextRuntime;
};

function truncateTextForRendering(text: string): string {
  if (text.length <= MAX_TUI_TEXT_RENDER_CHARS) return text;

  const omitted = text.length - MAX_TUI_TEXT_RENDER_CHARS;
  return (
    text.slice(0, MAX_TUI_TEXT_RENDER_CHARS) +
    `\n\n[TUI output truncated: ${omitted.toLocaleString("en-US")} chars omitted]`
  );
}

function parseUnmodifiedKittyPrintableCodepoint(sequence: string): number | undefined {
  const match = sequence.match(/^\x1b\[(\d+)(?::(\d*))?(?::(\d+))?(?:;(\d+))?(?::(\d+))?u$/);
  if (!match) return undefined;
  const codepoint = Number.parseInt(match[1], 10);
  const modifier = match[4] ? Number.parseInt(match[4], 10) - 1 : 0;
  const eventType = match[5] ? Number.parseInt(match[5], 10) : 1;
  const hasUnsupportedModifier = (modifier & ~(1 | 64 | 128)) !== 0;
  const isPrivateUse = codepoint >= 0xe000 && codepoint <= 0xf8ff;
  if (
    !Number.isFinite(codepoint) ||
    codepoint < 32 ||
    codepoint === 127 ||
    isPrivateUse ||
    hasUnsupportedModifier ||
    eventType !== 1
  ) {
    return undefined;
  }
  return codepoint;
}

function sequenceCodepoint(sequence: string): number | undefined {
  return sequence.length === 1 ? sequence.codePointAt(0) : undefined;
}

function describeSequence(value: string): Record<string, unknown> {
  return {
    text: value,
    hex: Buffer.from(value, "utf8").toString("hex"),
    length: value.length,
    codepoints: [...value].map((char) => char.codePointAt(0)),
  };
}

function writeInputDebug(event: string, payload: Record<string, unknown>): void {
  if (process.env.PI_TUI_INPUT_DEBUG !== "1") return;
  try {
    const logPath = join(process.cwd(), ".pi-invest", "tui-input-debug.jsonl");
    mkdirSync(dirname(logPath), { recursive: true });
    appendFileSync(
      logPath,
      JSON.stringify({ ts: new Date().toISOString(), event, ...payload }) + "\n",
      "utf8",
    );
  } catch {
    // Debug logging must never affect TUI input.
  }
}

function normalizeKittyFunctionalSequence(sequence: string): string {
  const match = sequence.match(/^\x1b\[(\d+)(?:;(\d+)(?::\d+)?)?u$/);
  if (!match) return undefined;

  const codepoint = Number.parseInt(match[1], 10);
  const modifier = match[2] ? Number.parseInt(match[2], 10) - 1 : 0;
  if (modifier !== 0 || !Number.isFinite(codepoint)) return undefined;

  switch (codepoint) {
    case 57417:
      return "\x1b[D";
    case 57418:
      return "\x1b[C";
    case 57419:
      return "\x1b[A";
    case 57420:
      return "\x1b[B";
    case 57421:
      return "\x1b[5~";
    case 57422:
      return "\x1b[6~";
    case 57423:
      return "\x1b[H";
    case 57424:
      return "\x1b[F";
    case 57426:
      return "\x1b[3~";
    default:
      return undefined;
  }
}

function normalizeStrayArrowTail(sequence: string): string {
  switch (sequence) {
    case "OA":
    case "[A":
      return "\x1b[A";
    case "OB":
    case "[B":
      return "\x1b[B";
    case "OC":
    case "[C":
      return "\x1b[C";
    case "OD":
    case "[D":
      return "\x1b[D";
    default:
      return undefined;
  }
}

function takeStrayArrowTailPrefix(input: string): { normalized: string; rest: string } | undefined {
  for (const tail of ["OA", "OB", "OC", "OD", "[A", "[B", "[C", "[D"]) {
    if (input.startsWith(tail)) {
      const normalized = normalizeStrayArrowTail(tail);
      if (normalized !== undefined) {
        return { normalized, rest: input.slice(tail.length) };
      }
    }
  }
  return undefined;
}

function isKittyKeyReleaseSequence(sequence: string): boolean {
  if (sequence.includes(BRACKETED_PASTE_START)) return false;
  return (
    sequence.includes(":3u") ||
    sequence.includes(":3~") ||
    sequence.includes(":3A") ||
    sequence.includes(":3B") ||
    sequence.includes(":3C") ||
    sequence.includes(":3D") ||
    sequence.includes(":3H") ||
    sequence.includes(":3F")
  );
}

function normalizeLineFeedSubmit(sequence: string): string {
  return sequence === "\n" ? "\r" : undefined;
}

function clearPendingKittyPrintable(buffer: StdinBufferRuntime): void {
  buffer.__piPendingKittyPrintableCodepoint = undefined;
  if (buffer.__piPendingKittyPrintableTimer) {
    clearTimeout(buffer.__piPendingKittyPrintableTimer);
    buffer.__piPendingKittyPrintableTimer = undefined;
  }
}

function rememberPendingKittyPrintable(buffer: StdinBufferRuntime, codepoint: number): void {
  clearPendingKittyPrintable(buffer);
  buffer.__piPendingKittyPrintableCodepoint = codepoint;
  buffer.__piPendingKittyPrintableTimer = setTimeout(() => {
    clearPendingKittyPrintable(buffer);
  }, 50);
}

function isCompleteSequence(data: string): "complete" | "incomplete" | "not-escape" {
  if (!data.startsWith(ESC)) return "not-escape";
  if (data.length === 1) return "incomplete";

  const afterEsc = data.slice(1);
  if (afterEsc.startsWith("[")) {
    if (afterEsc.startsWith("[M")) {
      return data.length >= 6 ? "complete" : "incomplete";
    }
    return isCompleteCsiSequence(data);
  }
  if (afterEsc.startsWith("]")) return isCompleteOscSequence(data);
  if (afterEsc.startsWith("P")) return isCompleteStTerminatedSequence(data, `${ESC}P`);
  if (afterEsc.startsWith("_")) return isCompleteStTerminatedSequence(data, `${ESC}_`);
  if (afterEsc.startsWith("O")) return afterEsc.length >= 2 ? "complete" : "incomplete";
  if (afterEsc.length === 1) return "complete";
  return "complete";
}

function isCompleteCsiSequence(data: string): "complete" | "incomplete" {
  if (!data.startsWith(`${ESC}[`)) return "complete";
  if (data.length < 3) return "incomplete";

  const payload = data.slice(2);
  const lastChar = payload[payload.length - 1];
  const lastCharCode = lastChar.charCodeAt(0);
  if (lastCharCode >= 0x40 && lastCharCode <= 0x7e) {
    if (payload.startsWith("<")) {
      const mouseMatch = /^<\d+;\d+;\d+[Mm]$/.test(payload);
      if (mouseMatch) return "complete";
      if (lastChar === "M" || lastChar === "m") {
        const parts = payload.slice(1, -1).split(";");
        if (parts.length === 3 && parts.every((part) => /^\d+$/.test(part))) {
          return "complete";
        }
      }
      return "incomplete";
    }
    return "complete";
  }
  return "incomplete";
}

function isCompleteOscSequence(data: string): "complete" | "incomplete" {
  if (!data.startsWith(`${ESC}]`)) return "complete";
  return data.endsWith(`${ESC}\\`) || data.endsWith("\x07") ? "complete" : "incomplete";
}

function isCompleteStTerminatedSequence(
  data: string,
  prefix: string,
): "complete" | "incomplete" {
  if (!data.startsWith(prefix)) return "complete";
  return data.endsWith(`${ESC}\\`) ? "complete" : "incomplete";
}

function extractCompleteSequences(buffer: string): { sequences: string[]; remainder: string } {
  const sequences: string[] = [];
  let pos = 0;
  while (pos < buffer.length) {
    const remaining = buffer.slice(pos);
    if (remaining.startsWith(ESC)) {
      let seqEnd = 1;
      while (seqEnd <= remaining.length) {
        const candidate = remaining.slice(0, seqEnd);
        const status = isCompleteSequence(candidate);
        if (status === "complete") {
          sequences.push(candidate);
          pos += seqEnd;
          break;
        }
        if (status === "incomplete") {
          seqEnd++;
        } else {
          sequences.push(candidate);
          pos += seqEnd;
          break;
        }
      }
      if (seqEnd > remaining.length) return { sequences, remainder: remaining };
    } else {
      const codepoint = remaining.codePointAt(0);
      if (codepoint === undefined) return { sequences, remainder: "" };
      const char = String.fromCodePoint(codepoint);
      sequences.push(char);
      pos += char.length;
    }
  }
  return { sequences, remainder: "" };
}

function dataToString(data: string | Buffer): string {
  if (Buffer.isBuffer(data)) {
    if (data.length === 1 && data[0] > 127) {
      const byte = data[0] - 128;
      return `\x1b${String.fromCharCode(byte)}`;
    }
    return data.toString();
  }
  return data;
}

export function patchPiTuiStdinBuffer(): void {
  const ctor = StdinBuffer as unknown as StdinBufferConstructor;
  const proto = ctor.prototype;
  if (proto[PATCH_FLAG]) return;

  const originalEmit = proto.emit as RawEmit;
  const originalClear = proto.clear;
  const originalDestroy = proto.destroy;

  proto.process = function patchedProcess(this: StdinBufferRuntime, data: string | Buffer): void {
    if (Buffer.isBuffer(data)) {
      writeInputDebug("process", {
        isBuffer: true,
        hex: data.toString("hex"),
        utf8: data.toString("utf8"),
        length: data.length,
      });
    } else {
      writeInputDebug("process", { isBuffer: false, ...describeSequence(data) });
    }

    if (this.timeout) {
      clearTimeout(this.timeout);
      this.timeout = null;
    }

    const str = dataToString(data);
    this.timeoutMs = Math.max(this.timeoutMs, 100);
    if (!this.pasteMode && this.buffer.length === 0) {
      const strayArrowTail = takeStrayArrowTailPrefix(str);
      if (strayArrowTail !== undefined) {
        writeInputDebug("process:normalized-stray-arrow-tail", {
          from: describeSequence(str),
          to: describeSequence(strayArrowTail.normalized),
          rest: strayArrowTail.rest ? describeSequence(strayArrowTail.rest) : undefined,
        });
        this.emit("data", strayArrowTail.normalized);
        if (strayArrowTail.rest.length > 0) {
          this.process(strayArrowTail.rest);
        }
        return;
      }
    }

    if (str.length === 0 && this.buffer.length === 0) {
      this.emit("data", "");
      return;
    }

    this.buffer += str;
    if (this.pasteMode) {
      this.pasteBuffer += this.buffer;
      this.buffer = "";
      const endIndex = this.pasteBuffer.indexOf(BRACKETED_PASTE_END);
      if (endIndex !== -1) {
        const pastedContent = this.pasteBuffer.slice(0, endIndex);
        const remaining = this.pasteBuffer.slice(endIndex + BRACKETED_PASTE_END.length);
        this.pasteMode = false;
        this.pasteBuffer = "";
        clearPendingKittyPrintable(this);
        this.emit("paste", pastedContent);
        if (remaining.length > 0) this.process(remaining);
      }
      return;
    }

    const startIndex = this.buffer.indexOf(BRACKETED_PASTE_START);
    if (startIndex !== -1) {
      if (startIndex > 0) {
        const beforePaste = this.buffer.slice(0, startIndex);
        const result = extractCompleteSequences(beforePaste);
        for (const sequence of result.sequences) {
          this.emit("data", sequence);
        }
      }
      clearPendingKittyPrintable(this);
      this.buffer = this.buffer.slice(startIndex + BRACKETED_PASTE_START.length);
      this.pasteMode = true;
      this.pasteBuffer = this.buffer;
      this.buffer = "";
      const endIndex = this.pasteBuffer.indexOf(BRACKETED_PASTE_END);
      if (endIndex !== -1) {
        const pastedContent = this.pasteBuffer.slice(0, endIndex);
        const remaining = this.pasteBuffer.slice(endIndex + BRACKETED_PASTE_END.length);
        this.pasteMode = false;
        this.pasteBuffer = "";
        clearPendingKittyPrintable(this);
        this.emit("paste", pastedContent);
        if (remaining.length > 0) this.process(remaining);
      }
      return;
    }

    const result = extractCompleteSequences(this.buffer);
    this.buffer = result.remainder;
    for (const sequence of result.sequences) {
      this.emit("data", sequence);
    }
    if (this.buffer.length > 0) {
      this.timeout = setTimeout(() => {
        const flushed = this.flush();
        for (const sequence of flushed) {
          this.emit("data", sequence);
        }
      }, this.timeoutMs);
    }
  };

  proto.emit = function patchedEmit(
    this: StdinBufferRuntime,
    eventName: string | symbol,
    ...args: unknown[]
  ): boolean {
    if (eventName === "data" && typeof args[0] === "string") {
      const sequence = args[0];
      writeInputDebug("emit:data:before", describeSequence(sequence));
      if (isKittyKeyReleaseSequence(sequence)) {
        clearPendingKittyPrintable(this);
        writeInputDebug("emit:data:dropped-release", describeSequence(sequence));
        return false;
      }

      const normalizedLineFeed = normalizeLineFeedSubmit(sequence);
      if (normalizedLineFeed !== undefined) {
        clearPendingKittyPrintable(this);
        writeInputDebug("emit:data:normalized-line-feed", {
          from: describeSequence(sequence),
          to: describeSequence(normalizedLineFeed),
        });
        return originalEmit.call(this, eventName, normalizedLineFeed);
      }

      const normalizedStrayArrowTail = normalizeStrayArrowTail(sequence);
      if (normalizedStrayArrowTail !== undefined) {
        clearPendingKittyPrintable(this);
        writeInputDebug("emit:data:normalized-stray-arrow-tail", {
          from: describeSequence(sequence),
          to: describeSequence(normalizedStrayArrowTail),
        });
        return originalEmit.call(this, eventName, normalizedStrayArrowTail);
      }

      const normalizedFunctional = normalizeKittyFunctionalSequence(sequence);
      if (normalizedFunctional !== undefined) {
        writeInputDebug("emit:data:normalized", {
          from: describeSequence(sequence),
          to: describeSequence(normalizedFunctional),
        });
        return originalEmit.call(this, eventName, normalizedFunctional);
      }

      const rawCodepoint = sequenceCodepoint(sequence);
      if (
        rawCodepoint !== undefined &&
        rawCodepoint === this.__piPendingKittyPrintableCodepoint
      ) {
        clearPendingKittyPrintable(this);
        writeInputDebug("emit:data:dropped-duplicate", describeSequence(sequence));
        return false;
      }
      const kittyCodepoint = parseUnmodifiedKittyPrintableCodepoint(sequence);
      if (kittyCodepoint !== undefined) {
        rememberPendingKittyPrintable(this, kittyCodepoint);
      }
    } else if (eventName === "paste") {
      clearPendingKittyPrintable(this);
      if (typeof args[0] === "string") {
        writeInputDebug("emit:paste", describeSequence(args[0]));
      }
    }

    return originalEmit.call(this, eventName, ...args);
  } as typeof proto.emit;

  proto.clear = function patchedClear(this: StdinBufferRuntime): void {
    clearPendingKittyPrintable(this);
    return originalClear.call(this);
  };

  proto.destroy = function patchedDestroy(this: StdinBufferRuntime): void {
    clearPendingKittyPrintable(this);
    return originalDestroy.call(this);
  };

  proto[PATCH_FLAG] = true;
}

export function patchPiTuiTextRendering(): void {
  const ctor = Text as unknown as TextConstructor;
  const proto = ctor.prototype;
  if (proto[TEXT_RENDER_PATCH_FLAG]) return;

  const originalRender = proto.render;
  proto.render = function patchedRender(this: TextRuntime, width: number): string[] {
    const originalText = this.text;
    const truncatedText = truncateTextForRendering(originalText);
    if (truncatedText === originalText) {
      return originalRender.call(this, width);
    }

    this.text = truncatedText;
    this.cachedText = undefined;
    this.cachedWidth = undefined;
    this.cachedLines = undefined;
    try {
      return originalRender.call(this, width);
    } finally {
      this.text = originalText;
      this.cachedText = undefined;
      this.cachedWidth = undefined;
      this.cachedLines = undefined;
    }
  };

  proto[TEXT_RENDER_PATCH_FLAG] = true;
}

type ProcessTerminalRuntime = {
  [TERMINAL_PATCH_FLAG]?: boolean;
  setupStdinBuffer: () => void;
  stdinDataHandler?: (data: string | Buffer) => void;
  _kittyProtocolActive: boolean;
  _modifyOtherKeysActive: boolean;
  queryAndEnableKittyProtocol: () => void;
  stop: () => void;
};

type ProcessTerminalConstructor = {
  prototype: ProcessTerminalRuntime;
};

type TerminalResetOptions = {
  runStty?: boolean;
  restoreRawMode?: boolean;
};

export function resetTerminalModes(options: TerminalResetOptions = {}): void {
  try {
    process.stdout.write("\x1b[?2026l"); // synchronized output off
    process.stdout.write("\x1b[?2004l"); // bracketed paste off
    process.stdout.write("\x1b[<u"); // Kitty keyboard protocol off
    process.stdout.write("\x1b[>4;0m"); // xterm modifyOtherKeys off
    process.stdout.write("\x1b[?1l"); // normal cursor-key mode
    process.stdout.write("\x1b[?1000l\x1b[?1002l\x1b[?1003l\x1b[?1006l"); // mouse modes off
    process.stdout.write("\x1b[0m"); // reset text attributes
    process.stdout.write("\x1b(B"); // ASCII charset
    process.stdout.write("\x1b[?25h"); // cursor visible
  } catch {
    // ignore
  }

  if (options.restoreRawMode) {
    try {
      if (process.stdin.isTTY) {
        process.stdin.setRawMode?.(false);
      }
    } catch {
      // ignore
    }
  }

  if (options.runStty) {
    try {
      execSync("stty sane 2>/dev/null || true", { stdio: "ignore", timeout: 500 });
    } catch {
      // ignore
    }
    try {
      execSync("stty iutf8 2>/dev/null || true", { stdio: "ignore", timeout: 500 });
    } catch {
      // ignore
    }
  }
}

function installTerminalSafetyNet(): void {
  const processWithFlag = process as NodeJS.Process & { [TERMINAL_SAFETY_FLAG]?: boolean };
  if (processWithFlag[TERMINAL_SAFETY_FLAG]) return;
  processWithFlag[TERMINAL_SAFETY_FLAG] = true;

  process.stdin.on("error", (error: NodeJS.ErrnoException) => {
    if (error.code === "EIO") {
      resetTerminalModes({ restoreRawMode: true, runStty: true });
      return;
    }
    throw error;
  });
  process.on("exit", () => {
    resetTerminalModes();
  });
  process.on("SIGTERM", () => {
    resetTerminalModes({ restoreRawMode: true, runStty: true });
    process.exit(143);
  });
  process.on("uncaughtException", (error) => {
    resetTerminalModes({ restoreRawMode: true, runStty: true });
    throw error;
  });
}

export function patchPiTuiProcessTerminalKeyboardProtocol(): void {
  const ctor = ProcessTerminal as unknown as ProcessTerminalConstructor;
  const proto = ctor.prototype;
  if (proto[TERMINAL_PATCH_FLAG]) return;

  const originalStop = proto.stop;

  proto.queryAndEnableKittyProtocol = function queryWithoutEnhancedKeyboard(
    this: ProcessTerminalRuntime,
  ): void {
    resetTerminalModes();
    process.stdout.write("\x1b[?2004h");

    this._kittyProtocolActive = false;
    this._modifyOtherKeysActive = false;
    setKittyProtocolActive(false);
    this.setupStdinBuffer();
    if (this.stdinDataHandler) {
      process.stdin.on("data", this.stdinDataHandler);
    }
  };

  proto.stop = function patchedStop(this: ProcessTerminalRuntime): void {
    try {
      originalStop.call(this);
    } finally {
      resetTerminalModes({ restoreRawMode: true, runStty: true });
    }
  };

  proto[TERMINAL_PATCH_FLAG] = true;
}

patchPiTuiStdinBuffer();
patchPiTuiTextRendering();
patchPiTuiProcessTerminalKeyboardProtocol();
installTerminalSafetyNet();
