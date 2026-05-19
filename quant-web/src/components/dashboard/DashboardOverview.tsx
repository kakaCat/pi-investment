import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import type { CSSProperties } from 'react';
import { Alert, Button, Col, Row, Space, Typography, message } from 'antd';
import {
  CheckCircleOutlined,
  ClockCircleOutlined,
  DatabaseOutlined,
  ReloadOutlined,
  WarningOutlined,
} from '@ant-design/icons';
import type {
  BacktestSummary,
  DashboardSignal,
  HealthStatus,
  JobRecord,
  PlatformStatus,
  StockDataStatus,
  TrainingRecord,
} from '../../dashboard/dashboardTypes';
import {
  calculateBacktestMetrics,
  calculateDataQualityMetrics,
  calculateJobMetrics,
  calculateSignalMetrics,
  getLatestTrainingRecord,
} from '../../dashboard/dashboardMetrics';
import BacktestSummaryPanel from './BacktestSummaryPanel';
import DataQualityPanel from './DataQualityPanel';
import JobQueuePanel from './JobQueuePanel';
import MetricCard from './MetricCard';
import ModelSummaryPanel from './ModelSummaryPanel';
import PlatformStatusPanel from './PlatformStatusPanel';
import SignalSummaryPanel from './SignalSummaryPanel';
import TaskActionPanel from './TaskActionPanel';

const { Text, Title } = Typography;

const opsApiToken = import.meta.env.VITE_OPS_API_TOKEN as string | undefined;

function buildOpsHeaders(baseHeaders: Record<string, string> = {}) {
  return opsApiToken ? { ...baseHeaders, Authorization: `Bearer ${opsApiToken}` } : baseHeaders;
}

type DashboardPanelKey =
  | 'health'
  | 'platformStatus'
  | 'jobs'
  | 'signals'
  | 'backtests'
  | 'trainingHistory'
  | 'dataStatus';

type DashboardErrors = Partial<Record<DashboardPanelKey, string>>;

interface JobsResponse {
  success: boolean;
  jobs: JobRecord[];
  error?: string;
  warning?: string;
}

interface PlatformStatusResponse {
  success: boolean;
  data?: PlatformStatus;
  error?: string;
}

interface SignalsResponse {
  signals: DashboardSignal[];
  count: number;
}

interface BacktestResultsResponse {
  count: number;
  summary: BacktestSummary[];
}

interface TrainingHistoryResponse {
  history: TrainingRecord[];
  error?: string;
}

interface DashboardOverviewProps {
  onNavigate?: (key: string) => void;
}

const PANEL_LABELS: Record<DashboardPanelKey, string> = {
  health: 'Health',
  platformStatus: 'Platform status',
  jobs: 'Jobs',
  signals: 'Signals',
  backtests: 'Backtests',
  trainingHistory: 'Training history',
  dataStatus: 'Data status',
};

const KNOWN_PLATFORM_CHECK_NAMES = ['database', 'signals', 'model', 'daily_report'] as const;

type KnownPlatformCheckName = (typeof KNOWN_PLATFORM_CHECK_NAMES)[number];
type PlatformPanelStatus = NonNullable<Parameters<typeof PlatformStatusPanel>[0]['status']>;

