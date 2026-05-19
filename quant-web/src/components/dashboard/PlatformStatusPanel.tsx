import { Alert, Card, Empty, List, Space, Tag, Typography } from 'antd';
import {
  CheckCircleOutlined,
  CloseCircleOutlined,
  DatabaseOutlined,
  FileTextOutlined,
  RobotOutlined,
  SignalFilled,
  WarningOutlined,
} from '@ant-design/icons';
import type { PlatformCheckStatus } from '../../dashboard/dashboardTypes';

const { Text } = Typography;

type PlatformCheckName = 'database' | 'signals' | 'model' | 'daily_report';

interface PlatformStatusCheck {
  name: PlatformCheckName;
  status: PlatformCheckStatus;
  message?: string;
  details?: Record<string, unknown>;
}

interface PlatformStatus {
  overall_status: PlatformCheckStatus;
  generated_at?: string;
  checks: PlatformStatusCheck[];
}

export interface PlatformStatusPanelProps {
  status?: PlatformStatus;
  loading?: boolean;
  error?: string;
}

const CHECK_LABELS: Record<PlatformCheckName, string> = {
  database: 'Database',
  signals: 'Signals',
  model: 'Model',
  daily_report: 'Daily report',
};

const CHECK_ICONS: Record<PlatformCheckName, React.ReactNode> = {
  database: <DatabaseOutlined />,
  signals: <SignalFilled />,
  model: <RobotOutlined />,
  daily_report: <FileTextOutlined />,
};

const STATUS_COLORS: Record<PlatformCheckStatus, string> = {
  healthy: 'green',
  degraded: 'orange',
  unavailable: 'red',
};

const STATUS_LABELS: Record<PlatformCheckStatus, string> = {
  healthy: 'Healthy',
  degraded: 'Degraded',
  unavailable: 'Unavailable',
};

export default function PlatformStatusPanel({
  status,
  loading = false,
  error,
}: PlatformStatusPanelProps) {
  return (
    <Card
      title="Platform Status"
      loading={loading && !status}
      extra={status && <Tag color={STATUS_COLORS[status.overall_status]}>{STATUS_LABELS[status.overall_status]}</Tag>}
    >
      <Space direction="vertical" size="middle" style={{ width: '100%' }}>
        {error && <Alert type="error" showIcon message="Unable to load platform status" description={error} />}
        {!status ? (
          <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="No platform status available" />
        ) : (
          <>
            <List
              size="small"
              dataSource={buildChecks(status)}
              renderItem={(check) => (
                <List.Item>
                  <List.Item.Meta
                    avatar={getStatusIcon(check.status)}
                    title={
                      <Space>
                        {CHECK_ICONS[check.name]}
                        <span>{CHECK_LABELS[check.name]}</span>
                        <Tag color={STATUS_COLORS[check.status]}>{STATUS_LABELS[check.status]}</Tag>
                      </Space>
                    }
                    description={check.message || '-'}
                  />
                </List.Item>
              )}
            />
            {status.generated_at && <Text type="secondary">Generated: {formatDateTime(status.generated_at)}</Text>}
          </>
        )}
      </Space>
    </Card>
  );
}

function buildChecks(status: PlatformStatus) {
  const byName = new Map(status.checks.map((check) => [check.name, check]));
  return (Object.keys(CHECK_LABELS) as PlatformCheckName[]).map((name) => (
    byName.get(name) || { name, status: 'unavailable' as const, message: 'No check result' }
  ));
}

function getStatusIcon(status: PlatformCheckStatus) {
  if (status === 'healthy') {
    return <CheckCircleOutlined style={{ color: '#3f8600' }} />;
  }
  if (status === 'degraded') {
    return <WarningOutlined style={{ color: '#d48806' }} />;
  }
  return <CloseCircleOutlined style={{ color: '#cf1322' }} />;
}

function formatDateTime(value: string) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return date.toLocaleString('zh-CN', { hour12: false });
}
