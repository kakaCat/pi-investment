import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
  Alert,
  Button,
  Card,
  Col,
  Descriptions,
  Form,
  Input,
  InputNumber,
  Progress,
  Row,
  Select,
  Space,
  Steps,
  Table,
  Tag,
  Typography,
  message
} from 'antd';
import {
  CheckCircleOutlined,
  CloseCircleOutlined,
  PlayCircleOutlined,
  ReloadOutlined,
  SyncOutlined
} from '@ant-design/icons';
import type { ColumnsType, TablePaginationConfig } from 'antd/es/table';

const { Text, Title } = Typography;

type JobType =
  | 'data_update'
  | 'factor_compute'
  | 'model_train'
  | 'signal_generate'
  | 'risk_check'
  | 'backtest_run'
  | 'daily_report';
type RunStatus = 'queued' | 'running' | 'success' | 'failed' | 'cancelled';
type StepStatus = 'queued' | 'running' | 'success' | 'failed' | 'cancelled' | 'skipped';
type ModelType = 'xgboost' | 'lightgbm' | 'randomforest';

interface PipelineFormValues {
  symbolsText: string;
  days: number;
  model: ModelType;
  futureDays: number;
  threshold: number;
}

interface PipelineConfig {
  symbols: string[];
  days: number;
  model: ModelType;
  futureDays: number;
  threshold: number;
}

interface ApiResponse<T> {
  success: boolean;
  data?: T;
  error?: string;
}

interface StockResolveItem {
  symbol: string;
  name?: string;
  market?: string;
  source?: 'local' | 'external_added';
  hasKlines?: boolean;
  klineCount?: number;
  latestKlineDate?: string | null;
  enoughForFactor?: boolean;
  enoughForTraining?: boolean;
  reason?: string;
}

interface PipelineRunStep {
  key: string;
  name: string;
  type?: 'resolve' | 'job';
  jobType?: JobType;
  status: StepStatus;
  jobId?: string | null;
  input?: Record<string, unknown> | null;
  output?: unknown;
  logs?: string[];
  error?: string | null;
  startedAt?: string | null;
  finishedAt?: string | null;
}

export interface PipelineRun {
  id: string;
  status: RunStatus;
  symbols: string[];
  validSymbols: string[];
  invalidSymbols: string[];
  params: Record<string, unknown>;
  currentStep: string;
  progress: number;
  error?: string | null;
  steps: PipelineRunStep[];
  createdAt: string;
  updatedAt: string;
  startedAt?: string | null;
  finishedAt?: string | null;
}

interface PipelineRunsPage {
  items: PipelineRun[];
  total: number;
  page: number;
  pageSize: number;
}

const STEP_DESCRIPTIONS: Record<string, string> = {
  resolve: '本地没有先查外部接口，有则写入 stocks',
  data_update: '只拉取所选股票 daily_klines',
  factor_compute: '只计算所选股票 factor_values',
  model_train: '用所选股票池构建样本并训练模型',
  signal_generate: '只对所选股票生成买卖信号',
  risk_check: '只检查所选股票风险',
  backtest_run: '只回测所选股票',
  daily_report: '生成本次链路汇总报告'
};

export function parseSymbolInput(input: string): string[] {
  const seen = new Set<string>();
  const symbols: string[] = [];
  input
    .split(/[\s,，]+/)
    .map((value) => value.trim().replace(/^(sh|sz|bj)/i, '').replace(/\.(SH|SZ|BJ|HK)$/i, ''))
    .filter(Boolean)
    .forEach((symbol) => {
      if (!seen.has(symbol)) {
        seen.add(symbol);
        symbols.push(symbol);
      }
    });
  return symbols;
}

export function buildPipelineParams(config: PipelineConfig): Record<JobType, Record<string, unknown>> {
  return {
    data_update: { symbols: config.symbols, days: config.days, force: true },
    factor_compute: { symbols: config.symbols },
    model_train: {
      symbols: config.symbols,
      days: config.days,
      model: config.model,
      futureDays: config.futureDays,
      threshold: config.threshold,
      useFeatureEngineering: true
    },
    signal_generate: { symbols: config.symbols },
    risk_check: { symbols: config.symbols },
    backtest_run: { symbols: config.symbols, days: config.days },
    daily_report: {}
  };
}