export default function DashboardOverview({ onNavigate = () => undefined }: DashboardOverviewProps) {
  const [health, setHealth] = useState<HealthStatus | undefined>();
  const [platformStatus, setPlatformStatus] = useState<PlatformStatus | undefined>();
  const [jobs, setJobs] = useState<JobRecord[]>([]);
  const [signals, setSignals] = useState<DashboardSignal[]>([]);
  const [backtests, setBacktests] = useState<BacktestSummary[]>([]);
  const [trainingHistory, setTrainingHistory] = useState<TrainingRecord[]>([]);
  const [dataStatus, setDataStatus] = useState<StockDataStatus | undefined>();
  const [loading, setLoading] = useState(false);
  const [errors, setErrors] = useState<DashboardErrors>({});
  const [lastRefreshed, setLastRefreshed] = useState<string | undefined>();
  const [actionLoading, setActionLoading] = useState<string | null>(null);
  const isMountedRef = useRef(false);
  const dashboardRequestIdRef = useRef(0);
  const jobsRequestIdRef = useRef(0);
  const jobsRequestInFlightRef = useRef(false);
  const jobsRequestPromiseRef = useRef<Promise<void> | null>(null);

  const loadDashboard = useCallback(async () => {
    const requestId = dashboardRequestIdRef.current + 1;
    dashboardRequestIdRef.current = requestId;
    const dashboardJobsRequestId = jobsRequestIdRef.current + 1;
    jobsRequestIdRef.current = dashboardJobsRequestId;

    if (isMountedRef.current) {
      setLoading(true);
    }

    const requests = await Promise.allSettled([
      fetchJson<HealthStatus>('/api/health'),
      fetchPlatformStatus(),
      fetchJobs(),
      fetchJson<SignalsResponse>('/api/signals?days=30'),
      fetchJson<BacktestResultsResponse>('/api/backtest/results'),
      fetchTrainingHistory(),
      fetchJson<StockDataStatus>('/api/stocks/data-status'),
    ]);

    if (!isMountedRef.current || requestId !== dashboardRequestIdRef.current) {
      return;
    }

    const nextErrors: DashboardErrors = {};

    applySettledResult(requests[0], 'health', nextErrors, (value) => {
      setHealth(value);
    });
    applySettledResult(requests[1], 'platformStatus', nextErrors, (value) => {
      setPlatformStatus(value);
    });
    applySettledResult(requests[2], 'jobs', nextErrors, (value) => {
      if (jobsRequestIdRef.current === dashboardJobsRequestId) {
        setJobs(value);
      }
    });
    applySettledResult(requests[3], 'signals', nextErrors, (value) => {
      setSignals(value.signals);
    });
    applySettledResult(requests[4], 'backtests', nextErrors, (value) => {
      setBacktests(value.summary);
    });
    applySettledResult(requests[5], 'trainingHistory', nextErrors, (value) => {
      setTrainingHistory(value);
    });
    applySettledResult(requests[6], 'dataStatus', nextErrors, (value) => {
      setDataStatus(value);
    });

    setErrors(nextErrors);
    setLastRefreshed(new Date().toISOString());
    setLoading(false);
  }, []);

  const refreshJobs = useCallback(async (options: { queueAfterCurrent?: boolean } = {}) => {
    if (jobsRequestInFlightRef.current) {
      if (!options.queueAfterCurrent) {
        return;
      }
      await jobsRequestPromiseRef.current;
      if (!isMountedRef.current) {
        return;
      }
    }

    const requestId = jobsRequestIdRef.current + 1;
    jobsRequestIdRef.current = requestId;
    jobsRequestInFlightRef.current = true;

    const requestPromise = (async () => {
      const nextJobs = await fetchJobs();
      if (!isMountedRef.current || requestId !== jobsRequestIdRef.current) {
        return;
      }
      setJobs(nextJobs);
      setErrors((currentErrors) => removePanelError(currentErrors, 'jobs'));
    })();

    jobsRequestPromiseRef.current = requestPromise;

    try {
      await requestPromise;
    } catch (error) {
      if (!isMountedRef.current || requestId !== jobsRequestIdRef.current) {
        return;
      }
      setErrors((currentErrors) => ({
        ...currentErrors,
        jobs: getErrorMessage(error),
      }));
    } finally {
      if (requestId === jobsRequestIdRef.current) {
        jobsRequestPromiseRef.current = null;
      }
      jobsRequestInFlightRef.current = false;
    }
  }, []);

  useEffect(() => {
    isMountedRef.current = true;
    void loadDashboard();

    return () => {
      isMountedRef.current = false;
    };
  }, [loadDashboard]);

  const hasActiveJobs = useMemo(
    () => jobs.some((job) => job.status === 'queued' || job.status === 'running'),
    [jobs],
  );

  useEffect(() => {
    if (!hasActiveJobs) {
      return undefined;
    }

    const intervalId = window.setInterval(() => {
      void refreshJobs();
    }, 3000);

    return () => window.clearInterval(intervalId);
  }, [hasActiveJobs, refreshJobs]);

  const handleRunTask = useCallback(
    async (type: string, params: Record<string, unknown>) => {
      setActionLoading(type);
      try {
        await postJobAction(`/api/jobs/${encodeURIComponent(type)}/run`, params);
        if (!isMountedRef.current) {
          return;
        }
        message.success('Task queued');
        await refreshJobs({ queueAfterCurrent: true });
      } catch (error) {
        if (isMountedRef.current) {
          message.error(getErrorMessage(error));
        }
      } finally {
        if (isMountedRef.current) {
          setActionLoading(null);
        }
      }
    },
    [refreshJobs],
  );

  const handleRetryJob = useCallback(
    async (job: JobRecord) => {
      setActionLoading(job.id);
      try {
        await postJobAction(`/api/jobs/${encodeURIComponent(job.id)}/retry`);
        if (!isMountedRef.current) {
          return;
        }
        message.success('Job retry queued');
        await refreshJobs({ queueAfterCurrent: true });
      } catch (error) {
        if (isMountedRef.current) {
          message.error(getErrorMessage(error));
        }
      } finally {
        if (isMountedRef.current) {
          setActionLoading(null);
        }
      }
    },
    [refreshJobs],
  );

  const handleCancelJob = useCallback(
    async (job: JobRecord) => {
      setActionLoading(job.id);
      try {
        await postJobAction(`/api/jobs/${encodeURIComponent(job.id)}/cancel`);
        if (!isMountedRef.current) {
          return;
        }
        message.success('Job cancellation requested');
        await refreshJobs({ queueAfterCurrent: true });
      } catch (error) {
        if (isMountedRef.current) {
          message.error(getErrorMessage(error));
        }
      } finally {
        if (isMountedRef.current) {
          setActionLoading(null);
        }
      }
    },
    [refreshJobs],
  );

  const signalMetrics = useMemo(() => calculateSignalMetrics(signals), [signals]);
  const backtestMetrics = useMemo(() => calculateBacktestMetrics(backtests), [backtests]);
  const jobMetrics = useMemo(() => calculateJobMetrics(jobs), [jobs]);
  const dataQualityMetrics = useMemo(() => calculateDataQualityMetrics(dataStatus), [dataStatus]);
  const latestTraining = useMemo(() => getLatestTrainingRecord(trainingHistory), [trainingHistory]);
  const platformPanelStatus = useMemo(() => adaptPlatformStatusForPanel(platformStatus), [platformStatus]);
  const activeJobTypes = useMemo(
    () => new Set(jobs.filter((job) => job.status === 'queued' || job.status === 'running').map((job) => job.type)),
    [jobs],
  );
  const failedPanelLabels = useMemo(
    () => Object.keys(errors).map((key) => PANEL_LABELS[key as DashboardPanelKey]),
    [errors],
  );

  return (
    <Space direction="vertical" size="middle" style={{ width: '100%' }}>
      <div style={headerStyle}>
        <Space direction="vertical" size={2}>
          <Title level={3} style={{ margin: 0 }}>
            Dashboard Overview
          </Title>
          <Text type="secondary">
            Last refreshed: {lastRefreshed ? formatDateTime(lastRefreshed) : 'Never'}
          </Text>
        </Space>
        <Button icon={<ReloadOutlined />} loading={loading} onClick={() => void loadDashboard()}>
          Refresh
        </Button>
      </div>

      {failedPanelLabels.length > 0 && (
        <Alert
          type="warning"
          showIcon
          message="Showing partial dashboard data"
          description={`Unable to load: ${failedPanelLabels.join(', ')}`}
        />
      )}

      <Row gutter={[16, 16]}>
        <Col xs={24} sm={12} xl={6}>
          <MetricCard
            title="Health"
            value={formatHealthValue(health)}
            prefix={health?.status === 'ok' ? <CheckCircleOutlined /> : <WarningOutlined />}
            tone={getHealthTone(health)}
            loading={loading && !health}
            helper={health ? `DB ${health.db_connected ? 'connected' : 'offline'} · Model ${health.model_loaded ? 'loaded' : 'missing'}` : 'No health data'}
          />
        </Col>
        <Col xs={24} sm={12} xl={6}>
          <MetricCard
            title="Signals"
            value={signalMetrics.total}
            tone="info"
            loading={loading && signals.length === 0}
            helper={`${signalMetrics.buyCount} buy · ${signalMetrics.sellCount} sell`}
          />
        </Col>
        <Col xs={24} sm={12} xl={6}>
          <MetricCard
            title="Backtests"
            value={backtestMetrics.count}
            tone={getReturnTone(backtestMetrics.averageReturn)}
            loading={loading && backtests.length === 0}
            helper={`Avg return ${formatPercent(backtestMetrics.averageReturn)}`}
          />
        </Col>
        <Col xs={24} sm={12} xl={6}>
          <MetricCard
            title="Jobs"
            value={jobMetrics.activeCount}
            suffix="active"
            prefix={<ClockCircleOutlined />}
            tone={jobMetrics.failedCount > 0 ? 'warning' : 'default'}
            loading={loading && jobs.length === 0}
            helper={`${jobMetrics.failedCount} failed · ${jobMetrics.total} total`}
          />
        </Col>
        <Col xs={24} sm={12} xl={6}>
          <MetricCard
            title="Platform"
            value={formatPlatformStatus(platformStatus)}
            tone={getPlatformTone(platformStatus)}
            loading={loading && !platformStatus}
            helper={platformStatus ? `Generated ${formatDateTime(platformStatus.generated_at)}` : 'No platform status'}
          />
        </Col>
        <Col xs={24} sm={12} xl={6}>
          <MetricCard
            title="Data Quality"
            value={formatPercent(dataQualityMetrics.completenessRate)}
            prefix={<DatabaseOutlined />}
            tone={(dataQualityMetrics.completenessRate ?? 0) >= 0.95 ? 'success' : 'warning'}
            loading={loading && !dataStatus}
            helper={`${dataQualityMetrics.completeStocks}/${dataQualityMetrics.totalStocks} complete`}
          />
        </Col>
        <Col xs={24} sm={12} xl={6}>
          <MetricCard
            title="Model"
            value={latestTraining ? formatNumber(latestTraining.test_auc) : '-'}
            tone="info"
            loading={loading && trainingHistory.length === 0}
            helper={latestTraining ? `Test AUC · ${formatDateTime(latestTraining.timestamp)}` : 'No training history'}
          />
        </Col>
        <Col xs={24} sm={12} xl={6}>
          <MetricCard
            title="Database"
            value={health?.db_info?.size_display || '-'}
            tone={health?.db_connected ? 'success' : 'danger'}
            loading={loading && !health}
            helper={health?.db_info?.path || 'Database metadata unavailable'}
          />
        </Col>
      </Row>

      <Row gutter={[16, 16]}>
        <Col xs={24} xl={8}>
          <SignalSummaryPanel
            signals={signals}
            loading={loading && signals.length === 0}
            error={errors.signals}
            onOpenSignals={() => onNavigate('signals')}
          />
        </Col>
        <Col xs={24} xl={8}>
          <BacktestSummaryPanel
            summary={backtests}
            loading={loading && backtests.length === 0}
            error={errors.backtests}
            onOpenBacktest={() => onNavigate('backtest')}
          />
        </Col>
        <Col xs={24} xl={8}>
          <TaskActionPanel
            activeJobTypes={activeJobTypes}
            actionLoading={actionLoading}
            onRunTask={handleRunTask}
          />
        </Col>
      </Row>

      <Row gutter={[16, 16]}>
        <Col xs={24} xl={12} xxl={6}>
          <PlatformStatusPanel
            status={platformPanelStatus}
            loading={loading && !platformStatus}
            error={errors.platformStatus}
          />
        </Col>
        <Col xs={24} xl={12} xxl={6}>
          <ModelSummaryPanel
            history={trainingHistory}
            loading={loading && trainingHistory.length === 0}
            error={errors.trainingHistory}
            onOpenTraining={() => onNavigate('model-training')}
          />
        </Col>
        <Col xs={24} xl={12} xxl={6}>
          <DataQualityPanel
            status={dataStatus}
            loading={loading && !dataStatus}
            error={errors.dataStatus}
            onOpenData={() => onNavigate('stock-list')}
          />
        </Col>
        <Col xs={24} xl={12} xxl={6}>
          <JobQueuePanel
            jobs={jobs}
            loading={loading && jobs.length === 0}
            error={errors.jobs}
            actionLoading={actionLoading}
            onRetry={handleRetryJob}
            onCancel={handleCancelJob}
            onOpenJobs={() => onNavigate('ops')}
          />
        </Col>
      </Row>
    </Space>
  );
}

