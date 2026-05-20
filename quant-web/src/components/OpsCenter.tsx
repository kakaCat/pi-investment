import React, { useEffect, useState } from 'react';
import {
  Alert,
  Button,
  Card,
  Col,
  Descriptions,
  Row,
  Space,
  Statistic,
  Table,
  Tag,
  Typography,
  Input,
  message
} from 'antd';
import {
  CheckCircleOutlined,
  CloseCircleOutlined,
  CloudServerOutlined,
  DatabaseOutlined,
  FileTextOutlined,
  FieldTimeOutlined,
  PlayCircleOutlined,
  ReloadOutlined,
  RobotOutlined,
  SignalFilled,
  SyncOutlined,
  WarningOutlined
} from '@ant-design/icons';
import type { ColumnsType } from 'antd/es/table';

const { Title, Text, Paragraph } = Typography;
const opsApiToken = import.meta.env.VITE_OPS_API_TOKEN as string | undefined;

type PlatformCheckName = 'database' | 'signals' | 'model' | 'daily_report';
type PlatformCheckStatus = 'healthy' | 'degraded' | 'unavailable';
type JobType =
  | 'data_update'
  | 'factor_compute'
  | 'signal_generate'
  | 'model_train'
  | 'backtest_run'
  | 'daily_report'
  | 'risk_check';
type JobStatus = 'queued' | 'running' | 'success' | 'failed' | 'cancelled';
type SchedulerRunStatus = 'triggered' | 'running' | 'success' | 'failed' | 'skipped' | 'missed' | 'compensated' | 'compensation_failed';
type SchedulerTriggerType = 'scheduled' | 'manual' | 'compensation';

interface PlatformStatusCheck {
  name: PlatformCheckName;
  status: PlatformCheckStatus;
  message: string;
  details?: Record<string, unknown>;
}

interface PlatformStatus {
  overall_status: PlatformCheckStatus;
  generated_at: string;
  checks: PlatformStatusCheck[];
}

interface JobRecord {
  id: string;
  type: JobType;
  status: JobStatus;
  params: Record<string, unknown>;
  logs: string[];
  attempts: number;
  createdAt: string;
  updatedAt: string;
  startedAt?: string;
  finishedAt?: string;
  result?: unknown;
  error?: string;
}

interface ApiResponse<T> {
  success: boolean;
  data?: T;
  error?: string;
}

interface JobsResponse {
  success: boolean;
  count: number;
  jobs: JobRecord[];
  error?: string;
  warning?: string;
}

interface SchedulerRun {
  id: string;
  taskId: string;
  taskName: string;
  scheduledFor: string;
  triggerType: SchedulerTriggerType;
  status: SchedulerRunStatus;
  triggeredAt?: string;
  startedAt?: string;
  finishedAt?: string;
  durationMs?: number;
  error?: string;
  compensationReason?: string;
  payload: Record<string, unknown>;
  createdAt: string;
  updatedAt: string;
}

interface SchedulerTask {
  id: string;
  name: string;
  enabled: boolean;
  scheduleKind: 'cron' | 'every' | 'at' | 'delay';
  scheduleExpr?: string;
  scheduleAt?: string;
  everySeconds?: number;
  delaySeconds?: number;
  payload: Record<string, unknown>;
  compensationEnabled: boolean;
  compensationCheckAfter?: string;
  compensationMaxAttempts: number;
  deleteAfterRun: boolean;
  nextRunAt: string | null;
  lastRun?: SchedulerRun;
  todayTriggered: boolean;
  todaySuccess: boolean;
  compensationDue: boolean;
}

interface SchedulerTasksResponse {
  success: boolean;
  tasks: SchedulerTask[];
  error?: string;
}

interface SchedulerRunsResponse {
  success: boolean;
  count?: number;
  runs: SchedulerRun[];
  error?: string;
}

interface BackupResult {
  backupDir: string;
  manifest: {
    created_at: string;
    copied: Array<{ source: string; backupPath: string; kind: string }>;
    skipped_missing: Array<{ source: string; reason: string }>;
    rootDir: string;
  };
}

interface RestorePlan {
  dryRun: true;
  backupDir: string;
  wouldRestore: Array<{ source: string; from: string; to: string; kind: string }>;
  skipped_missing: Array<{ source: string; reason: string }>;
}

