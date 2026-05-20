import React, { useEffect, useState } from 'react'
import { Card, Spin, Alert, Typography, Row, Col, Statistic } from 'antd'
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer, PieChart, Pie, Cell } from 'recharts'
import axios from 'axios'

const { Title, Text } = Typography

interface Feature {
  feature: string
  importance: number
  percentage: number
  cumulative: number
}

interface FeatureImportanceData {
  features: Feature[]
  total_features: number
  top_20_percent_count: number
}

const COLORS = ['#0088FE', '#00C49F', '#FFBB28', '#FF8042', '#8884D8', '#82CA9D', '#FFC658', '#FF6B6B']

const FeatureImportance: React.FC = () => {
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [data, setData] = useState<FeatureImportanceData | null>(null)

  useEffect(() => {
    fetchData()
  }, [])

  const fetchData = async () => {
    try {
      setLoading(true)
      setError(null)
      const response = await axios.get('/api/feature-importance')
      setData(response.data)
    } catch (err: any) {
      setError(err.response?.data?.error || '获取数据失败')
    } finally {
      setLoading(false)
    }
  }

  if (loading) {
    return (
      <div style={{ textAlign: 'center', padding: '100px 0' }}>
        <Spin size="large" />
        <div style={{ marginTop: 16 }}>加载因子重要性数据...</div>
      </div>
    )
  }

  if (error) {
    return (
      <Alert
        message="加载失败"
        description={error}
        type="error"
        showIcon
      />
    )
  }

  if (!data) return null

  const top15 = data.features.slice(0, 15)
  const top5 = data.features.slice(0, 5)

  return (
    <div>
      <Title level={2}>📊 因子重要性分析</Title>
      <Text type="secondary">了解模型主要依赖哪些指标进行预测</Text>

      {/* 统计卡片 */}
      <Row gutter={16} style={{ marginTop: 24, marginBottom: 24 }}>
        <Col span={8}>
          <Card>
            <Statistic
              title="总因子数"
              value={data.total_features}
              suffix="个"
            />
          </Card>
        </Col>
        <Col span={8}>
          <Card>
            <Statistic
              title="核心因子数"
              value={data.top_20_percent_count}
              suffix="个"
              valueStyle={{ color: '#3f8600' }}
            />
            <Text type="secondary" style={{ fontSize: 12 }}>贡献80%预测能力</Text>
          </Card>
        </Col>
        <Col span={8}>
          <Card>
            <Statistic
              title="最重要因子"
              value={data.features[0].feature}
              valueStyle={{ fontSize: 16 }}
            />
            <Text type="secondary" style={{ fontSize: 12 }}>
              贡献 {data.features[0].percentage.toFixed(2)}%
            </Text>
          </Card>
        </Col>
      </Row>

      {/* Top 15 柱状图 */}
      <Card title="🏆 Top 15 最重要因子" style={{ marginBottom: 24 }}>
        <ResponsiveContainer width="100%" height={400}>
          <BarChart data={top15} layout="vertical" margin={{ left: 100 }}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis type="number" />
            <YAxis type="category" dataKey="feature" />
            <Tooltip
              formatter={(value: number, name: string) => {
                if (name === 'importance') return [value.toFixed(4), '重要性']
                if (name === 'percentage') return [`${value.toFixed(2)}%`, '占比']
                return [value, name]
              }}
            />
            <Legend />
            <Bar dataKey="importance" fill="#1890ff" name="重要性" />
          </BarChart>
        </ResponsiveContainer>
      </Card>

      {/* Top 5 饼图 */}
      <Card title="📈 Top 5 因子占比">
        <ResponsiveContainer width="100%" height={300}>
          <PieChart>
            <Pie
              data={top5}
              dataKey="percentage"
              nameKey="feature"
              cx="50%"
              cy="50%"
              outerRadius={100}
              label={({ feature, percentage }) => `${feature}: ${percentage.toFixed(1)}%`}
            >
              {top5.map((_, index) => (
                <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
              ))}
            </Pie>
            <Tooltip formatter={(value: number) => `${value.toFixed(2)}%`} />
          </PieChart>
        </ResponsiveContainer>
      </Card>

      {/* 解读 */}
      <Card title="💡 解读" style={{ marginTop: 24 }}>
        <ul>
          <li>
            前 <strong>{data.top_20_percent_count}</strong> 个因子贡献了 <strong>80%</strong> 的预测能力（80/20法则）
          </li>
          <li>
            <strong>{data.features[0].feature}</strong> 是最重要的因子，贡献 <strong>{data.features[0].percentage.toFixed(2)}%</strong>
          </li>
          <li>
            前3个因子合计贡献 <strong>
              {data.features.slice(0, 3).reduce((sum, f) => sum + f.percentage, 0).toFixed(2)}%
            </strong>
          </li>
        </ul>
      </Card>
    </div>
  )
}

export default FeatureImportance