async function fetchJson<T>(url: string, init?: RequestInit): Promise<T> {
  const response = await fetch(url, init);
  const contentType = response.headers.get('content-type') || '';
  const text = await response.text();
  const hasBody = text.trim().length > 0;
  const isJson = contentType.toLowerCase().includes('json');
  let body: unknown;

  if (hasBody && isJson) {
    try {
      body = JSON.parse(text);
    } catch (error) {
      throw new Error(`Invalid JSON response from ${url}: ${getErrorMessage(error)}`);
    }
  }

  if (!response.ok) {
    const detail = extractApiError(body) || getTextSnippet(text);
    throw new Error(detail ? `Request failed with ${response.status}: ${detail}` : `Request failed with ${response.status}`);
  }

  if (!hasBody) {
    throw new Error(`Expected JSON response from ${url}, received an empty response`);
  }

  if (!isJson) {
    throw new Error(`Expected JSON response from ${url}, received ${contentType || 'unknown content type'}`);
  }

  return body as T;
}

async function fetchPlatformStatus() {
  const response = await fetchJson<PlatformStatusResponse>('/api/platform/status');
  if (!response.success || !response.data) {
    throw new Error(response.error || 'Platform status response was unsuccessful');
  }
  return response.data;
}

async function fetchJobs() {
  const response = await fetchJson<JobsResponse>('/api/jobs');
  if (!response.success) {
    throw new Error(response.error || response.warning || 'Jobs response was unsuccessful');
  }
  return response.jobs;
}

