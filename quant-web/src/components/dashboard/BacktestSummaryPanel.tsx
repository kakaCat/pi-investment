import { Alert, Button, Card, Empty, Space, Table, Tag } from 'antd';
import { ArrowRightOutlined } from '@ant-design/icons';
import type { ColumnsType } from 'antd/es/table';
import type { BacktestSummary } from '../../dashboard/dashboardTypes';

type BacktestSummaryRow = BacktestSummary & {
  dashboardRowKey: string;
};

export interface BacktestSummaryPanelProps {
  summary: BacktestSummary[];
  loading?: boolean;
  error?: string;
  onOpenBacktest: () => void;
}

const columns: ColumnsType<BacktestSummaryRow> = [
  {
    title: 'Symbol',
    dataIndex: 'symbol',
    key: 'symbol',
    width: 100,
    render: (symbol: string) => <strong>{symbol}</strong>,
  },
  {
    title: 'Strategy',
    dataIndex: 'best_strategy',
    key: 'best_strategy',
    ellipsis: true,
  },
  {
    title: 'Return',
    dataIndex: 'best_return',
    key: 'best_return',
    width: 100,
    align: 'right',
    render: (value: unknown) => renderReturn(value),
  },
  {
    title: 'Sharpe',
    dataIndex: 'sharpe_ratio',
    key: 'sharpe_ratio',
    width: 90,
    align: 'right',
    render: (value: unknown) => formatNumber(value),
  },
  {
    title: 'Drawdown',
    dataIndex: 'max_drawdown',
    key: 'max_drawdown',
    width: 110,
    align: 'right',
    render: (value: unknown) => formatPercent(value),
  },
];

export default function BacktestSummaryPanel({
  summary,
  loading = false,
  error,
  onOpenBacktest,
}: BacktestSummaryPanelProps) {
  const topRows: BacktestSummaryRow[] = [...summary]
    .sort((first, second) => {
      const sharpeDelta = compareFiniteDescending(first.sharpe_ratio, second.sharpe_ratio);
      return sharpeDelta === 0
        ? compareFiniteDescending(first.best_return, second.best_return)
        : sharpeDelta;
    })
    .slice(0, 5)
    .map((row, index) => ({
      ...row,
      dashboardRowKey: `${index}-${row.symbol}-${row.best_strategy}-${row.date}`,
    }));

  return (
    <Card
      title="Backtest Summary"
      extra={
        <Button size="small" type="link" icon={<ArrowRightOutlined />} onClick={onOpenBacktest}>
          Open
        </Button>
      }
    >
      <Space direction="vertical" size="middle" style={{ width: '100%' }}>
        {error && <Alert type="error" showIcon message="Unable to load backtests" description={error} />}
        <Table
          size="small"
          rowKey="dashboardRowKey"
          columns={columns}
          dataSource={topRows}
          loading={loading}
          pagination={false}
          locale={{
            emptyText: (
              <Empty
                image={Empty.PRESENTED_IMAGE_SIMPLE}
                description="No backtest results. Open backtests to run one."
              />
            ),
          }}
        />
      </Space>
    </Card>
  );
}

function toFiniteNumber(value: unknown): number | undefined {
  const numericValue = typeof value === 'number' ? value : Number(value);
  return Number.isFinite(numericValue) ? numericValue : undefined;
}

function compareFiniteDescending(first: unknown, second: unknown) {
  const firstValue = toFiniteNumber(first);
  const secondValue = toFiniteNumber(second);

  if (firstValue === undefined && secondValue === undefined) {
    return 0;
  }
  if (firstValue === undefined) {
    return 1;
  }
  if (secondValue === undefined) {
    return -1;
  }
  return secondValue - firstValue;
}

function renderReturn(value: unknown) {
  const numericValue = toFiniteNumber(value);
  if (numericValue === undefined) {
    return <Tag>-</Tag>;
  }
  return <Tag color={numericValue >= 0 ? 'green' : 'red'}>{formatPercent(numericValue)}</Tag>;
}

function formatPercent(value: unknown) {
  const numericValue = toFiniteNumber(value);
  return numericValue === undefined ? '-' : `${(numericValue * 100).toFixed(1)}%`;
}

function formatNumber(value: unknown) {
  const numericValue = toFiniteNumber(value);
  return numericValue === undefined ? '-' : numericValue.toFixed(2);
}