interface RestoreResult {
  dryRun: false;
  backupDir: string;
  restored: Array<{ source: string; from: string; to: string; kind: string }>;
  skipped_missing: Array<{ source: string; reason: string }>;
}

interface TaskAction {
  type: JobType;
  title: string;
  description: string;
  params: Record<string, unknown>;
  danger?: boolean;
}

const TASK_ACTIONS: TaskAction[] = [
  {
    type: 'data_update',
    title: '数据更新',
    description: '调用 Python Quant API 更新最近行情数据',
    params: { source: 'hs300', days: 5, force: false }
  },
  {
    type: 'factor_compute',
    title: '因子计算',
    description: '重新计算本地因子数据',
    params: {}
  },
  {
    type: 'signal_generate',
    title: '信号生成',
    description: '基于最新数据生成内部研究信号',
    params: {}
  },
  {
    type: 'daily_report',
    title: '日报生成',
    description: '生成内部投研日报产物',
    params: {}
  },
  {
    type: 'risk_check',
    title: '风险检查',
    description: '执行当前组合/观察池风险检查',
    params: {}
  },
  {
    type: 'model_train',
    title: '模型训练',
    description: '触发模型重训，耗时较长',
    params: { days: 90, model: 'xgboost', cvSplits: 5 }
  },
  {
    type: 'backtest_run',
    title: '回测运行',
    description: '运行默认回测脚本，耗时较长',
    params: {},
    danger: true
  }
];

const CHECK_LABELS: Record<PlatformCheckName, string> = {
  database: '数据库',
  signals: '信号文件',
  model: '模型产物',
  daily_report: '日报产物'
};

const CHECK_ICONS: Record<PlatformCheckName, React.ReactNode> = {
  database: <DatabaseOutlined />,
  signals: <SignalFilled />,
  model: <RobotOutlined />,
  daily_report: <FileTextOutlined />
};

const STATUS_COLORS: Record<PlatformCheckStatus | JobStatus | SchedulerRunStatus, string> = {
  healthy: 'green',
  degraded: 'orange',
  unavailable: 'red',
  queued: 'default',
  running: 'processing',
  success: 'green',
  failed: 'red',
  cancelled: 'orange',
  triggered: 'blue',
  skipped: 'default',
  missed: 'red',
  compensated: 'purple',
  compensation_failed: 'red'
};

const STATUS_LABELS: Record<PlatformCheckStatus | JobStatus | SchedulerRunStatus, string> = {
  healthy: '正常',
  degraded: '降级',
  unavailable: '不可用',
  queued: '排队中',
  running: '运行中',
  success: '成功',
  failed: '失败',
  cancelled: '已取消',
  triggered: '已触发',
  skipped: '已跳过',
  missed: '未触发',
  compensated: '已补偿',
  compensation_failed: '补偿失败'
};