async function fetchTrainingHistory() {
  const response = await fetchJson<TrainingHistoryResponse>('/api/training/history');
  if (response.error) {
    throw new Error(response.error);
  }
  return response.history;
}

async function postJobAction(url: string, body?: Record<string, unknown>) {
  await fetchJson<unknown>(url, {
    method: 'POST',
    headers: buildOpsHeaders(body ? { 'Content-Type': 'application/json' } : {}),
    body: body ? JSON.stringify(body) : undefined,
  });
}

function applySettledResult<T>(
  result: PromiseSettledResult<T>,
  key: DashboardPanelKey,
  nextErrors: DashboardErrors,
  onSuccess: (value: T) => void,
) {
  if (result.status === 'fulfilled') {
    onSuccess(result.value);
    return;
  }

  nextErrors[key] = getErrorMessage(result.reason);
}

function removePanelError(errors: DashboardErrors, key: DashboardPanelKey) {
  if (!errors[key]) {
    return errors;
  }

  const rest = { ...errors };
  delete rest[key];
  return rest;
}

function extractApiError(body: unknown) {
  if (body && typeof body === 'object') {
    const maybeError = 'error' in body ? body.error : undefined;
    const maybeMessage = 'message' in body ? body.message : undefined;
    if (typeof maybeError === 'string') {
      return maybeError;
    }
    if (typeof maybeMessage === 'string') {
      return maybeMessage;
    }
  }
  return undefined;
}

