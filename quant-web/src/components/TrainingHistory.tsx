import React, { useEffect, useState } from 'react';
import { Card, Table, Statistic, Row, Col, Spin, Alert, Progress } from 'antd';
import { CheckCircleOutlined } from '@ant-design/icons';
import type { ColumnsType } from 'antd/es/table';

interface TrainingRecord {
  timestamp: string;
  start_time?: string;
  end_time?: string;
  duration_seconds?: number;
  model_type: string;
  n_features: number;
  total_samples: number;
  cv_accuracy: number;
  cv_auc: number;
  test_accuracy: number;
  test_auc: number;
  class_balance: number;
}

const TrainingHistory: React.FC = () => {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [history, setHistory] = useState<TrainingRecord[]>([]);

  useEffect(() => {
    fetchTrainingHistory();
  }, []);

  const fetchTrainingHistory = async () => {
    try {
      setLoading(true);
      const response = await fetch('/api/training/history');
      const data = await response.json();

      if (data.error) {
        setError(data.error);
      } else {
        setHistory(data.history || []);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : '获取训练历史失败');
    } finally {
      setLoading(false);
    }
  };

  const formatDuration = (seconds?: number): string => {
    if (!seconds) return '未记录';
    if (seconds < 60) return `${Math.round(seconds)}秒`;
    if (seconds < 3600) {
      const minutes = Math.floor(seconds / 60);
      const secs = Math.round(seconds % 60);
      return `${minutes}分${secs}秒`;
    }
    const hours = Math.floor(seconds / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    return `${hours}小时${minutes}分`;
  };

  const columns: ColumnsType<TrainingRecord> = [
    {
      title: '训练时间',
      dataIndex: 'timestamp',
      key: 'timestamp',
      width: 180,
      render: (timestamp: string) => new Date(timestamp).toLocaleString('zh-CN')
    },
    {
      title: '模型类型',
      dataIndex: 'model_type',
      key: 'model_type',
      width: 120,
      render: (type: string) => type.toUpperCase()
    },
    {
      title: '特征数',
      dataIndex: 'n_features',
      key: 'n_features',
      width: 100
    },
    {
      title: '样本数',
      dataIndex: 'total_samples',
      key: 'total_samples',
      width: 100
    },
    {
      title: '交叉验证准确率',
      dataIndex: 'cv_accuracy',
      key: 'cv_accuracy',
      width: 150,
      sorter: (a, b) => a.cv_accuracy - b.cv_accuracy,
      render: (value: number) => (
        <Progress
          percent={parseFloat((value * 100).toFixed(2))}
          size="small"
          status={value >= 0.8 ? 'success' : value >= 0.7 ? 'normal' : 'exception'}
        />
      )
    },
    {
      title: 'CV AUC',
      dataIndex: 'cv_auc',
      key: 'cv_auc',
      width: 100,
      sorter: (a, b) => a.cv_auc - b.cv_auc,
      render: (value: number) => value.toFixed(4)
    },
    {
      title: '测试准确率',
      dataIndex: 'test_accuracy',
      key: 'test_accuracy',
      width: 120,
      sorter: (a, b) => a.test_accuracy - b.test_accuracy,
      render: (value: number) => `${(value * 100).toFixed(2)}%`
    },
    {
      title: '测试 AUC',
      dataIndex: 'test_auc',
      key: 'test_auc',
      width: 100,
      sorter: (a, b) => a.test_auc - b.test_auc,
      render: (value: number) => value.toFixed(4)
    },
    {
      title: '正样本比例',
      dataIndex: 'class_balance',
      key: 'class_balance',
      width: 120,
      render: (value: number) => `${(value * 100).toFixed(1)}%`
    },
    {
      title: '训练时长',
      key: 'duration',
      width: 200,
      render: (record: TrainingRecord) => {
        if (!record.start_time || !record.end_time || !record.duration_seconds) {
          return <span style={{ color: '#999' }}>未记录</span>;
        }
        const startTime = new Date(record.start_time).toLocaleTimeString('zh-CN');
        const endTime = new Date(record.end_time).toLocaleTimeString('zh-CN');
        const duration = formatDuration(record.duration_seconds);
        return `${startTime} - ${endTime} (${duration})`;
      }
    }
  ];

  const latestModel = history.length > 0 ? history[0] : null;

  if (loading) {
    return (
      <div style={{ textAlign: 'center', padding: '50px' }}>
        <Spin size="large" />
      </div>
    );
  }

  if (error) {
    return <Alert message="错误" description={error} type="error" showIcon />;
  }

  return (
    <div style={{ padding: '24px' }}>
      <h1>训练历史</h1>

      {latestModel && (
        <Row gutter={16} style={{ marginBottom: '24px' }}>
          <Col span={6}>
            <Card>
              <Statistic
                title="最新模型"
                value={latestModel.model_type.toUpperCase()}
                prefix={<CheckCircleOutlined style={{ color: '#52c41a' }} />}
              />
              <div style={{ marginTop: '8px', fontSize: '12px', color: '#888' }}>
                {new Date(latestModel.timestamp).toLocaleString('zh-CN')}
              </div>
            </Card>
          </Col>
          <Col span={6}>
            <Card>
              <Statistic
                title="交叉验证准确率"
                value={(latestModel.cv_accuracy * 100).toFixed(2)}
                suffix="%"
                valueStyle={{ color: latestModel.cv_accuracy >= 0.8 ? '#3f8600' : '#000' }}
              />
            </Card>
          </Col>
          <Col span={6}>
            <Card>
              <Statistic
                title="测试准确率"
                value={(latestModel.test_accuracy * 100).toFixed(2)}
                suffix="%"
                valueStyle={{ color: latestModel.test_accuracy >= 0.7 ? '#3f8600' : '#000' }}
              />
            </Card>
          </Col>
          <Col span={6}>
            <Card>
              <Statistic
                title="特征数 / 样本数"
                value={latestModel.n_features}
                suffix={`/ ${latestModel.total_samples}`}
              />
            </Card>
          </Col>
        </Row>
      )}

      <Card title={`训练记录 (共 ${history.length} 次)`}>
        <Table
          columns={columns}
          dataSource={history}
          rowKey={(record) => record.timestamp}
          pagination={{ pageSize: 10 }}
        />
      </Card>
    </div>
  );
};

export default TrainingHistory;
