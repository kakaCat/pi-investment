import { Alert, Button, Card, Empty, Space, Table, Tag, Typography } from 'antd';
import { ArrowRightOutlined, CloseCircleOutlined, ReloadOutlined } from '@ant-design/icons';
import type { ColumnsType } from 'antd/es/table';
import type { JobRecord, JobStatus } from '../../dashboard/dashboardTypes';

const { Text } = Typography;

export interface JobQueuePanelProps {
  jobs: JobRecord[];
  loading?: boolean;
  error?: string;
  actionLoading?: string | null;
  onRetry: (job: JobRecord) => void;
  onCancel: (job: JobRecord) => void;
  onOpenJobs: () => void;
}

const STATUS_COLORS: Record<JobStatus, string> = {
  queued: 'default',
  running: 'processing',
  success: 'green',
  failed: 'red',
  cancelled: 'orange',
};

const STATUS_LABELS: Record<JobStatus, string> = {
  queued: 'Queued',
  running: 'Running',
  success: 'Success',
  failed: 'Failed',
  cancelled: 'Cancelled',
};

export default function JobQueuePanel({
  jobs,
  loading = false,
  error,
  actionLoading = null,
  onRetry,
  onCancel,
  onOpenJobs,
}: JobQueuePanelProps) {
  const recentJobs = [...jobs]
    .sort((first, second) => Date.parse(second.updatedAt) - Date.parse(first.updatedAt))
    .slice(0, 5);
  const columns: ColumnsType<JobRecord> = [
    {
      title: 'Job',
      dataIndex: 'id',
      key: 'id',
      width: 120,
      ellipsis: true,
      render: (id: string, record) => (
        <Space direction="vertical" size={0}>
          <Text strong>{id}</Text>
          <Text type="secondary">{record.type}</Text>
        </Space>
      ),
    },
    {
      title: 'Status',
      dataIndex: 'status',
      key: 'status',
      width: 110,
      render: (status: JobStatus) => <Tag color={STATUS_COLORS[status]}>{STATUS_LABELS[status]}</Tag>,
    },
    {
      title: 'Updated',
      dataIndex: 'updatedAt',
      key: 'updatedAt',
      width: 150,
      render: formatDateTime,
    },
    {
      title: 'Logs',
      key: 'logs',
      ellipsis: true,
      render: (_, record) => renderLogPreview(record),
    },
    {
      title: 'Actions',
      key: 'actions',
      width: 170,
      render: (_, record) => (
        <Space>
          <Button
            size="small"
            icon={<ReloadOutlined />}
            disabled={record.status !== 'failed'}
            loading={actionLoading === record.id && record.status === 'failed'}
            onClick={() => onRetry(record)}
          >
            Retry
          </Button>
          <Button
            size="small"
            danger
            icon={<CloseCircleOutlined />}
            disabled={record.status !== 'queued' && record.status !== 'running'}
            loading={
              actionLoading === record.id && (record.status === 'queued' || record.status === 'running')
            }
            onClick={() => onCancel(record)}
          >
            Cancel
          </Button>
        </Space>
      ),
    },
  ];

  return (
    <Card
      title="Job Queue"
      extra={
        <Button size="small" type="link" icon={<ArrowRightOutlined />} onClick={onOpenJobs}>
          Open
        </Button>
      }
    >
      <Space direction="vertical" size="middle" style={{ width: '100%' }}>
        {error && <Alert type="error" showIcon message="Unable to load jobs" description={error} />}
        <Table
          size="small"
          rowKey="id"
          columns={columns}
          dataSource={recentJobs}
          loading={loading}
          pagination={false}
          locale={{
            emptyText: <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="No recent jobs" />,
          }}
        />
      </Space>
    </Card>
  );
}

function renderLogPreview(job: JobRecord) {
  if (job.error) {
    return <Text type="danger">{job.error}</Text>;
  }
  const cleanLogs = job.logs.filter((line) => line.trim().length > 0);
  if (cleanLogs.length === 0) {
    return <Text type="secondary">-</Text>;
  }
  return <Text type="secondary">{cleanLogs.slice(-2).join(' | ')}</Text>;
}

function formatDateTime(value: string) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return date.toLocaleString('zh-CN', { hour12: false });
}