function getTextSnippet(text: string) {
  const snippet = text.replace(/\s+/g, ' ').trim().slice(0, 180);
  return snippet.length > 0 ? snippet : undefined;
}

function getErrorMessage(error: unknown) {
  return error instanceof Error ? error.message : String(error);
}

function adaptPlatformStatusForPanel(status?: PlatformStatus): PlatformPanelStatus | undefined {
  if (!status) {
    return undefined;
  }

  const checks = status.checks.filter(isKnownPlatformCheck);
  return {
    overall_status: status.overall_status,
    generated_at: status.generated_at,
    checks,
  };
}

function isKnownPlatformCheck(
  check: PlatformStatus['checks'][number],
): check is PlatformStatus['checks'][number] & { name: KnownPlatformCheckName } {
  return (KNOWN_PLATFORM_CHECK_NAMES as readonly string[]).includes(check.name);
}

function getHealthTone(health?: HealthStatus) {
  if (!health) {
    return 'default';
  }
  return health.status === 'ok' && health.db_connected && health.model_loaded ? 'success' : 'warning';
}

function getPlatformTone(status?: PlatformStatus) {
  if (!status) {
    return 'default';
  }
  if (status.overall_status === 'healthy') {
    return 'success';
  }
  return status.overall_status === 'degraded' ? 'warning' : 'danger';
}

function getReturnTone(value?: number) {
  if (typeof value !== 'number') {
    return 'default';
  }
  return value >= 0 ? 'success' : 'danger';
}

function formatHealthValue(health?: HealthStatus) {
  if (!health) {
    return '-';
  }
  return health.status.toUpperCase();
}

function formatPlatformStatus(status?: PlatformStatus) {
  if (!status) {
    return '-';
  }
  return status.overall_status.replace('_', ' ').toUpperCase();
}

function formatPercent(value?: number) {
  return typeof value === 'number' && Number.isFinite(value) ? `${(value * 100).toFixed(1)}%` : '-';
}

function formatNumber(value?: number) {
  return typeof value === 'number' && Number.isFinite(value) ? value.toFixed(3) : '-';
}

function formatDateTime(value: string) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return date.toLocaleString('zh-CN', { hour12: false });
}

const headerStyle: CSSProperties = {
  alignItems: 'center',
  display: 'flex',
  gap: 16,
  justifyContent: 'space-between',
};
