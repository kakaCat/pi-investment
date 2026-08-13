import { describe, it, expect, jest, beforeEach, afterEach } from '@jest/globals';
import { createRecallAuditPort } from './audit-v2-client.js';
import { mkdir, rm, readFile } from 'node:fs/promises';
import { join } from 'node:path';
import { tmpdir } from 'node:os';

describe('createRecallAuditPort', () => {
  let tempDir: string;
  let originalEnv: NodeJS.ProcessEnv;
  let originalFetch: typeof global.fetch;

  beforeEach(async () => {
    // Create temp directory for tests
    tempDir = join(tmpdir(), `recall-audit-test-${Date.now()}`);
    await mkdir(tempDir, { recursive: true });

    // Save and override environment
    originalEnv = { ...process.env };
    process.env.PI_INVEST_DIR = tempDir;
    process.env.QUANTSYS_V2_API_URL = 'http://test-v2-api:5001';

    // Save original fetch
    originalFetch = global.fetch;
  });

  afterEach(async () => {
    // Restore environment
    process.env = originalEnv;

    // Restore fetch
    global.fetch = originalFetch;

    // Clean up temp directory
    try {
      await rm(tempDir, { recursive: true, force: true });
    } catch (err) {
      // Ignore cleanup errors
    }
  });

  it('should write to V2 API on success', async () => {
    const mockFetch = jest.fn<typeof fetch>().mockResolvedValue({
      ok: true,
      status: 201,
    } as Response);
    global.fetch = mockFetch as any;

    const port = createRecallAuditPort();
    await port.record({
      ts: '2026-08-13T10:00:00Z',
      sessionId: 'sess-123',
      flow: 'interactive-chat',
      queryText: 'test query',
      strategy: 'hybrid',
      degraded: false,
      gateResult: 'passed',
      hits: [
        { memoryId: 1, score: 0.85, source: 'vector', vectorScore: 0.85 },
        { memoryId: 2, score: 0.75, source: 'both', bm25Score: 12.3, vectorScore: 0.75 },
      ],
    });

    expect(mockFetch).toHaveBeenCalledTimes(1);
    expect(mockFetch).toHaveBeenCalledWith(
      'http://test-v2-api:5001/api/memory/recall-audit',
      expect.objectContaining({
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: expect.any(String),
      })
    );

    const callArgs = mockFetch.mock.calls[0] as any[];
    const body = JSON.parse(callArgs[1].body);
    expect(body).toEqual({
      ts: '2026-08-13T10:00:00Z',
      session_id: 'sess-123',
      flow: 'interactive-chat',
      query_text: 'test query',
      strategy: 'hybrid',
      degraded: false,
      gate_result: 'passed',
      suppress_reason: undefined,
      hits: [
        { memory_id: 1, score: 0.85, source: 'vector', vector_score: 0.85, bm25_score: undefined },
        { memory_id: 2, score: 0.75, source: 'both', bm25_score: 12.3, vector_score: 0.75 },
      ],
    });

    // JSONL file should not exist
    const jsonlPath = join(tempDir, 'recall-audit.jsonl');
    await expect(readFile(jsonlPath, 'utf-8')).rejects.toThrow();
  });

  it('should fall back to JSONL when fetch rejects', async () => {
    const mockFetch = jest.fn<typeof fetch>().mockRejectedValue(new Error('Network error'));
    global.fetch = mockFetch as any;

    const port = createRecallAuditPort();
    await port.record({
      ts: '2026-08-13T10:00:00Z',
      sessionId: 'sess-456',
      flow: 'skill-invocation',
      queryText: 'fallback test',
      strategy: 'vector',
      degraded: true,
      gateResult: 'suppressed',
      suppressReason: 'empty-result',
      hits: [],
    });

    expect(mockFetch).toHaveBeenCalledTimes(1);

    // JSONL file should have the record
    const jsonlPath = join(tempDir, 'recall-audit.jsonl');
    const content = await readFile(jsonlPath, 'utf-8');
    const lines = content.trim().split('\n');
    expect(lines).toHaveLength(1);

    const record = JSON.parse(lines[0]);
    expect(record).toEqual({
      ts: '2026-08-13T10:00:00Z',
      sessionId: 'sess-456',
      flow: 'skill-invocation',
      queryText: 'fallback test',
      strategy: 'vector',
      degraded: true,
      gateResult: 'suppressed',
      suppressReason: 'empty-result',
      hits: [],
    });
  });

  it('should not throw when both V2 and JSONL fail', async () => {
    const mockFetch = jest.fn<typeof fetch>().mockRejectedValue(new Error('Network error'));
    global.fetch = mockFetch as any;

    // Make JSONL fail by setting PI_INVEST_DIR to an invalid path
    process.env.PI_INVEST_DIR = '/nonexistent/invalid/path/that/cannot/be/created';

    const port = createRecallAuditPort();

    // Should not throw — fire-and-forget contract
    await expect(port.record({
      ts: '2026-08-13T10:00:00Z',
      flow: 'scheduled-task',
      queryText: 'double failure',
      strategy: 'bm25',
      degraded: false,
      gateResult: 'passed',
      hits: [{ memoryId: 99, score: 0.5, source: 'bm25' }],
    })).resolves.toBeUndefined();

    expect(mockFetch).toHaveBeenCalledTimes(1);
  });

  it('should handle V2 API non-ok response and fall back', async () => {
    const mockFetch = jest.fn<typeof fetch>().mockResolvedValue({
      ok: false,
      status: 500,
    } as Response);
    global.fetch = mockFetch as any;

    const port = createRecallAuditPort();
    await port.record({
      ts: '2026-08-13T10:00:00Z',
      flow: 'wake-event',
      queryText: 'server error test',
      strategy: 'hybrid',
      degraded: false,
      gateResult: 'passed',
      hits: [{ memoryId: 10, score: 0.6, source: 'vector', vectorScore: 0.6 }],
    });

    expect(mockFetch).toHaveBeenCalledTimes(1);

    // Should have fallen back to JSONL
    const jsonlPath = join(tempDir, 'recall-audit.jsonl');
    const content = await readFile(jsonlPath, 'utf-8');
    expect(content.trim()).not.toBe('');
  });

  it('should respect 3s timeout', async () => {
    let aborted = false;
    const mockFetch = jest.fn<typeof fetch>().mockImplementation((url, init) => {
      return new Promise((resolve, reject) => {
        const signal = init?.signal as AbortSignal;
        if (signal) {
          signal.addEventListener('abort', () => {
            aborted = true;
            reject(new Error('aborted'));
          });
        }
        // Never resolve to simulate hanging request
      });
    });
    global.fetch = mockFetch as any;

    const port = createRecallAuditPort();

    const startTime = Date.now();
    await port.record({
      ts: '2026-08-13T10:00:00Z',
      flow: 'interactive-chat',
      queryText: 'timeout test',
      strategy: 'hybrid',
      degraded: false,
      gateResult: 'passed',
      hits: [],
    });
    const elapsed = Date.now() - startTime;

    // Should abort around 3000ms and fall back to JSONL quickly
    expect(elapsed).toBeLessThan(3500);
    expect(aborted).toBe(true);

    // JSONL should have the record
    const jsonlPath = join(tempDir, 'recall-audit.jsonl');
    const content = await readFile(jsonlPath, 'utf-8');
    expect(content.trim()).not.toBe('');
  });
});
