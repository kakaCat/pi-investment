import { Button, Card, Space, Tag, Typography } from 'antd';
import { PlayCircleOutlined } from '@ant-design/icons';

const { Text } = Typography;

type TaskType =
  | 'data_update'
  | 'factor_compute'
  | 'signal_generate'
  | 'risk_check'
  | 'model_train'
  | 'backtest_run'
  | 'daily_report';

interface TaskAction {
  type: TaskType;
  title: string;
  description: string;
  params: Record<string, unknown>;
  danger?: boolean;
}

export interface TaskActionPanelProps {
  activeJobTypes: Set<string>;
  actionLoading?: string | null;
  onRunTask: (type: string, params: Record<string, unknown>) => void;
}

const TASK_ACTIONS: TaskAction[] = [
  {
    type: 'data_update',
    title: 'Data Update',
    description: 'Refresh recent market data',
    params: { source: 'hs300', days: 5, force: false },
  },
  {
    type: 'factor_compute',
    title: 'Factor Compute',
    description: 'Recalculate factor datasets',
    params: {},
  },
  {
    type: 'signal_generate',
    title: 'Signal Generate',
    description: 'Generate latest research signals',
    params: {},
  },
  {
    type: 'risk_check',
    title: 'Risk Check',
    description: 'Run current portfolio risk checks',
    params: {},
  },
  {
    type: 'model_train',
    title: 'Model Train',
    description: 'Trigger model retraining',
    params: { days: 90, model: 'xgboost', cvSplits: 5 },
  },
  {
    type: 'backtest_run',
    title: 'Backtest Run',
    description: 'Run the default backtest workflow',
    params: {},
    danger: true,
  },
  {
    type: 'daily_report',
    title: 'Daily Report',
    description: 'Generate the daily research report',
    params: {},
  },
];

export default function TaskActionPanel({
  activeJobTypes,
  actionLoading = null,
  onRunTask,
}: TaskActionPanelProps) {
  return (
    <Card title="Task Actions" extra={<Text type="secondary">Tasks run in the job queue</Text>}>
      <div style={{ display: 'grid', gap: 12, gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))' }}>
        {TASK_ACTIONS.map((task) => {
          const isActive = activeJobTypes.has(task.type);
          return (
            <div style={taskItemStyle} key={task.type}>
              <Space direction="vertical" size="small" style={{ width: '100%' }}>
                <Space style={{ justifyContent: 'space-between', width: '100%' }}>
                  <Text strong>{task.title}</Text>
                  <Tag>{task.type}</Tag>
                </Space>
                <Text type="secondary">{task.description}</Text>
                <Button
                  block
                  danger={task.danger}
                  icon={<PlayCircleOutlined />}
                  loading={actionLoading === task.type}
                  disabled={isActive}
                  onClick={() => onRunTask(task.type, task.params)}
                >
                  {isActive ? 'Already active' : 'Run task'}
                </Button>
              </Space>
            </div>
          );
        })}
      </div>
    </Card>
  );
}

const taskItemStyle: React.CSSProperties = {
  border: '1px solid #f0f0f0',
  borderRadius: 6,
  padding: 12,
};
