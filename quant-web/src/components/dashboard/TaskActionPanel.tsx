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
    title: '数据更新',
    description: '刷新最近行情数据',
    params: { source: 'hs300', days: 5, force: false },
  },
  {
    type: 'factor_compute',
    title: '因子计算',
    description: '重新计算因子数据集',
    params: {},
  },
  {
    type: 'signal_generate',
    title: '生成信号',
    description: '生成最新研究信号',
    params: {},
  },
  {
    type: 'risk_check',
    title: '风险检查',
    description: '检查当前组合风险',
    params: {},
  },
  {
    type: 'model_train',
    title: '模型训练',
    description: '触发模型重新训练',
    params: { days: 90, model: 'xgboost', cvSplits: 5 },
  },
  {
    type: 'backtest_run',
    title: '执行回测',
    description: '运行默认回测流程',
    params: {},
    danger: true,
  },
  {
    type: 'daily_report',
    title: '日报生成',
    description: '生成每日研究报告',
    params: {},
  },
];

export default function TaskActionPanel({
  activeJobTypes,
  actionLoading = null,
  onRunTask,
}: TaskActionPanelProps) {
  return (
    <Card title="任务操作" extra={<Text type="secondary">任务会进入后台队列执行</Text>}>
      <div style={taskGridStyle}>
        {TASK_ACTIONS.map((task) => {
          const isActive = activeJobTypes.has(task.type);
          return (
            <div style={taskItemStyle} key={task.type}>
              <Space direction="vertical" size="small" style={{ width: '100%' }}>
                <Space align="start" style={{ justifyContent: 'space-between', width: '100%' }}>
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
                  {isActive ? '执行中' : '运行任务'}
                </Button>
              </Space>
            </div>
          );
        })}
      </div>
    </Card>
  );
}

const taskGridStyle: React.CSSProperties = {
  display: 'grid',
  gap: 12,
  gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))',
};

const taskItemStyle: React.CSSProperties = {
  border: '1px solid #f0f0f0',
  borderRadius: 6,
  minWidth: 0,
  padding: 12,
};