const OpsCenter: React.FC = () => {
  const [platformStatus, setPlatformStatus] = useState<PlatformStatus | null>(null);
  const [jobs, setJobs] = useState<JobRecord[]>([]);
  const [loadingStatus, setLoadingStatus] = useState(false);
  const [loadingJobs, setLoadingJobs] = useState(false);
  const [actionLoading, setActionLoading] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [jobsWarning, setJobsWarning] = useState<string | null>(null);
  const [schedulerTasks, setSchedulerTasks] = useState<SchedulerTask[]>([]);
  const [failedSchedulerRuns, setFailedSchedulerRuns] = useState<SchedulerRun[]>([]);
  const [latestBackup, setLatestBackup] = useState<BackupResult | null>(null);
  const [restorePlan, setRestorePlan] = useState<RestorePlan | null>(null);
  const [restoreBackupDir, setRestoreBackupDir] = useState('');
  const [restoreConfirmation, setRestoreConfirmation] = useState('');
  const [loadingScheduler, setLoadingScheduler] = useState(false);
  const [backupLoading, setBackupLoading] = useState(false);
  const [restoreLoading, setRestoreLoading] = useState(false);
  const jobsRequestInFlight = React.useRef(false);

  const hasActiveJobs = jobs.some((job) => job.status === 'queued' || job.status === 'running');

  useEffect(() => {
    void refreshAll();
  }, []);

  useEffect(() => {
    if (!hasActiveJobs) {
      return;
    }

    const interval = window.setInterval(() => {
      void fetchJobs({ silent: true, preserveError: true });
    }, 3000);

    return () => window.clearInterval(interval);
  }, [hasActiveJobs]);

  const refreshAll = async () => {
    await Promise.all([fetchPlatformStatus(), fetchJobs(), fetchSchedulerTasks(), fetchFailedSchedulerRuns()]);
  };

  const fetchPlatformStatus = async () => {
    setLoadingStatus(true);
    setError(null);
    try {
      const response = await fetch('/api/platform/status');
      const payload = await parseJson<ApiResponse<PlatformStatus>>(response);
      if (!payload.success || !payload.data) {
        throw new Error(payload.error || '平台状态接口返回异常');
      }
      setPlatformStatus(payload.data);
    } catch (err) {
      setError(err instanceof Error ? err.message : '获取平台状态失败');
    } finally {
      setLoadingStatus(false);
    }
  };

  const fetchJobs = async (options: { silent?: boolean; preserveError?: boolean } = {}) => {
    if (jobsRequestInFlight.current) {
      return;
    }

    jobsRequestInFlight.current = true;
    if (!options.silent) {
      setLoadingJobs(true);
      setError(null);
    }
    try {
      const response = await fetch('/api/jobs');
      const payload = await parseJson<JobsResponse>(response);
      if (!payload.success) {
        throw new Error(payload.error || '作业列表接口返回异常');
      }
      setJobs(payload.jobs);
      setJobsWarning(payload.warning || null);
    } catch (err) {
      if (!options.preserveError) {
        setError(err instanceof Error ? err.message : '获取作业列表失败');
      }
    } finally {
      jobsRequestInFlight.current = false;
      if (!options.silent) {
        setLoadingJobs(false);
      }
    }
  };

  const fetchSchedulerTasks = async () => {
    setLoadingScheduler(true);
    try {
      const response = await fetch('/api/scheduler/tasks');
      const payload = await parseJson<SchedulerTasksResponse>(response);
      if (!payload.success) {
        throw new Error(payload.error || '定时任务接口返回异常');
      }
      setSchedulerTasks(payload.tasks);
    } catch (err) {
      setError(err instanceof Error ? err.message : '获取定时任务失败');
    } finally {
      setLoadingScheduler(false);
    }
  };

  const fetchFailedSchedulerRuns = async () => {
    try {
      const response = await fetch('/api/scheduler/runs/failed?limit=20');
      const payload = await parseJson<SchedulerRunsResponse>(response);
      if (!payload.success) {
        throw new Error(payload.error || '调度失败记录接口返回异常');
      }
      setFailedSchedulerRuns(payload.runs);
    } catch (err) {
      setError(err instanceof Error ? err.message : '获取调度失败记录失败');
    }
  };

  const createBackup = async () => {
    setBackupLoading(true);
    setError(null);
    try {
      const response = await fetch('/api/platform/backups', {
        method: 'POST',
        headers: buildOpsHeaders()
      });
      const payload = await parseJson<ApiResponse<BackupResult>>(response);
      if (!payload.success || !payload.data) {
        throw new Error(payload.error || '备份创建失败');
      }
      setLatestBackup(payload.data);
      setRestoreBackupDir(payload.data.backupDir);
      setRestorePlan(null);
      message.success('备份已创建');
    } catch (err) {
      const description = err instanceof Error ? err.message : '备份创建失败';
      setError(description);
      message.error(description);
    } finally {
      setBackupLoading(false);
    }
  };

  const planRestore = async () => {
    setRestoreLoading(true);
    setError(null);
    try {
      const response = await fetch('/api/platform/restore-plan', {
        method: 'POST',
        headers: buildOpsHeaders({ 'Content-Type': 'application/json' }),
        body: JSON.stringify({ backupDir: restoreBackupDir })
      });
      const payload = await parseJson<ApiResponse<RestorePlan>>(response);
      if (!payload.success || !payload.data) {
        throw new Error(payload.error || '恢复预演失败');
      }
      setRestorePlan(payload.data);
      message.success('恢复预演已生成');
    } catch (err) {
      const description = err instanceof Error ? err.message : '恢复预演失败';
      setError(description);
      message.error(description);
    } finally {
      setRestoreLoading(false);
    }
  };

  const executeRestore = async () => {
    setRestoreLoading(true);
    setError(null);
    try {
      const response = await fetch('/api/platform/restore', {
        method: 'POST',
        headers: buildOpsHeaders({ 'Content-Type': 'application/json' }),
        body: JSON.stringify({
          backupDir: restoreBackupDir,
          confirmation: restoreConfirmation
        })
      });
      const payload = await parseJson<ApiResponse<RestoreResult>>(response);
      if (!payload.success || !payload.data) {
        throw new Error(payload.error || '恢复执行失败');
      }
      setRestorePlan(null);
      message.success(`恢复完成: ${payload.data.restored.length} 项`);
      await refreshAll();
    } catch (err) {
      const description = err instanceof Error ? err.message : '恢复执行失败';
      setError(description);
      message.error(description);
    } finally {
      setRestoreLoading(false);
    }
  };

  const runTask = async (task: TaskAction) => {
    setActionLoading(task.type);
    setError(null);
    try {
      const response = await fetch(`/api/jobs/${task.type}/run`, {
        method: 'POST',
        headers: buildOpsHeaders({ 'Content-Type': 'application/json' }),
        body: JSON.stringify(task.params)
      });
      const payload = await parseJson<ApiResponse<JobRecord>>(response);
      if (!payload.success || !payload.data) {
        throw new Error(payload.error || '任务启动失败');
      }
      message.success(`${task.title} 已提交: ${payload.data.id}`);
      await fetchJobs();
    } catch (err) {
      const description = err instanceof Error ? err.message : '任务启动失败';
      setError(description);
      message.error(description);
    } finally {
      setActionLoading(null);
    }
  };

  const retryJob = async (job: JobRecord) => {
    setActionLoading(job.id);
    setError(null);
    try {
      const response = await fetch(`/api/jobs/${job.id}/retry`, {
        method: 'POST',
        headers: buildOpsHeaders()
      });
      const payload = await parseJson<ApiResponse<JobRecord>>(response);
      if (!payload.success || !payload.data) {
        throw new Error(payload.error || '重试任务失败');
      }
      message.success(`已重试任务: ${job.id}`);
      await fetchJobs();
    } catch (err) {
      const description = err instanceof Error ? err.message : '重试任务失败';
      setError(description);
      message.error(description);
    } finally {
      setActionLoading(null);
    }
  };

  const cancelJob = async (job: JobRecord) => {
    setActionLoading(job.id);
    setError(null);
    try {
      const response = await fetch(`/api/jobs/${job.id}/cancel`, {
        method: 'POST',
        headers: buildOpsHeaders()
      });
      const payload = await parseJson<ApiResponse<JobRecord>>(response);
      if (!payload.success || !payload.data) {
        throw new Error(payload.error || '取消任务失败');
      }
      message.success(`已取消任务: ${job.id}`);
      await fetchJobs();
    } catch (err) {
      const description = err instanceof Error ? err.message : '取消任务失败';
      setError(description);
      message.error(description);
    } finally {
      setActionLoading(null);
    }
  };

  const triggerSchedulerTask = async (task: SchedulerTask, mode: 'trigger' | 'compensate') => {
    setActionLoading(`${mode}:${task.id}`);
    setError(null);
    try {
      const response = await fetch(`/api/scheduler/tasks/${task.id}/${mode}`, {
        method: 'POST',
        headers: buildOpsHeaders()
      });
      const payload = await parseJson<ApiResponse<SchedulerRun>>(response);
      if (!payload.success || !payload.data) {
        throw new Error(payload.error || '定时任务触发失败');
      }
      message.success(`${task.name} 已${mode === 'trigger' ? '手动触发' : '补偿触发'}`);
      await fetchSchedulerTasks();
      await fetchFailedSchedulerRuns();
    } catch (err) {
      const description = err instanceof Error ? err.message : '定时任务触发失败';
      setError(description);
      message.error(description);
    } finally {
      setActionLoading(null);
    }
  };

  const jobColumns: ColumnsType<JobRecord> = [
    {
      title: '任务ID',
      dataIndex: 'id',
      key: 'id',
      width: 120,
      render: (id: string) => <Text strong>{id}</Text>
    },
    {
      title: '类型',
      dataIndex: 'type',
      key: 'type',
      width: 140,
      render: (type: JobType) => <Tag>{getTaskTitle(type)}</Tag>
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      width: 110,
      render: (status: JobStatus) => renderStatusTag(status)
    },
    {
      title: '尝试次数',
      dataIndex: 'attempts',
      key: 'attempts',
      width: 90
    },
    {
      title: '更新时间',
      dataIndex: 'updatedAt',
      key: 'updatedAt',
      width: 180,
      render: formatDateTime
    },
    {
      title: '错误',
      dataIndex: 'error',
      key: 'error',
      ellipsis: true,
      render: (value?: string) => value ? <Text type="danger">{value}</Text> : <Text type="secondary">-</Text>
    },
    {
      title: '操作',
      key: 'action',
      width: 170,
      render: (_, record) => (
        <Space>
          <Button
            size="small"
            icon={<ReloadOutlined />}
            disabled={record.status !== 'failed'}
            loading={actionLoading === record.id && record.status === 'failed'}
            onClick={() => void retryJob(record)}
          >
            重试
          </Button>
          <Button
            size="small"
            danger
            disabled={record.status !== 'queued' && record.status !== 'running'}
            loading={actionLoading === record.id && (record.status === 'queued' || record.status === 'running')}
            onClick={() => void cancelJob(record)}
          >
            取消
          </Button>
        </Space>
      )
    }
  ];

  const schedulerColumns: ColumnsType<SchedulerTask> = [
    {
      title: '任务',
      dataIndex: 'name',
      key: 'name',
      width: 180,
      render: (name: string, record) => (
        <Space direction="vertical" size={0}>
          <Text strong>{name}</Text>
          <Text type="secondary">{record.id}</Text>
        </Space>
      )
    },
    {
      title: '调度',
      key: 'schedule',
      width: 180,
      render: (_, record) => <Tag>{formatSchedule(record)}</Tag>
    },
    {
      title: '下次运行',
      dataIndex: 'nextRunAt',
      key: 'nextRunAt',
      width: 180,
      render: formatDateTime
    },
    {
      title: '今日状态',
      key: 'today',
      width: 150,
      render: (_, record) => (
        <Space>
          <Tag color={record.todaySuccess ? 'green' : record.todayTriggered ? 'blue' : 'red'}>
            {record.todaySuccess ? '已成功' : record.todayTriggered ? '已触发' : '未触发'}
          </Tag>
          {record.compensationDue && <Tag color="red">待补偿</Tag>}
        </Space>
      )
    },
    {
      title: '最近状态',
      key: 'lastRun',
      width: 130,
      render: (_, record) => record.lastRun ? renderStatusTag(record.lastRun.status) : <Text type="secondary">无记录</Text>
    },
    {
      title: '补偿',
      key: 'compensation',
      width: 150,
      render: (_, record) => record.compensationEnabled
        ? <Tag color="purple">{record.compensationCheckAfter || '已开启'}</Tag>
        : <Tag>关闭</Tag>
    },
    {
      title: '错误',
      key: 'error',
      ellipsis: true,
      render: (_, record) => record.lastRun?.error ? <Text type="danger">{record.lastRun.error}</Text> : <Text type="secondary">-</Text>
    },
    {
      title: '操作',
      key: 'action',
      width: 190,
      render: (_, record) => (
        <Space>
          <Button
            size="small"
            icon={<PlayCircleOutlined />}
            loading={actionLoading === `trigger:${record.id}`}
            onClick={() => void triggerSchedulerTask(record, 'trigger')}
          >
            触发
          </Button>
          <Button
            size="small"
            icon={<FieldTimeOutlined />}
            disabled={!record.compensationEnabled}
            loading={actionLoading === `compensate:${record.id}`}
            onClick={() => void triggerSchedulerTask(record, 'compensate')}
          >
            补偿
          </Button>
        </Space>
      )
    }
  ];

  const failedRunColumns: ColumnsType<SchedulerRun> = [
    {
      title: '运行ID',
      dataIndex: 'id',
      key: 'id',
      width: 150,
      render: (id: string) => <Text strong>{id}</Text>
    },
    {
      title: '任务',
      dataIndex: 'taskName',
      key: 'taskName',
      width: 180
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      width: 120,
      render: (status: SchedulerRunStatus) => renderStatusTag(status)
    },
    {
      title: '触发类型',
      dataIndex: 'triggerType',
      key: 'triggerType',
      width: 120,
      render: (triggerType: SchedulerTriggerType) => <Tag>{triggerType}</Tag>
    },
    {
      title: '计划时间',
      dataIndex: 'scheduledFor',
      key: 'scheduledFor',
      width: 180,
      render: formatDateTime
    },
    {
      title: '错误/原因',
      key: 'error',
      ellipsis: true,
      render: (_, record) => record.error || record.compensationReason || '-'
    }
  ];

  const sortedJobs = [...jobs].sort((left, right) => Date.parse(right.updatedAt) - Date.parse(left.updatedAt));
  const latestJob = sortedJobs[0];
  const activeJobCount = jobs.filter((job) => job.status === 'queued' || job.status === 'running').length;
  const failedJobCount = jobs.filter((job) => job.status === 'failed').length;
  const activeJobTypes = new Set(
    jobs
      .filter((job) => job.status === 'queued' || job.status === 'running')
      .map((job) => job.type)
  );

  return (
    <div style={{ padding: '24px' }}>
      <Space direction="vertical" size="large" style={{ width: '100%' }}>
        <div>
          <Title level={2} style={{ marginBottom: 8 }}>
            <CloudServerOutlined /> 运维中心
          </Title>
          <Paragraph type="secondary" style={{ marginBottom: 0 }}>
            内部投研/信号平台的运行状态、批处理任务和失败重试入口。
          </Paragraph>
        </div>

        {error && (
          <Alert
            type="error"
            showIcon
            message="接口调用失败"
            description={error}
            action={<Button size="small" onClick={() => void refreshAll()}>刷新</Button>}
          />
        )}

        {jobsWarning && (
          <Alert
            type="warning"
            showIcon
            message="作业存储告警"
            description={jobsWarning}
          />
        )}

        <Row gutter={[16, 16]}>
          <Col xs={24} sm={12} lg={6}>
            <Card loading={loadingStatus}>
              <Statistic
                title="平台状态"
                value={platformStatus ? STATUS_LABELS[platformStatus.overall_status] : '未知'}
                valueStyle={{ color: getStatusColor(platformStatus?.overall_status) }}
                prefix={platformStatus?.overall_status === 'healthy' ? <CheckCircleOutlined /> : <WarningOutlined />}
              />
            </Card>
          </Col>
          <Col xs={24} sm={12} lg={6}>
            <Card loading={loadingJobs}>
              <Statistic title="作业总数" value={jobs.length} suffix="个" />
            </Card>
          </Col>
          <Col xs={24} sm={12} lg={6}>
            <Card loading={loadingJobs}>
              <Statistic
                title="运行中"
                value={activeJobCount}
                suffix="个"
                prefix={activeJobCount > 0 ? <SyncOutlined spin /> : undefined}
              />
            </Card>
          </Col>
          <Col xs={24} sm={12} lg={6}>
            <Card loading={loadingJobs}>
              <Statistic
                title="失败任务"
                value={failedJobCount}
                suffix="个"
                valueStyle={{ color: failedJobCount > 0 ? '#cf1322' : undefined }}
                prefix={failedJobCount > 0 ? <CloseCircleOutlined /> : <CheckCircleOutlined />}
              />
            </Card>
          </Col>
          <Col xs={24} sm={12} lg={6}>
            <Card loading={loadingScheduler}>
              <Statistic
                title="调度异常"
                value={failedSchedulerRuns.length}
                suffix="条"
                valueStyle={{ color: failedSchedulerRuns.length > 0 ? '#cf1322' : undefined }}
                prefix={failedSchedulerRuns.length > 0 ? <WarningOutlined /> : <CheckCircleOutlined />}
              />
            </Card>
          </Col>
        </Row>

        <Card
          title="平台检查"
          extra={<Button icon={<ReloadOutlined />} loading={loadingStatus} onClick={() => void fetchPlatformStatus()}>刷新状态</Button>}
        >
          <Row gutter={[16, 16]}>
            {platformStatus?.checks.map((check) => (
              <Col xs={24} lg={12} key={check.name}>
                <Card size="small" title={<Space>{CHECK_ICONS[check.name]}{CHECK_LABELS[check.name]}</Space>} extra={renderStatusTag(check.status)}>
                  <Descriptions column={1} size="small">
                    <Descriptions.Item label="说明">{check.message}</Descriptions.Item>
                    <Descriptions.Item label="更新时间">{formatDateTime(getDetailValue(check.details, 'modified_at'))}</Descriptions.Item>
                    <Descriptions.Item label="来源">{formatDetailValue(getDetailValue(check.details, 'source'))}</Descriptions.Item>
                    <Descriptions.Item label="路径">{formatDetailValue(getDetailValue(check.details, 'path'))}</Descriptions.Item>
                  </Descriptions>
                </Card>
              </Col>
            )) || (
              <Col span={24}>
                <Alert type="info" showIcon message="暂无平台状态数据" />
              </Col>
            )}
          </Row>
        </Card>

        <Card title="任务触发" extra={<Text type="secondary">长任务会进入后台作业队列</Text>}>
          <Row gutter={[16, 16]}>
            {TASK_ACTIONS.map((task) => (
              <Col xs={24} md={12} xl={8} key={task.type}>
                <Card size="small">
                  <Space direction="vertical" style={{ width: '100%' }}>
                    <Space style={{ justifyContent: 'space-between', width: '100%' }}>
                      <Text strong>{task.title}</Text>
                      <Tag>{task.type}</Tag>
                    </Space>
                    <Text type="secondary">{task.description}</Text>
                    <Button
                      type={task.danger ? 'default' : 'primary'}
                      icon={<PlayCircleOutlined />}
                      loading={actionLoading === task.type}
                      disabled={activeJobTypes.has(task.type)}
                      onClick={() => void runTask(task)}
                    >
                      {activeJobTypes.has(task.type) ? '已有任务运行' : '启动任务'}
                    </Button>
                  </Space>
                </Card>
              </Col>
            ))}
          </Row>
        </Card>

        <Card
          title="定时调度"
          extra={<Button icon={<ReloadOutlined />} loading={loadingScheduler} onClick={() => void Promise.all([fetchSchedulerTasks(), fetchFailedSchedulerRuns()])}>刷新调度</Button>}
        >
          <Table
            columns={schedulerColumns}
            dataSource={schedulerTasks}
            rowKey="id"
            loading={loadingScheduler}
            pagination={{ pageSize: 8 }}
            expandable={{
              expandedRowRender: (record) => (
                <Space direction="vertical" style={{ width: '100%' }}>
                  <Text strong>Payload</Text>
                  <pre style={preStyle}>{JSON.stringify(record.payload, null, 2)}</pre>
                  {record.lastRun && (
                    <>
                      <Text strong>最近运行</Text>
                      <pre style={preStyle}>{JSON.stringify(record.lastRun, null, 2)}</pre>
                    </>
                  )}
                </Space>
              )
            }}
          />
        </Card>

        <Card
          title="调度异常记录"
          extra={<Text type="secondary">最近失败、跳过、错过和补偿失败的调度运行</Text>}
        >
          <Table
            columns={failedRunColumns}
            dataSource={failedSchedulerRuns}
            rowKey="id"
            pagination={{ pageSize: 8 }}
          />
        </Card>

        <Card
          title="备份与恢复演练"
          extra={
            <Button
              icon={<FileTextOutlined />}
              loading={backupLoading}
              onClick={() => void createBackup()}
            >
              创建备份
            </Button>
          }
        >
          <Space direction="vertical" size="middle" style={{ width: '100%' }}>
          {latestBackup ? (
            <Descriptions column={1} size="small">
              <Descriptions.Item label="备份目录">{latestBackup.backupDir}</Descriptions.Item>
              <Descriptions.Item label="创建时间">{formatDateTime(latestBackup.manifest.created_at)}</Descriptions.Item>
              <Descriptions.Item label="已复制">{latestBackup.manifest.copied.map((entry) => entry.source).join(', ') || '-'}</Descriptions.Item>
              <Descriptions.Item label="缺失跳过">{latestBackup.manifest.skipped_missing.map((entry) => entry.source).join(', ') || '-'}</Descriptions.Item>
            </Descriptions>
          ) : (
            <Alert type="info" showIcon message="尚未在本页面创建备份" description="备份会写入 .pi-invest/backups，并生成 manifest.json；恢复目前仅提供 dry-run 计划接口。" />
          )}
            <Space direction="vertical" style={{ width: '100%' }}>
              <Text strong>恢复操作</Text>
              <Input
                placeholder="输入备份目录，例如 .pi-invest/backups/..."
                value={restoreBackupDir}
                onChange={(event) => setRestoreBackupDir(event.target.value)}
              />
              <Space>
                <Button
                  loading={restoreLoading}
                  disabled={!restoreBackupDir}
                  onClick={() => void planRestore()}
                >
                  生成恢复预演
                </Button>
                <Input
                  placeholder="输入 RESTORE_LOCAL_STATE 才能执行"
                  value={restoreConfirmation}
                  onChange={(event) => setRestoreConfirmation(event.target.value)}
                  style={{ width: 260 }}
                />
                <Button
                  danger
                  loading={restoreLoading}
                  disabled={!restoreBackupDir || restoreConfirmation !== 'RESTORE_LOCAL_STATE'}
                  onClick={() => void executeRestore()}
                >
                  执行恢复
                </Button>
              </Space>
              {restorePlan && (
                <Alert
                  type="warning"
                  showIcon
                  message={`恢复预演: 将恢复 ${restorePlan.wouldRestore.length} 项`}
                  description={
                    <pre style={preStyle}>
                      {JSON.stringify(restorePlan.wouldRestore, null, 2)}
                    </pre>
                  }
                />
              )}
            </Space>
          </Space>
        </Card>

        <Card
          title="作业队列"
          extra={
            <Space>
              {latestJob && <Text type="secondary">最近更新: {formatDateTime(latestJob.updatedAt)}</Text>}
              <Button icon={<ReloadOutlined />} loading={loadingJobs} onClick={() => void fetchJobs()}>刷新队列</Button>
            </Space>
          }
        >
          <Table
            columns={jobColumns}
            dataSource={sortedJobs}
            rowKey="id"
            loading={loadingJobs}
            pagination={{ pageSize: 10 }}
            expandable={{
              expandedRowRender: (record) => (
                <Space direction="vertical" style={{ width: '100%' }}>
                  <Text strong>参数</Text>
                  <pre style={preStyle}>{JSON.stringify(record.params, null, 2)}</pre>
                  {record.logs.length > 0 && (
                    <>
                      <Text strong>日志</Text>
                      <pre style={preStyle}>{record.logs.slice(-8).join('\n')}</pre>
                    </>
                  )}
                </Space>
              )
            }}
          />
        </Card>
      </Space>
    </div>
  );
};

