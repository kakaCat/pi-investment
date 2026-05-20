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
      title="模型摘要"
      loading={loading && history.length === 0}
      extra={
        <Button size="small" type="link" icon={<ArrowRightOutlined />} onClick={onOpenTraining}>
          打开
        </Button>
      }
    >
      <Space direction="vertical" size="middle" style={{ width: '100%' }}>
        {error && <Alert type="error" showIcon message="训练历史加载失败" description={error} />}
        {!latestRecord ? (
          <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无模型训练历史" />
        ) : (
          <>
            <div style={{ display: 'grid', gap: 12, gridTemplateColumns: 'repeat(auto-fit, minmax(130px, 1fr))' }}>
              <MetricCard title="CV AUC" value={formatNumber(latestRecord.cv_auc)} tone="info" loading={loading} />
              <MetricCard title="Test AUC" value={formatNumber(latestRecord.test_auc)} tone="success" loading={loading} />
              <MetricCard title="特征数" value={latestRecord.n_features} loading={loading} />
              <MetricCard title="样本数" value={latestRecord.total_samples} loading={loading} />
            </div>
            <Descriptions size="small" column={{ xs: 1, sm: 2 }} bordered>
              <Descriptions.Item label="模型">{latestRecord.model_type}</Descriptions.Item>
              <Descriptions.Item label="训练时间">{formatDateTime(latestRecord.timestamp)}</Descriptions.Item>
              <Descriptions.Item label="耗时">{formatDuration(latestRecord.duration_seconds)}</Descriptions.Item>
              <Descriptions.Item label="类别平衡">
                {formatPercent(latestRecord.class_balance)}
              </Descriptions.Item>
            </Descriptions>
            <Text type="secondary">最近一次完成的训练记录</Text>
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
