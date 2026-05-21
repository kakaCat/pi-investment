import { Suspense, lazy, useState } from 'react'
import { Layout, Menu, Spin, Typography } from 'antd'
import type { MenuProps } from 'antd'
import { HomeOutlined, BarChartOutlined, StockOutlined, DashboardOutlined, SignalFilled, ExperimentOutlined, HistoryOutlined, DatabaseOutlined, RocketOutlined, CloudServerOutlined, ApartmentOutlined } from '@ant-design/icons'

const { Header, Sider, Content } = Layout
const { Text, Title } = Typography

const MENU_KEYS = [
  'dashboard',
  'welcome',
  'feature-importance',
  'stock-analysis',
  'stock-comparison',
  'signals',
  'backtest',
  'pipeline',
  'training',
  'model-training',
  'stock-list',
  'stock-management',
  'ops'
] as const

type MenuKey = typeof MENU_KEYS[number]

const DashboardOverview = lazy(() => import('./components/dashboard/DashboardOverview'))
const Welcome = lazy(() => import('./components/Welcome'))
const FeatureImportance = lazy(() => import('./components/FeatureImportance'))
const StockAnalysis = lazy(() => import('./components/StockAnalysis'))
const StockComparison = lazy(() => import('./components/StockComparison'))
const SignalsDashboard = lazy(() => import('./components/SignalsDashboard'))
const BacktestDashboard = lazy(() => import('./components/BacktestDashboard'))
const QuantPipeline = lazy(() => import('./components/QuantPipeline'))
const TrainingHistory = lazy(() => import('./components/TrainingHistory'))
const StockList = lazy(() => import('./components/StockList'))
const StockManagement = lazy(() => import('./components/StockManagement'))
const ModelTraining = lazy(() => import('./components/ModelTraining'))
const OpsCenter = lazy(() => import('./components/OpsCenter'))

function App() {
  const [selectedMenu, setSelectedMenu] = useState<MenuKey>('dashboard')

  const navigateTo = (key: string) => {
    if (isMenuKey(key)) {
      setSelectedMenu(key)
    }
  }

  const renderContent = () => {
    switch (selectedMenu) {
      case 'dashboard':
        return (
          <div className="dashboard-page">
            <DashboardOverview onNavigate={navigateTo} />
          </div>
        )
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
      case 'pipeline':
        return <QuantPipeline />
      case 'training':
        return <TrainingHistory />
      case 'model-training':
        return <ModelTraining />
      case 'stock-list':
        return <StockList />
      case 'stock-management':
        return <StockManagement />
      case 'ops':
        return <OpsCenter />
      default:
        return (
          <div className="dashboard-page">
            <DashboardOverview onNavigate={navigateTo} />
          </div>
        )
    }
  }

  const menuItems: MenuProps['items'] = [
    {
      key: 'overview',
      label: '总览',
      type: 'group',
      children: [
        {
          key: 'dashboard',
          icon: <DashboardOutlined />,
          label: '仪表盘'
        }
      ]
    },
    {
      key: 'research',
      label: '研究',
      type: 'group',
      children: [
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
          key: 'pipeline',
          icon: <ApartmentOutlined />,
          label: '量化链路'
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
        }
      ]
    },
    {
      key: 'model',
      label: '模型',
      type: 'group',
      children: [
        {
          key: 'model-training',
          icon: <RocketOutlined />,
          label: '模型训练'
        },
        {
          key: 'training',
          icon: <HistoryOutlined />,
          label: '训练历史'
        }
      ]
    },
    {
      key: 'data',
      label: '数据',
      type: 'group',
      children: [
        {
          key: 'stock-list',
          icon: <DatabaseOutlined />,
          label: '股票列表'
        },
        {
          key: 'stock-management',
          icon: <StockOutlined />,
          label: '股票管理'
        }
      ]
    },
    {
      key: 'operations',
      label: '运维',
      type: 'group',
      children: [
        {
          key: 'ops',
          icon: <CloudServerOutlined />,
          label: '运维中心'
        },
        {
          key: 'welcome',
          icon: <HomeOutlined />,
          label: '系统信息'
        }
      ]
    }
  ]

  return (
    <Layout className="app-shell">
      <Header className="app-header">
        <div>
          <Title level={3} style={{ color: 'white', margin: 0 }}>
            量化管理台
          </Title>
          <Text className="app-header-subtitle">Quant Management Console</Text>
        </div>
      </Header>
      <Layout>
        <Sider width={232} style={{ background: '#fff' }}>
          <Menu
            mode="inline"
            selectedKeys={[selectedMenu]}
            style={{ height: '100%', borderRight: 0 }}
            onSelect={({ key }) => navigateTo(String(key))}
            items={menuItems}
          />
        </Sider>
        <Layout>
          <Content className="app-content">
            <Suspense fallback={<Spin className="app-content-loading" />}>
              {renderContent()}
            </Suspense>
          </Content>
        </Layout>
      </Layout>
    </Layout>
  )
}

function isMenuKey(value: string): value is MenuKey {
  return (MENU_KEYS as readonly string[]).includes(value)
}

export default App
