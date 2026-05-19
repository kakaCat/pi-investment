import React from 'react'
import { Card, Alert, Steps, Typography, Space, Button } from 'antd'
import { CheckCircleOutlined, CloseCircleOutlined, SyncOutlined } from '@ant-design/icons'

const { Title, Paragraph, Text } = Typography

interface SystemStatus {
  backend: boolean
  database: boolean
  model: boolean
}

export default function Welcome() {
  const [status, setStatus] = React.useState<SystemStatus>({
    backend: false,
    database: false,
    model: false
  })
  const [loading, setLoading] = React.useState(true)

  React.useEffect(() => {
    checkStatus()
  }, [])

  const checkStatus = async () => {
    setLoading(true)
    try {
      const response = await fetch('/api/health')
      const data = await response.json()
      setStatus({
        backend: data.status === 'ok',
        database: data.db_connected,
        model: data.model_loaded
      })
    } catch (error) {
      console.error('Failed to check status:', error)
    } finally {
      setLoading(false)
    }
  }

  const getStatusIcon = (isOk: boolean) => {
    if (loading) return <SyncOutlined spin />
    return isOk ? <CheckCircleOutlined style={{ color: '#52c41a' }} /> : <CloseCircleOutlined style={{ color: '#ff4d4f' }} />
  }

  return (
    <div style={{ padding: '24px' }}>
      <Space direction="vertical" size="large" style={{ width: '100%' }}>
        <Card>
          <Title level={2}>🎉 欢迎使用量化系统可视化平台</Title>
          <Paragraph>
            这是一个基于机器学习的量化投资分析系统，提供因子分析、股票预测、信号监控等功能。
          </Paragraph>
        </Card>

        <Card title="📊 系统状态" extra={<Button onClick={checkStatus} loading={loading}>刷新</Button>}>
          <Steps
            direction="vertical"
            items={[
              {
                title: '后端API服务',
                status: status.backend ? 'finish' : 'error',
                icon: getStatusIcon(status.backend),
                description: status.backend ? '✅ 运行正常 (http://localhost:5001)' : '❌ 连接失败'
              },
              {
                title: '数据库连接',
                status: status.database ? 'finish' : 'error',
                icon: getStatusIcon(status.database),
                description: status.database ? '✅ 已连接' : '❌ 未连接'
              },
              {
                title: 'ML模型',
                status: status.model ? 'finish' : 'wait',
                icon: getStatusIcon(status.model),
                description: status.model ? '✅ 已加载' : '⚠️ 未加载（需要训练）'
              }
            ]}
          />
        </Card>

        {!status.model && status.backend && status.database && (
          <Alert
            message="模型未训练"
            description={
              <Space direction="vertical">
                <Text>当前系统缺少训练好的ML模型，部分功能受限。</Text>
                <Text strong>原因：</Text>
                <ul style={{ marginBottom: 0 }}>
                  <li>数据量不足（需要至少180天的历史数据）</li>
                  <li>或者模型文件不存在</li>
                </ul>
                <Text strong>解决方案：</Text>
                <ol style={{ marginBottom: 0 }}>
                  <li>获取更多历史数据：<code>python scripts/fetch_data.py</code></li>
                  <li>训练模型：<code>python scripts/ml_retrain.py</code></li>
                </ol>
              </Space>
            }
            type="warning"
            showIcon
          />
        )}

        <Card title="🚀 快速开始">
          <Steps
            direction="vertical"
            items={[
              {
                title: '查看因子重要性',
                description: '点击左侧菜单"因子重要性"，查看哪些因子对预测最重要（需要模型）'
              },
              {
                title: '分析单只股票',
                description: '点击"股票分析"，输入股票代码（如000001），查看详细因子分析（需要模型）'
              },
              {
                title: '对比多只股票',
                description: '点击"股票对比"，添加多只股票进行横向对比（需要模型）'
              },
              {
                title: '查看交易信号',
                description: '点击"交易信号"，查看系统生成的买卖信号（需要模型）'
              }
            ]}
          />
        </Card>

        <Card title="📚 技术架构">
          <Paragraph>
            <ul>
              <li><strong>前端：</strong>React 18 + TypeScript + Ant Design + Recharts</li>
              <li><strong>后端：</strong>Flask + Python 3.14</li>
              <li><strong>数据库：</strong>SQLite</li>
              <li><strong>机器学习：</strong>XGBoost + LightGBM</li>
              <li><strong>因子库：</strong>52个量化因子（技术27个 + 基本面25个）</li>
            </ul>
          </Paragraph>
        </Card>

        <Card title="💡 使用提示">
          <Alert
            message="当前状态"
            description={
              status.model
                ? '✅ 系统完全就绪，所有功能可用'
                : '⚠️ 模型未加载，可以查看系统架构，但预测功能暂不可用'
            }
            type={status.model ? 'success' : 'info'}
            showIcon
          />
        </Card>
      </Space>
    </div>
  )
}