export function buildPipelineRunsUrl(page: number, pageSize: number) {
  return `/api/pipeline/runs?page=${page}&pageSize=${pageSize}`;
}

export function derivePipelineProgress(run?: Pick<PipelineRun, 'steps' | 'progress'> | null) {
  if (!run) return 0;
  const steps = run.steps || [];
  if (steps.length === 0) return run.progress || 0;
  const finished = steps.filter((step) => step.status === 'success' || step.status === 'skipped').length;
  return Math.round((finished / steps.length) * 100);
}

export default function QuantPipeline() {
  const [form] = Form.useForm<PipelineFormValues>();
  const [runs, setRuns] = useState<PipelineRun[]>([]);
  const [selectedRun, setSelectedRun] = useState<PipelineRun | null>(null);
  const [pagination, setPagination] = useState({ page: 1, pageSize: 10, total: 0 });
  const [loadingRuns, setLoadingRuns] = useState(false);
  const [starting, setStarting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refreshSelectedRun = useCallback(async (runId: string) => {
    const latest = await fetchPipelineRun(runId);
    setSelectedRun(latest);
    return latest;
  }, []);

  const loadRuns = useCallback(async (page = pagination.page, pageSize = pagination.pageSize) => {
    setLoadingRuns(true);
    try {
      const data = await fetchPipelineRuns(page, pageSize);
      setRuns(data.items);
      setPagination({ page: data.page, pageSize: data.pageSize, total: data.total });
      setSelectedRun((current) => {
        if (current) {
          return data.items.find((item) => item.id === current.id) || current;
        }
        return data.items[0] || null;
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : '运行记录加载失败');
    } finally {
      setLoadingRuns(false);
    }
  }, [pagination.page, pagination.pageSize]);

  useEffect(() => {
    void loadRuns(1, pagination.pageSize);
  }, []);

  useEffect(() => {
    const hasRunning = runs.some((run) => run.status === 'running' || run.status === 'queued')
      || selectedRun?.status === 'running'
      || selectedRun?.status === 'queued';
    if (!hasRunning) return undefined;

    const timer = window.setInterval(() => {
      void loadRuns(pagination.page, pagination.pageSize);
      if (selectedRun) {
        void refreshSelectedRun(selectedRun.id).catch(() => undefined);
      }
    }, 3000);
    return () => window.clearInterval(timer);
  }, [loadRuns, pagination.page, pagination.pageSize, refreshSelectedRun, runs, selectedRun]);

  const runPipeline = async (values: PipelineFormValues) => {
    const symbols = parseSymbolInput(values.symbolsText);
    if (symbols.length === 0) {
      message.error('请输入至少一只股票代码');
      return;
    }

    setStarting(true);
    setError(null);
    try {
      const created = await createPipelineRun({
        symbols,
        days: values.days,
        model: values.model,
        futureDays: values.futureDays,
        threshold: values.threshold
      });
      setSelectedRun(created);
      await loadRuns(1, pagination.pageSize);
      message.success('量化链路已启动');
    } catch (err) {
      const description = err instanceof Error ? err.message : '链路启动失败';
      setError(description);
      message.error(description);
    } finally {
      setStarting(false);
    }
  };

  const retrySelectedRun = async () => {
    if (!selectedRun) {
      await runPipeline(form.getFieldsValue());
      return;
    }
    const params = selectedRun.params || {};
    await runPipeline({
      symbolsText: (selectedRun.symbols || []).join(','),
      days: Number(params.days || 180),
      model: (params.model as ModelType) || 'xgboost',
      futureDays: Number(params.futureDays || 5),
      threshold: Number(params.threshold || 0.05)
    });
  };

  const currentStep = selectedRun?.steps.find((step) => step.key === selectedRun.currentStep)
    || selectedRun?.steps.find((step) => step.status === 'running')
    || selectedRun?.steps[0];
  const progress = derivePipelineProgress(selectedRun);
  const resolvedStocks = extractResolvedStocks(selectedRun);
  const activeLogs = currentStep?.logs || [];

  const runColumns: ColumnsType<PipelineRun> = [
    { title: '运行ID', dataIndex: 'id', key: 'id', width: 150 },
    { title: '股票', key: 'symbols', render: (_, record) => compactSymbols(record.symbols), ellipsis: true },
    { title: '状态', dataIndex: 'status', key: 'status', width: 100, render: renderRunStatus },
    {
      title: '当前节点',
      dataIndex: 'currentStep',
      key: 'currentStep',
      width: 120,
      render: (_, record) => record.steps.find((step) => step.key === record.currentStep)?.name || record.currentStep
    },
    {
      title: '进度',
      key: 'progress',
      width: 140,
      render: (_, record) => <Progress percent={derivePipelineProgress(record)} size="small" />
    },
    { title: '开始时间', dataIndex: 'startedAt', key: 'startedAt', width: 180, render: formatTime },
    { title: '结束时间', dataIndex: 'finishedAt', key: 'finishedAt', width: 180, render: formatTime },
    { title: '耗时', key: 'duration', width: 100, render: (_, record) => formatDuration(record.startedAt, record.finishedAt) },
    {
      title: '操作',
      key: 'action',
      width: 90,
      render: (_, record) => (
        <Button type="link" size="small" onClick={() => refreshSelectedRun(record.id)}>
          查看
        </Button>
      )
    }
  ];

  const stockColumns: ColumnsType<StockResolveItem> = [
    { title: '股票', dataIndex: 'symbol', key: 'symbol', width: 110 },
    { title: '名称', dataIndex: 'name', key: 'name', width: 140, render: (value) => value || '-' },
    {
      title: '来源',
      dataIndex: 'source',
      key: 'source',
      width: 120,
      render: (source) => source === 'external_added' ? <Tag color="blue">接口新增</Tag> : source ? <Tag>本地</Tag> : <Tag color="red">无效</Tag>
    },
    { title: 'K线天数', dataIndex: 'klineCount', key: 'klineCount', width: 100, render: (value) => value ?? '-' },
    { title: '最新日期', dataIndex: 'latestKlineDate', key: 'latestKlineDate', width: 120, render: (value) => value || '-' },
    {
      title: '状态',
      key: 'status',
      render: (_, record) => record.reason
        ? <Text type="danger">{record.reason}</Text>
        : <Space><Tag color={record.enoughForFactor ? 'green' : 'orange'}>因子</Tag><Tag color={record.enoughForTraining ? 'green' : 'orange'}>训练</Tag></Space>
    }
  ];

  const handleTableChange = (next: TablePaginationConfig) => {
    void loadRuns(next.current || 1, next.pageSize || pagination.pageSize);
  };

  return (
    <div className="pipeline-page">
      <Space direction="vertical" size="large" style={{ width: '100%' }}>
        <div>
          <Title level={3} style={{ marginBottom: 4 }}>量化链路</Title>
          <Text type="secondary">按单只或多只股票执行：标的识别、行情补齐、因子、训练、信号、风控、回测、汇总。</Text>
        </div>

        {error && <Alert type="error" showIcon message="链路执行失败" description={error} />}
        {selectedRun?.error && <Alert type="error" showIcon message="当前运行失败" description={selectedRun.error} />}

        <Card title="运行链路">
          <Form
            form={form}
            layout="vertical"
            initialValues={{
              symbolsText: '000001,600036',
              days: 180,
              model: 'xgboost',
              futureDays: 5,
              threshold: 0.05
            }}
            onFinish={runPipeline}
          >
            <Row gutter={16}>
              <Col xs={24} lg={10}>
                <Form.Item label="股票代码" name="symbolsText" rules={[{ required: true, message: '请输入股票代码' }]}>
                  <Input.TextArea rows={3} placeholder="000001, 600036, 600519" disabled={starting} />
                </Form.Item>
              </Col>
              <Col xs={12} lg={4}>
                <Form.Item label="训练/拉取天数" name="days" rules={[{ required: true }]}>
                  <InputNumber min={60} max={730} style={{ width: '100%' }} disabled={starting} />
                </Form.Item>
              </Col>
              <Col xs={12} lg={4}>
                <Form.Item label="模型" name="model" rules={[{ required: true }]}>
                  <Select disabled={starting}>
                    <Select.Option value="xgboost">XGBoost</Select.Option>
                    <Select.Option value="lightgbm">LightGBM</Select.Option>
                    <Select.Option value="randomforest">Random Forest</Select.Option>
                  </Select>
                </Form.Item>
              </Col>
              <Col xs={12} lg={3}>
                <Form.Item label="预测天数" name="futureDays" rules={[{ required: true }]}>
                  <InputNumber min={1} max={30} style={{ width: '100%' }} disabled={starting} />
                </Form.Item>
              </Col>
              <Col xs={12} lg={3}>
                <Form.Item label="收益阈值" name="threshold" rules={[{ required: true }]}>
                  <InputNumber min={0.01} max={0.2} step={0.01} style={{ width: '100%' }} disabled={starting} />
                </Form.Item>
              </Col>
            </Row>
            <Space>
              <Button type="primary" htmlType="submit" icon={<PlayCircleOutlined />} loading={starting}>
                开始完整链路
              </Button>
              <Button icon={<ReloadOutlined />} disabled={starting} onClick={retrySelectedRun}>
                重跑选中链路
              </Button>
            </Space>
          </Form>
        </Card>

        <Row gutter={16}>
          <Col xs={24} xl={14}>
            <Card title="链路进度" extra={<Progress percent={progress} size="small" style={{ width: 180 }} />}>
              {selectedRun ? (
                <Steps
                  direction="vertical"
                  current={Math.max(selectedRun.steps.findIndex((step) => step.key === selectedRun.currentStep), 0)}
                  items={selectedRun.steps.map((step) => ({
                    title: step.name,
                    description: (
                      <Space direction="vertical" size={2}>
                        <Text type="secondary">{STEP_DESCRIPTIONS[step.key] || '-'}</Text>
                        {step.jobId && <Text type="secondary">Job: {step.jobId}</Text>}
                        {step.error && <Text type="danger">{step.error}</Text>}
                      </Space>
                    ),
                    status: toAntdStepStatus(step.status),
                    icon: renderStepIcon(step.status)
                  }))}
                />
              ) : (
                <Text type="secondary">暂无运行记录，点击开始后显示链路进度。</Text>
              )}
            </Card>
          </Col>
          <Col xs={24} xl={10}>
            <Card title="当前节点详情">
              <Space direction="vertical" style={{ width: '100%' }}>
                <Descriptions size="small" column={1}>
                  <Descriptions.Item label="运行ID">{selectedRun?.id || '-'}</Descriptions.Item>
                  <Descriptions.Item label="节点">{currentStep?.name || '-'}</Descriptions.Item>
                  <Descriptions.Item label="可执行股票">{selectedRun?.validSymbols?.length ? selectedRun.validSymbols.join(', ') : '-'}</Descriptions.Item>
                  <Descriptions.Item label="任务状态">{selectedRun ? renderRunStatus(selectedRun.status) : '-'}</Descriptions.Item>
                </Descriptions>
                {activeLogs.length ? (
                  <pre className="pipeline-log">{activeLogs.slice(-12).join('\n')}</pre>
                ) : (
                  <Text type="secondary">暂无任务日志</Text>
                )}
              </Space>
            </Card>
          </Col>
        </Row>

        <Card title="标的识别结果">
          <Table
            size="small"
            rowKey="symbol"
            columns={stockColumns}
            dataSource={resolvedStocks}
            pagination={false}
            locale={{ emptyText: '开始后显示本地/外部接口识别结果' }}
          />
        </Card>

        <Card title="运行记录">
          <Table
            size="small"
            rowKey="id"
            loading={loadingRuns}
            columns={runColumns}
            dataSource={runs}
            onRow={(record) => ({ onClick: () => refreshSelectedRun(record.id) })}
            rowClassName={(record) => record.id === selectedRun?.id ? 'pipeline-run-selected' : ''}
            pagination={{
              current: pagination.page,
              pageSize: pagination.pageSize,
              total: pagination.total,
              showSizeChanger: true
            }}
            onChange={handleTableChange}
          />
        </Card>
      </Space>
    </div>
  );
}

async function createPipelineRun(config: PipelineConfig): Promise<PipelineRun> {
  const response = await fetch('/api/pipeline/runs', {
    method: 'POST',
    headers: buildOpsHeaders({ 'Content-Type': 'application/json' }),
    body: JSON.stringify(config)
  });
  const payload = await parseJson<ApiResponse<PipelineRun>>(response);
  if (!payload.success || !payload.data) {
    throw new Error(payload.error || '链路启动失败');
  }
  return payload.data;
}

async function fetchPipelineRuns(page: number, pageSize: number): Promise<PipelineRunsPage> {
  const response = await fetch(buildPipelineRunsUrl(page, pageSize));
  const payload = await parseJson<ApiResponse<PipelineRunsPage>>(response);
  if (!payload.success || !payload.data) {
    throw new Error(payload.error || '运行记录加载失败');
  }
  return payload.data;
}

async function fetchPipelineRun(id: string): Promise<PipelineRun> {
  const response = await fetch(`/api/pipeline/runs/${id}`);
  const payload = await parseJson<ApiResponse<PipelineRun>>(response);
  if (!payload.success || !payload.data) {
    throw new Error(payload.error || '运行详情加载失败');
  }
  return payload.data;
}

async function parseJson<T>(response: Response): Promise<T> {
  const contentType = response.headers.get('content-type') || '';
  const bodyText = await response.text();
  const payload = contentType.includes('application/json') && bodyText
    ? JSON.parse(bodyText) as T
    : ({} as T);

  if (!response.ok) {
    const maybeError = payload as { error?: string };
    throw new Error(maybeError.error || `HTTP ${response.status}`);
  }
  return payload;
}

function extractResolvedStocks(run: PipelineRun | null): StockResolveItem[] {
  const resolveStep = run?.steps.find((step) => step.key === 'resolve');
  const output = resolveStep?.output as { stocks?: StockResolveItem[] } | undefined;
  return output?.stocks || [];
}

function toAntdStepStatus(status: StepStatus) {
  if (status === 'running') return 'process';
  if (status === 'success' || status === 'skipped') return 'finish';
  if (status === 'failed' || status === 'cancelled') return 'error';
  return 'wait';
}

function renderStepIcon(status: StepStatus) {
  if (status === 'success' || status === 'skipped') return <CheckCircleOutlined />;
  if (status === 'failed' || status === 'cancelled') return <CloseCircleOutlined />;
  if (status === 'running') return <SyncOutlined spin />;
  return undefined;
}

function renderRunStatus(status: RunStatus) {
  const color: Record<RunStatus, string> = {
    queued: 'default',
    running: 'processing',
    success: 'green',
    failed: 'red',
    cancelled: 'orange'
  };
  const label: Record<RunStatus, string> = {
    queued: '等待中',
    running: '运行中',
    success: '成功',
    failed: '失败',
    cancelled: '已取消'
  };
  return <Tag color={color[status]}>{label[status]}</Tag>;
}

function compactSymbols(symbols: string[]) {
  if (!symbols?.length) return '-';
  if (symbols.length <= 3) return symbols.join(', ');
  return `${symbols.slice(0, 3).join(', ')} 等${symbols.length}只`;
}

function formatTime(value?: string | null) {
  if (!value) return '-';
  return new Date(value).toLocaleString();
}

function formatDuration(start?: string | null, end?: string | null) {
  if (!start) return '-';
  const startMs = new Date(start).getTime();
  const endMs = end ? new Date(end).getTime() : Date.now();
  if (Number.isNaN(startMs) || Number.isNaN(endMs)) return '-';
  const seconds = Math.max(Math.round((endMs - startMs) / 1000), 0);
  if (seconds < 60) return `${seconds}s`;
  const minutes = Math.floor(seconds / 60);
  const rest = seconds % 60;
  return `${minutes}m ${rest}s`;
}

function buildOpsHeaders(baseHeaders: Record<string, string> = {}) {
  const token = import.meta.env.VITE_OPS_API_TOKEN as string | undefined;
  if (!token) {
    return baseHeaders;
  }
  return { ...baseHeaders, Authorization: `Bearer ${token}` };
}
