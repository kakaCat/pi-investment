import { mkdir, writeFile } from 'fs/promises';
import * as path from 'path';

export interface JobAlertNotifier {
  notify(message: string): Promise<void>;
}

export interface JobAlertServiceOptions {
  alertDirectory?: string;
  now?: () => Date;
}

export interface JobFailureAlert {
  jobType: string;
  jobId: string;
  status: string;
  error?: unknown;
  timestamp?: Date | string;
}

export interface StaleArtifactAlert {
  artifactType: 'data' | 'model' | 'report';
  id: string;
  lastUpdatedAt?: Date | string;
  detectedAt?: Date | string;
  maxAge?: string;
}

export interface ZeroSignalAnomalyAlert {
  jobType: string;
  jobId: string;
  signalCount: number;
  timestamp?: Date | string;
}

export class JobAlertService {
  private readonly alertDirectory: string;
  private readonly now: () => Date;

  constructor(
    private readonly notifier: JobAlertNotifier,
    options: JobAlertServiceOptions = {},
  ) {
    this.alertDirectory = options.alertDirectory ?? path.join('.pi-invest', 'alerts');
    this.now = options.now ?? (() => new Date());
  }

  async alertJobFailure(alert: JobFailureAlert): Promise<void> {
    await this.send(
      [
        '[JOB_FAILURE]',
        `jobType=${alert.jobType}`,
        `jobId=${alert.jobId}`,
        `status=${alert.status}`,
        `error=${formatError(alert.error)}`,
        `timestamp=${formatDate(alert.timestamp ?? this.now())}`,
      ].join(' '),
    );
  }

  async alertStaleData(alert: Omit<StaleArtifactAlert, 'artifactType'>): Promise<void> {
    await this.alertStaleArtifact({ ...alert, artifactType: 'data' });
  }

  async alertStaleModel(alert: Omit<StaleArtifactAlert, 'artifactType'>): Promise<void> {
    await this.alertStaleArtifact({ ...alert, artifactType: 'model' });
  }

  async alertStaleReport(alert: Omit<StaleArtifactAlert, 'artifactType'>): Promise<void> {
    await this.alertStaleArtifact({ ...alert, artifactType: 'report' });
  }

  async alertZeroSignalAnomaly(alert: ZeroSignalAnomalyAlert): Promise<void> {
    await this.send(
      [
        '[ZERO_SIGNAL_ANOMALY]',
        `jobType=${alert.jobType}`,
        `jobId=${alert.jobId}`,
        `signalCount=${alert.signalCount}`,
        `timestamp=${formatDate(alert.timestamp ?? this.now())}`,
      ].join(' '),
    );
  }

  private async alertStaleArtifact(alert: StaleArtifactAlert): Promise<void> {
    await this.send(
      [
        '[STALE_ARTIFACT]',
        `artifactType=${alert.artifactType}`,
        `id=${alert.id}`,
        alert.maxAge ? `maxAge=${alert.maxAge}` : undefined,
        alert.lastUpdatedAt ? `lastUpdatedAt=${formatDate(alert.lastUpdatedAt)}` : undefined,
        `detectedAt=${formatDate(alert.detectedAt ?? this.now())}`,
      ]
        .filter(Boolean)
        .join(' '),
    );
  }

  private async send(message: string): Promise<void> {
    try {
      await this.notifier.notify(message);
    } catch (error) {
      await this.writeFallbackAlert(message, error);
    }
  }

  private async writeFallbackAlert(message: string, error: unknown): Promise<void> {
    await mkdir(this.alertDirectory, { recursive: true });

    const createdAt = this.now();
    const filename = `${toFileTimestamp(createdAt)}-${Math.random().toString(36).slice(2, 10)}.log`;
    const body = [
      `createdAt=${formatDate(createdAt)}`,
      `notifyError=${formatError(error)}`,
      `message=${message}`,
      '',
    ].join('\n');

    await writeFile(path.join(this.alertDirectory, filename), body, 'utf8');
  }
}

function formatDate(value: Date | string): string {
  return value instanceof Date ? value.toISOString() : value;
}

function formatError(error: unknown): string {
  if (error instanceof Error) {
    return error.message;
  }

  if (typeof error === 'string') {
    return error;
  }

  if (error === undefined || error === null) {
    return 'unknown';
  }

  try {
    return JSON.stringify(error);
  } catch {
    return String(error);
  }
}

function toFileTimestamp(value: Date): string {
  return value.toISOString().replace(/[:.]/g, '-');
}
