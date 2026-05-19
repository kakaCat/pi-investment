import React, { useState } from 'react'
import { Layout, Menu, Typography } from 'antd'
import { HomeOutlined, BarChartOutlined, StockOutlined, DashboardOutlined, SignalFilled, ExperimentOutlined, HistoryOutlined, DatabaseOutlined, RocketOutlined } from '@ant-design/icons'
import Welcome from './components/Welcome'
import FeatureImportance from './components/FeatureImportance'
import StockAnalysis from './components/StockAnalysis'
import StockComparison from './components/StockComparison'
import SignalsDashboard from './components/SignalsDashboard'
import BacktestDashboard from './components/BacktestDashboard'
import TrainingHistory from './components/TrainingHistory'
import StockList from './components/StockList'
import ModelTraining from './components/ModelTraining'

const { Header, Sider, Content } = Layout
const { Title } = Typography

type MenuKey = 'welcome' | 'feature-importance' | 'stock-analysis' | 'stock-comparison' | 'signals' | 'backtest' | 'training' | 'model-training' | 'stock-list'

function App() {
  const [selectedMenu, setSelectedMenu] = useState<MenuKey>('welcome')

  const renderContent = () => {
    switch (selectedMenu) {
      case 'welcome':
        return <Welcome />
      case 'feature-importance':
        return <FeatureImportance />
      case 'stock-analysis':
        return <StockAnalysis />
      case 'stock-comparison':
        return <StockComparison />
      case 'signals':
        return <SignalsDashboard />
      case 'backtest':
        return <BacktestDashboard />
      case 'training':
        return <TrainingHistory />
      case 'model-training':
        return <ModelTraining />
      case 'stock-list':
        return <StockList />
      default:
        return <Welcome />
    }
  }

  return (
    <Layout style={{ minHeight: '100vh' }}>
      <Header style={{ background: '#001529', padding: '0 24px', display: 'flex', alignItems: 'center' }}>
        <Title level={3} style={{ color: 'white', margin: 0 }}>
          📊 量化系统可视化
        </Title>
      </Header>
      <Layout>
        <Sider width={200} style={{ background: '#fff' }}>
          <Menu
            mode="inline"
            selectedKeys={[selectedMenu]}
            style={{ height: '100%', borderRight: 0 }}
            onSelect={({ key }) => setSelectedMenu(key as MenuKey)}
            items={[
              {
                key: 'welcome',
                icon: <HomeOutlined />,
                label: '欢迎页'
              },
              {
                key: 'feature-importance',
                icon: <BarChartOutlined />,
                label: '因子重要性'
              },
              {
                key: 'stock-analysis',
                icon: <StockOutlined />,
                label: '股票分析'
              },
              {
                key: 'stock-comparison',
                icon: <DashboardOutlined />,
                label: '股票对比'
              },
              {
                key: 'signals',
                icon: <SignalFilled />,
                label: '交易信号'
              },
              {
                key: 'backtest',
                icon: <ExperimentOutlined />,
                label: '回测仪表板'
              },
              {
                key: 'model-training',
                icon: <RocketOutlined />,
                label: '模型训练'
              },
              {
                key: 'training',
                icon: <HistoryOutlined />,
                label: '训练历史'
              },
              {
                key: 'stock-list',
                icon: <DatabaseOutlined />,
                label: '股票列表'
              }
            ]}
          />
        </Sider>
        <Layout style={{ padding: '24px' }}>
          <Content
            style={{
              background: '#fff',
              padding: 24,
              margin: 0,
              minHeight: 280,
              borderRadius: 8
            }}
          >
            {renderContent()}
          </Content>
        </Layout>
      </Layout>
    </Layout>
  )
}

export default App
