import React, { useState, useEffect } from 'react';
import {
  Card,
  Form,
  InputNumber,
  Select,
  Switch,
  Button,
  Progress,
  Alert,
  Statistic,
  Row,
  Col,
  Table,
  Tag,
  Space,
  Modal,
  Descriptions
} from 'antd';
import {
  PlayCircleOutlined,
  CheckCircleOutlined,
  CloseCircleOutlined,
  SyncOutlined,
  HistoryOutlined
} from '@ant-design/icons';
import type { ColumnsType } from 'antd/es/table';

const { Option } = Select;

interface TrainingParams {
  days: number;
  model: 'xgboost' | 'lightgbm' | 'random_forest';
  cvSplits: number;
  useFeatureEngineering: boolean;
}

interface TrainingTask {
  id: string;
  status: 'running' | 'completed' | 'failed';
  progress: number;
  startTime: string;
  endTime?: string;
  params: TrainingParams;
  result?: any;
  error?: string;
}

interface TrainingReport {
  filename: string;
  timestamp: string;
  metrics?: any;
  params?: any;
  n_features: number;
}

const ModelTraining: React.FC = () => {
  const [form] = Form.useForm();
  const [loading, setLoading] = useState(false);
  const [currentTask, setCurrentTask] = useState<TrainingTask | null>(null);
  const [reports, setReports] = useState<TrainingReport[]>([]);
  const [selectedReport, setSelectedReport] = useState<any>(null);
  const [modalVisible, setModalVisible] = useState(false);

  useEffect(() => {
    fetchReports();
  }, []);

  useEffect(() => {
    let interval: NodeJS.Timeout;
    if (currentTask && currentTask.status === 'running') {
      interval = setInterval(() => {
        pollTaskStatus(currentTask.id);
      }, 3000);
    }
    return () => {
      if (interval) clearInterval(interval);
    };
  }, [currentTask]);

  const fetchReports = async () => {
    try {
      const response = await fetch('/api/training/reports');
      const data = await response.json();
      if (data.success) {
        setReports(data.data);
      }
    } catch (error) {
      console.error('Failed to fetch reports:', error);
    }
  };

  const startTraining = async (values: TrainingParams) => {
    try {
      setLoading(true);
      const response = await fetch('/api/training/start', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(values)
      });

      const data = await response.json();
      if (data.success) {
        setCurrentTask({
          id: data.data.taskId,
          status: 'running',
          progress: 0,
          startTime: new Date().toISOString(),
          params: values
        });
      }
    } catch (error) {
      console.error('Failed to start training:', error);
    } finally {
      setLoading(false);
    }
  };

  const pollTaskStatus = async (taskId: string) => {
    try {
      const response = await fetch(`/api/training/status/${taskId}`);
      const data = await response.json();

      if (data.success) {
        setCurrentTask(data.data);

        if (data.data.status === 'completed' || data.data.status === 'failed') {
          fetchReports();
        }
      }
    } catch (error) {
      console.error('Failed to poll task status:', error);
    }
  };

  const viewReportDetail = async (filename: string) => {
    try {
      const response = await fetch(`/api/training/report/${filename}`);
      const data = await response.json();
      if (data.success) {
        setSelectedReport(data.data);
        setModalVisible(true);
      }
    } catch (error) {
      console.error('Failed to fetch report detail:', error);
    }
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'running':
        return <SyncOutlined spin style={{ color: '#1890ff' }} />;
      case 'completed':
        return <CheckCircleOutlined style={{ color: '#52c41a' }} />;
      case 'failed':
        return <CloseCircleOutlined style={{ color: '#ff4d4f' }} />;
      default:
        return null;
    }
  };

  const reportColumns: ColumnsType<TrainingReport> = [
    {
      title: '训练时间',
      dataIndex: 'timestamp',
      key: 'timestamp',
      render: (timestamp: string) => {
        const year = timestamp.substring(0, 4);
        const month = timestamp.substring(4, 6);
        const day = timestamp.substring(6, 8);
        const hour = timestamp.substring(9, 11);
        const minute = timestamp.substring(11, 13);
        const second = timestamp.substring(13, 15);
        return `${year}-${month}-${day} ${hour}:${minute}:${second}`;
      }
    },
    {
      title: '特征数',
      dataIndex: 'n_features',
      key: 'n_features',
      render: (n: number) => (
        <Tag color={n >= 49 ? 'green' : 'blue'}>{n} 个特征</Tag>
      )
    },
    {
      title: '操作',
      key: 'action',
      render: (_, record) => (
        <Button
          type="link"
          icon={<HistoryOutlined />}
          onClick={() => viewReportDetail(record.filename)}
        >
          查看详情
        </Button>
      )
    }
  ];

  return (
    <div style={{ padding: '24px' }}>
      <h1>模型训练</h1>

      {/* 训练配置表单 */}
      <Card title="训练配置" style={{ marginBottom: '24px' }}>
        <Form
          form={form}
          layout="vertical"
          initialValues={{
            days: 90,
            model: 'xgboost',
            cvSplits: 5,
            useFeatureEngineering: true
          }}
          onFinish={startTraining}
        >
          <Row gutter={16}>
            <Col span={6}>
              <Form.Item
                label="训练天数"
                name="days"
                rules={[
                  { required: true, message: '请输入训练天数' },
                  { type: 'number', min: 30, max: 365, message: '天数范围: 30-365' }
                ]}
              >
                <InputNumber
                  style={{ width: '100%' }}
                  min={30}
                  max={365}
                  placeholder="30-365天"
                />
              </Form.Item>
            </Col>

            <Col span={6}>
              <Form.Item
                label="模型类型"
                name="model"
                rules={[{ required: true, message: '请选择模型类型' }]}
              >
                <Select>
                  <Option value="xgboost">XGBoost</Option>
                  <Option value="lightgbm">LightGBM</Option>
                  <Option value="random_forest">Random Forest</Option>
                </Select>
              </Form.Item>
            </Col>

            <Col span={6}>
              <Form.Item
                label="交叉验证折数"
                name="cvSplits"
                rules={[
                  { required: true, message: '请输入折数' },
                  { type: 'number', min: 2, max: 10, message: '折数范围: 2-10' }
                ]}
              >
                <InputNumber
                  style={{ width: '100%' }}
                  min={2}
                  max={10}
                  placeholder="2-10折"
                />
              </Form.Item>
            </Col>

            <Col span={6}>
              <Form.Item
                label="使用高级特征工程"
                name="useFeatureEngineering"
                valuePropName="checked"
                tooltip="开启后使用49个高级特征，关闭则使用38个原始特征"
              >
                <Switch
                  checkedChildren="开启 (49特征)"
                  unCheckedChildren="关闭 (38特征)"
                />
              </Form.Item>
            </Col>
          </Row>

          <Form.Item>
            <Button
              type="primary"
              htmlType="submit"
              icon={<PlayCircleOutlined />}
              loading={loading}
              disabled={currentTask?.status === 'running'}
            >
              开始训练
            </Button>
          </Form.Item>
        </Form>
      </Card>

      {/* 当前训练任务状态 */}
      {currentTask && (
        <Card
          title={
            <Space>
              {getStatusIcon(currentTask.status)}
              <span>训练任务: {currentTask.id}</span>
            </Space>
          }
          style={{ marginBottom: '24px' }}
        >
          <Row gutter={16} style={{ marginBottom: '16px' }}>
            <Col span={6}>
              <Statistic
                title="状态"
                value={
                  currentTask.status === 'running'
                    ? '进行中'
                    : currentTask.status === 'completed'
                    ? '已完成'
                    : '失败'
                }
                valueStyle={{
                  color:
                    currentTask.status === 'running'
                      ? '#1890ff'
                      : currentTask.status === 'completed'
                      ? '#52c41a'
                      : '#ff4d4f'
                }}
              />
            </Col>
            <Col span={6}>
              <Statistic
                title="训练天数"
                value={currentTask.params.days}
                suffix="天"
              />
            </Col>
            <Col span={6}>
              <Statistic
                title="模型类型"
                value={currentTask.params.model.toUpperCase()}
              />
            </Col>
            <Col span={6}>
              <Statistic
                title="特征类型"
                value={currentTask.params.useFeatureEngineering ? '高级特征' : '原始特征'}
              />
            </Col>
          </Row>

          {currentTask.status === 'running' && (
            <Progress percent={currentTask.progress} status="active" />
          )}

          {currentTask.status === 'completed' && currentTask.result && (
            <Alert
              message="训练完成"
              description={
                <div>
                  <p>准确率: {(currentTask.result.cv_results.mean_scores.accuracy * 100).toFixed(2)}%</p>
                  <p>AUC: {currentTask.result.cv_results.mean_scores.auc.toFixed(4)}</p>
                  <p>特征数: {currentTask.result.n_features}</p>
                </div>
              }
              type="success"
              showIcon
            />
          )}

          {currentTask.status === 'failed' && (
            <Alert
              message="训练失败"
              description={currentTask.error}
              type="error"
              showIcon
            />
          )}
        </Card>
      )}

      {/* 历史训练报告 */}
      <Card title={`历史训练报告 (共 ${reports.length} 次)`}>
        <Table
          columns={reportColumns}
          dataSource={reports}
          rowKey="filename"
          pagination={{ pageSize: 10 }}
        />
      </Card>

      {/* 报告详情模态框 */}
      <Modal
        title="训练报告详情"
        open={modalVisible}
        onCancel={() => setModalVisible(false)}
        footer={null}
        width={800}
      >
        {selectedReport && (
          <div>
            <Descriptions bordered column={2}>
              <Descriptions.Item label="训练时间">
                {selectedReport.timestamp}
              </Descriptions.Item>
              <Descriptions.Item label="特征数">
                {selectedReport.n_features}
              </Descriptions.Item>
            </Descriptions>

            {selectedReport.feature_names && (
              <div style={{ marginTop: '16px' }}>
                <h3>特征列表</h3>
                <div style={{ maxHeight: '300px', overflow: 'auto' }}>
                  {selectedReport.feature_names.map((name: string, idx: number) => (
                    <Tag key={idx} style={{ margin: '4px' }}>
                      {name}
                    </Tag>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}
      </Modal>
    </div>
  );
};

export default ModelTraining;
