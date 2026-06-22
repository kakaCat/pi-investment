import { mkdtemp, readFile, readdir, rm } from 'fs/promises';
import { jest } from '@jest/globals';
import os from 'os';
import path from 'path';

import { JobAlertService, JobAlertNotifier } from './job-alert-service.js';

describe('JobAlertService', () => {
  const fixedNow = new Date('2026-05-19T10:30:00.000Z');

  it('formats job failure alerts for the notifier', async () => {
    const notifier = createNotifier();
    const service = new JobAlertService(notifier, { now: () => fixedNow });

    await service.alertJobFailure({
      jobType: 'daily-signal',
      jobId: 'job-123',
      status: 'failed',
      error: new Error('model timeout'),
    });

    expect(notifier.notify).toHaveBeenCalledWith(
      '[JOB_FAILURE] jobType=daily-signal jobId=job-123 status=failed error=model timeout timestamp=2026-05-19T10:30:00.000Z',
    );
  });

  it('formats stale artifact alerts', async () => {
    const notifier = createNotifier();
    const service = new JobAlertService(notifier, { now: () => fixedNow });

    await service.alertStaleData({
      id: 'prices:CN',
      lastUpdatedAt: '2026-05-18T00:00:00.000Z',
      maxAge: '6h',
    });
    await service.alertStaleModel({
      id: 'risk-v2',
      detectedAt: '2026-05-19T10:00:00.000Z',
    });
    await service.alertStaleReport({
      id: 'daily-pnl',
    });

    expect(notifier.notify).toHaveBeenNthCalledWith(
      1,
      '[STALE_ARTIFACT] artifactType=data id=prices:CN maxAge=6h lastUpdatedAt=2026-05-18T00:00:00.000Z detectedAt=2026-05-19T10:30:00.000Z',
    );
    expect(notifier.notify).toHaveBeenNthCalledWith(
      2,
      '[STALE_ARTIFACT] artifactType=model id=risk-v2 detectedAt=2026-05-19T10:00:00.000Z',
    );
    expect(notifier.notify).toHaveBeenNthCalledWith(
      3,
      '[STALE_ARTIFACT] artifactType=report id=daily-pnl detectedAt=2026-05-19T10:30:00.000Z',
    );
  });

  it('formats zero signal anomaly alerts', async () => {
    const notifier = createNotifier();
    const service = new JobAlertService(notifier, { now: () => fixedNow });

    await service.alertZeroSignalAnomaly({
      jobType: 'signal-generation',
      jobId: 'job-456',
      signalCount: 0,
    });

    expect(notifier.notify).toHaveBeenCalledWith(
      '[ZERO_SIGNAL_ANOMALY] jobType=signal-generation jobId=job-456 signalCount=0 timestamp=2026-05-19T10:30:00.000Z',
    );
  });

  it('writes a fallback alert file when the notifier throws', async () => {
    const alertDirectory = await mkdtemp(path.join(os.tmpdir(), 'job-alerts-'));
    const notifier = createNotifier();
    notifier.notify.mockRejectedValueOnce(new Error('feishu unavailable'));
    const service = new JobAlertService(notifier, {
      alertDirectory,
      now: () => fixedNow,
    });

    try {
      await service.alertJobFailure({
        jobType: 'report',
        jobId: 'job-789',
        status: 'failed',
        error: 'render failed',
      });

      const files = await readdir(alertDirectory);
      expect(files).toHaveLength(1);
      expect(files[0]).toMatch(/^2026-05-19T10-30-00-000Z-[a-z0-9]{8}\.log$/);

      const content = await readFile(path.join(alertDirectory, files[0]), 'utf8');
      expect(content).toContain('createdAt=2026-05-19T10:30:00.000Z');
      expect(content).toContain('notifyError=feishu unavailable');
      expect(content).toContain(
        'message=[JOB_FAILURE] jobType=report jobId=job-789 status=failed error=render failed timestamp=2026-05-19T10:30:00.000Z',
      );
    } finally {
      await rm(alertDirectory, { recursive: true, force: true });
    }
  });
});

function createNotifier(): JobAlertNotifier & { notify: jest.MockedFunction<JobAlertNotifier['notify']> } {
  const notify = jest.fn<() => Promise<void>>().mockResolvedValue(undefined);
  return {
    notify: notify as jest.MockedFunction<JobAlertNotifier['notify']>,
  };
}
