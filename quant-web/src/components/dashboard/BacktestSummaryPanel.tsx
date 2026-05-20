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
    title: '代码',
    dataIndex: 'symbol',
    key: 'symbol',
    width: 100,
    render: (symbol: string) => <strong>{symbol}</strong>,
  },
  {
    title: '策略',
    dataIndex: 'best_strategy',
    key: 'best_strategy',
    ellipsis: true,
  },
  {
    title: '收益',
    dataIndex: 'best_return',
    key: 'best_return',
    width: 100,
    align: 'right',
    render: (value: unknown) => renderReturn(value),
  },
  {
    title: '夏普',
    dataIndex: 'sharpe_ratio',
    key: 'sharpe_ratio',
    width: 90,
    align: 'right',
    render: (value: unknown) => formatNumber(value),
  },
  {
    title: '回撤',
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
      title="回测摘要"
      extra={
        <Button size="small" type="link" icon={<ArrowRightOutlined />} onClick={onOpenBacktest}>
          打开
        </Button>
      }
    >
      <Space direction="vertical" size="middle" style={{ width: '100%' }}>
        {error && <Alert type="error" showIcon message="回测结果加载失败" description={error} />}
        <Table
          size="small"
          rowKey="dashboardRowKey"
          columns={columns}
          dataSource={topRows}
          loading={loading}
          pagination={false}
          scroll={{ x: 560 }}
          locale={{
            emptyText: (
              <Empty
                image={Empty.PRESENTED_IMAGE_SIMPLE}
                description="暂无回测结果"
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