async function parseJson<T>(response: Response): Promise<T> {
  const contentType = response.headers.get('content-type') || '';
  const bodyText = await response.text();
  const payload = contentType.includes('application/json') && bodyText
    ? JSON.parse(bodyText) as T
    : ({} as T);

  if (!response.ok) {
    const maybeError = payload as { error?: string };
    const responseText = bodyText ? `: ${bodyText.slice(0, 300)}` : '';
    throw new Error(maybeError.error || `HTTP ${response.status}${responseText}`);
  }
  return payload;
}

function renderStatusTag(status: PlatformCheckStatus | JobStatus | SchedulerRunStatus) {
  return <Tag color={STATUS_COLORS[status]}>{STATUS_LABELS[status]}</Tag>;
}

function formatSchedule(task: SchedulerTask) {
  if (task.scheduleKind === 'cron') return task.scheduleExpr || 'cron';
  if (task.scheduleKind === 'every') return `每 ${task.everySeconds || '-'} 秒`;
  if (task.scheduleKind === 'delay') return `延迟 ${task.delaySeconds || '-'} 秒`;
  if (task.scheduleKind === 'at') return task.scheduleAt || '指定时间';
  return task.scheduleKind;
}

function getStatusColor(status?: PlatformCheckStatus) {
  if (status === 'healthy') return '#3f8600';
  if (status === 'degraded') return '#d48806';
  if (status === 'unavailable') return '#cf1322';
  return undefined;
}

function getTaskTitle(type: JobType) {
  return TASK_ACTIONS.find((task) => task.type === type)?.title || type;
}

function getDetailValue(details: Record<string, unknown> | undefined, key: string) {
  return details?.[key];
}

function formatDetailValue(value: unknown) {
  if (typeof value === 'string' || typeof value === 'number' || typeof value === 'boolean') {
    return String(value);
  }
  if (Array.isArray(value)) {
    return value.join(', ');
  }
  return '-';
}

function formatDateTime(value: unknown) {
  if (typeof value !== 'string' || value.length === 0) {
    return '-';
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return date.toLocaleString('zh-CN', { hour12: false });
}

function buildOpsHeaders(baseHeaders: Record<string, string> = {}) {
  if (!opsApiToken) {
    return baseHeaders;
  }

  return {
    ...baseHeaders,
    Authorization: `Bearer ${opsApiToken}`
  };
}

const preStyle: React.CSSProperties = {
  background: '#f5f5f5',
  borderRadius: 6,
  margin: 0,
  maxHeight: 220,
  overflow: 'auto',
  padding: 12
};

export default OpsCenter;
