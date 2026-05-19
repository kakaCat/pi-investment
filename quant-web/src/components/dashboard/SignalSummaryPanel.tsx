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
  signals: DashboardSignal[];
  loading?: boolean;
  error?: string;
  onOpenSignals: () => void;
}

const columns: ColumnsType<SignalSummaryRow> = [
  {
    title: 'Symbol',
    dataIndex: 'symbol',
    key: 'symbol',
    width: 100,
    render: (symbol: string, record) => (
      <Space direction="vertical" size={0}>
        <Text strong>{symbol}</Text>
        {record.name && <Text type="secondary">{record.name}</Text>}
      </Space>
    ),
  },
  {
    title: 'Side',
    dataIndex: 'signal',
    key: 'signal',
    width: 90,
    render: (signal: SignalSummaryRow['signal']) => (
      <Tag color={signal === 'BUY' ? 'green' : 'red'}>{signal}</Tag>
    ),
  },
  {
    title: 'Strategy',
    dataIndex: 'strategy',
    key: 'strategy',
    ellipsis: true,
    render: (strategy?: string) => strategy || '-',
  },
  {
    title: 'Confidence',
    dataIndex: 'confidence',
    key: 'confidence',
    width: 110,
    align: 'right',
    render: formatPercent,
  },
  {
    title: 'Date',
    key: 'date',
    width: 130,
    render: (_, record) => formatDate(record.date || record.created_at),
  },
];

export default function SignalSummaryPanel({
  signals,
  loading = false,
  error,
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
      title="Signal Summary"
      extra={
        <Button size="small" type="link" icon={<ArrowRightOutlined />} onClick={onOpenSignals}>
          Open
        </Button>
      }
    >
      <Space direction="vertical" size="middle" style={{ width: '100%' }}>
        {error && <Alert type="error" showIcon message="Unable to load signals" description={error} />}
        <div style={{ display: 'grid', gap: 12, gridTemplateColumns: 'repeat(auto-fit, minmax(120px, 1fr))' }}>
          <MetricCard title="Buy" value={metrics.buyCount} tone="success" loading={loading} />
          <MetricCard title="Sell" value={metrics.sellCount} tone="danger" loading={loading} />
          <MetricCard
            title="High Confidence"
            value={metrics.highConfidenceCount}
            tone="info"
            loading={loading}
            helper="Confidence >= 80%"
          />
        </div>
        <Table
          size="small"
          rowKey="dashboardRowKey"
          columns={columns}
          dataSource={latestSignals}
          loading={loading}
          pagination={false}
          locale={{
            emptyText: (
              <Empty
                image={Empty.PRESENTED_IMAGE_SIMPLE}
                description="No recent signals"
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
