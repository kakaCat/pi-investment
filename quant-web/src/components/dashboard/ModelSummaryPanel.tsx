import { Alert, Button, Card, Descriptions, Empty, Space, Typography } from 'antd';
import { ArrowRightOutlined } from '@ant-design/icons';
import type { TrainingRecord } from '../../dashboard/dashboardTypes';
import { getLatestTrainingRecord } from '../../dashboard/dashboardMetrics';
import MetricCard from './MetricCard';

const { Text } = Typography;

export interface ModelSummaryPanelProps {
  history: TrainingRecord[];
  loading?: boolean;
  error?: string;
  onOpenTraining: () => void;
}

export default function ModelSummaryPanel({
  history,
  loading = false,
  error,
  onOpenTraining,
}: ModelSummaryPanelProps) {
  const latestRecord = getLatestTrainingRecord(history);

  return (
    <Card
      title="Model Summary"
      loading={loading && history.length === 0}
      extra={
        <Button size="small" type="link" icon={<ArrowRightOutlined />} onClick={onOpenTraining}>
          Open
        </Button>
      }
    >
      <Space direction="vertical" size="middle" style={{ width: '100%' }}>
        {error && <Alert type="error" showIcon message="Unable to load training history" description={error} />}
        {!latestRecord ? (
          <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="No model training history" />
        ) : (
          <>
            <div style={{ display: 'grid', gap: 12, gridTemplateColumns: 'repeat(auto-fit, minmax(130px, 1fr))' }}>
              <MetricCard title="CV AUC" value={formatNumber(latestRecord.cv_auc)} tone="info" loading={loading} />
              <MetricCard title="Test AUC" value={formatNumber(latestRecord.test_auc)} tone="success" loading={loading} />
              <MetricCard title="Features" value={latestRecord.n_features} loading={loading} />
              <MetricCard title="Samples" value={latestRecord.total_samples} loading={loading} />
            </div>
            <Descriptions size="small" column={{ xs: 1, sm: 2 }} bordered>
              <Descriptions.Item label="Model">{latestRecord.model_type}</Descriptions.Item>
              <Descriptions.Item label="Trained">{formatDateTime(latestRecord.timestamp)}</Descriptions.Item>
              <Descriptions.Item label="Duration">{formatDuration(latestRecord.duration_seconds)}</Descriptions.Item>
              <Descriptions.Item label="Class Balance">
                {formatPercent(latestRecord.class_balance)}
              </Descriptions.Item>
            </Descriptions>
            <Text type="secondary">Latest completed training record</Text>
          </>
        )}
      </Space>
    </Card>
  );
}

function formatNumber(value: number) {
  return Number.isFinite(value) ? value.toFixed(3) : '-';
}

function formatPercent(value: number) {
  return Number.isFinite(value) ? `${(value * 100).toFixed(1)}%` : '-';
}

function formatDuration(seconds?: number) {
  if (typeof seconds !== 'number' || !Number.isFinite(seconds)) {
    return '-';
  }
  if (seconds < 60) {
    return `${seconds.toFixed(0)}s`;
  }
  return `${Math.floor(seconds / 60)}m ${Math.round(seconds % 60)}s`;
}

function formatDateTime(value: string) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return date.toLocaleString('zh-CN', { hour12: false });
}
