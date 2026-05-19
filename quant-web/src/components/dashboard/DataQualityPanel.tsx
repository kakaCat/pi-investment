import { Alert, Button, Card, Empty, Progress, Space, Typography } from 'antd';
import { ArrowRightOutlined, DatabaseOutlined } from '@ant-design/icons';
import type { StockDataStatus } from '../../dashboard/dashboardTypes';
import { calculateDataQualityMetrics } from '../../dashboard/dashboardMetrics';
import MetricCard from './MetricCard';

const { Text } = Typography;

export interface DataQualityPanelProps {
  status?: StockDataStatus;
  loading?: boolean;
  error?: string;
  onOpenData: () => void;
}

export default function DataQualityPanel({
  status,
  loading = false,
  error,
  onOpenData,
}: DataQualityPanelProps) {
  const metrics = calculateDataQualityMetrics(status);
  const completionPercent = Math.round((metrics.completenessRate ?? 0) * 100);
  const hasData = Boolean(status && metrics.totalStocks > 0);

  return (
    <Card
      title="Data Quality"
      loading={loading && !status}
      extra={
        <Button size="small" type="link" icon={<ArrowRightOutlined />} onClick={onOpenData}>
          Open
        </Button>
      }
    >
      <Space direction="vertical" size="middle" style={{ width: '100%' }}>
        {error && <Alert type="error" showIcon message="Unable to load data status" description={error} />}
        {!hasData ? (
          <Empty
            image={Empty.PRESENTED_IMAGE_SIMPLE}
            description="No stock data status. Database may be missing or empty."
          />
        ) : (
          <>
            <Progress
              percent={completionPercent}
              status={metrics.incompleteStocks > 0 ? 'active' : 'success'}
            />
            <div style={{ display: 'grid', gap: 12, gridTemplateColumns: 'repeat(auto-fit, minmax(120px, 1fr))' }}>
              <MetricCard title="Total" value={metrics.totalStocks} prefix={<DatabaseOutlined />} loading={loading} />
              <MetricCard title="Complete" value={metrics.completeStocks} tone="success" loading={loading} />
              <MetricCard
                title="Incomplete"
                value={metrics.incompleteStocks}
                tone={metrics.incompleteStocks > 0 ? 'warning' : 'success'}
                loading={loading}
              />
            </div>
            <Text type="secondary">Latest data date: {metrics.latestDataDate || '-'}</Text>
          </>
        )}
      </Space>
    </Card>
  );
}
