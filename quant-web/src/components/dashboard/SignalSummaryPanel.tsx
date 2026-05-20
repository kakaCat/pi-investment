import { Alert, Button, Card, Empty, Space, Table, Tag, Typography } from 'antd';
import { ArrowRightOutlined } from '@ant-design/icons';
import type { ColumnsType } from 'antd/es/table';
import type { DashboardSignal } from '../../dashboard/dashboardTypes';
import { calculateSignalMetrics } from '../../dashboard/dashboardMetrics';
import MetricCard from './MetricCard';

const { Text } = Typography;

type SignalSummaryRow = DashboardSignal & {
  dashboardRowKey: string;
};

export interface SignalSummaryPanelProps {
  title?: string;
  signals: DashboardSignal[];
  loading?: boolean;
  error?: string;
  emptyDescription?: string;
  onOpenSignals: () => void;
}

const columns: ColumnsType<SignalSummaryRow> = [
  {
    title: '代码',
    dataIndex: 'symbol',
    key: 'symbol',
    width: 96,
    render: (symbol: string, record) => (
      <Space direction="vertical" size={0}>
        <Text strong>{symbol}</Text>
        {record.name && <Text type="secondary">{record.name}</Text>}
      </Space>
    ),
  },
  {
    title: '方向',
    dataIndex: 'signal',
    key: 'signal',
    width: 76,
    render: (signal: SignalSummaryRow['signal']) => (
      <Tag color={signal === 'BUY' ? 'green' : 'red'}>{signal === 'BUY' ? '买入' : '卖出'}</Tag>
    ),
  },
  {
    title: '策略',
    dataIndex: 'strategy',
    key: 'strategy',
    ellipsis: true,
    render: (strategy?: string) => strategy || '-',
  },
  {
    title: '置信度',
    dataIndex: 'confidence',
    key: 'confidence',
    width: 88,
    align: 'right',
    render: formatPercent,
  },
  {
    title: '日期',
    key: 'date',
    width: 108,
    render: (_, record) => formatDate(record.date || record.created_at),
  },
];

export default function SignalSummaryPanel({
  title = '信号摘要',
  signals,
  loading = false,
  error,
  emptyDescription = '暂无最近信号',
  onOpenSignals,
}: SignalSummaryPanelProps) {
  const metrics = calculateSignalMetrics(signals);
  const latestSignals: SignalSummaryRow[] = [...signals]
    .sort((first, second) => getSignalTime(second) - getSignalTime(first))
    .slice(0, 5)
    .map((signal, index) => ({
      ...signal,
      dashboardRowKey: `${index}-${signal.symbol}-${signal.signal}-${signal.date || signal.created_at || ''}`,
    }));

  return (
    <Card
      title={title}
      extra={
        <Button size="small" type="link" icon={<ArrowRightOutlined />} onClick={onOpenSignals}>
          打开
        </Button>
      }
    >
      <Space direction="vertical" size="middle" style={{ width: '100%' }}>
        {error && <Alert type="error" showIcon message="信号加载失败" description={error} />}
        <div style={{ display: 'grid', gap: 12, gridTemplateColumns: 'repeat(auto-fit, minmax(120px, 1fr))' }}>
          <MetricCard title="买入" value={metrics.buyCount} tone="success" loading={loading} />
          <MetricCard title="卖出" value={metrics.sellCount} tone="danger" loading={loading} />
          <MetricCard
            title="高置信"
            value={metrics.highConfidenceCount}
            tone="info"
            loading={loading}
            helper="置信度 >= 80%"
          />
        </div>
        <Table
          size="small"
          rowKey="dashboardRowKey"
          columns={columns}
          dataSource={latestSignals}
          loading={loading}
          pagination={false}
          scroll={{ x: 560 }}
          locale={{
            emptyText: (
              <Empty
                image={Empty.PRESENTED_IMAGE_SIMPLE}
                description={emptyDescription}
              />
            ),
          }}
        />
      </Space>
    </Card>
  );
}

function getSignalTime(signal: DashboardSignal) {
  return Date.parse(signal.created_at || signal.date || '') || 0;
}

function formatPercent(value?: number) {
  return typeof value === 'number' ? `${(value * 100).toFixed(0)}%` : '-';
}

function formatDate(value?: string) {
  if (!value) {
    return '-';
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return date.toLocaleDateString('zh-CN');
}
