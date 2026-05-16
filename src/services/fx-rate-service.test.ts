import { describe, test, expect, beforeEach, afterEach } from "@jest/globals";
import { FxRateService } from "./fx-rate-service.js";
import { mkdirSync, rmSync, existsSync } from "fs";
import { join } from "path";

const TEST_DIR = join(process.cwd(), ".test-fx-rates");

describe("FxRateService", () => {
  beforeEach(() => {
    if (existsSync(TEST_DIR)) rmSync(TEST_DIR, { recursive: true });
    mkdirSync(TEST_DIR, { recursive: true });
  });

  afterEach(() => {
    if (existsSync(TEST_DIR)) rmSync(TEST_DIR, { recursive: true });
  });

  test("initializes with empty cache file", () => {
    const service = new FxRateService(TEST_DIR);
    const cachePath = join(TEST_DIR, "fx-rates.json");
    expect(existsSync(cachePath)).toBe(true);
  });
});
