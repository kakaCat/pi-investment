import { createRouter, createWebHistory } from 'vue-router'
import type { RouteRecordRaw } from 'vue-router'
import { ElLoading } from 'element-plus'

// 懒加载布局组件
const MainLayout = () => import('@/components/layout/MainLayout.vue')

// 路由加载状态管理
let loadingInstance: ReturnType<typeof ElLoading.service> | null = null
let loadingTimer: ReturnType<typeof setTimeout> | null = null
let loadingSequence = 0

const routes: RouteRecordRaw[] = [
  {
    path: '/',
    component: MainLayout,
    redirect: '/dashboard',
    children: [
      {
        path: '/dashboard',
        name: 'Dashboard',
        component: () => import(/* webpackChunkName: "dashboard" */ '@/views/Dashboard/index.vue'),
        meta: { title: '仪表盘', preload: true }
      },
      {
        path: '/indicator-ide',
        name: 'IndicatorIDE',
        component: () => import(/* webpackChunkName: "indicator-ide" */ '@/views/IndicatorIDE/index.vue'),
        meta: { title: '指标IDE' }
      },
      {
        path: '/stock-list',
        name: 'StockList',
        component: () => import(/* webpackChunkName: "stock-list" */ '@/views/StockList/index.vue'),
        meta: { title: '图表研究' }
      },
      {
        path: '/stocks/:symbol',
        name: 'StockDetail',
        component: () => import(/* webpackChunkName: "stock-detail" */ '@/views/StockDetail/index.vue'),
        meta: { title: '股票详情' }
      },
      {
        path: '/factors',
        name: 'FactorAnalysis',
        component: () => import(/* webpackChunkName: "factor-analysis" */ '@/views/FactorAnalysis/index.vue'),
        meta: { title: '因子分析' }
      },
      {
        path: '/signals',
        name: 'SignalList',
        component: () => import(/* webpackChunkName: "signal-list" */ '@/views/SignalList/index.vue'),
        meta: { title: '交易信号' }
      },
      {
        path: '/opportunity-radar',
        name: 'OpportunityRadar',
        component: () => import(/* webpackChunkName: "opportunity-radar" */ '@/views/OpportunityRadar/index.vue'),
        meta: { title: '机会雷达' }
      },
      {
        path: '/pools',
        name: 'PoolList',
        component: () => import(/* webpackChunkName: "pool-list" */ '@/views/PoolList/index.vue'),
        meta: { title: '股票池' }
      },
      {
        path: '/pools/:id',
        name: 'PoolDetail',
        component: () => import(/* webpackChunkName: "pool-detail" */ '@/views/PoolDetail/index.vue'),
        meta: { title: '股票池详情' }
      },
      {
        path: '/backtest',
        name: 'BacktestCenter',
        component: () => import(/* webpackChunkName: "backtest-center" */ '@/views/BacktestCenter/index.vue'),
        meta: { title: '回测与快速交易' }
      },
      {
        path: '/portfolio',
        name: 'Portfolio',
        component: () => import(/* webpackChunkName: "portfolio" */ '@/views/Portfolio/index.vue'),
        meta: { title: '持仓管理', preload: true }
      },
      {
        path: '/orders',
        name: 'Orders',
        component: () => import(/* webpackChunkName: "orders" */ '@/views/Orders/index.vue'),
        meta: { title: '订单管理' }
      },
      {
        path: '/risk',
        name: 'RiskCheck',
        component: () => import(/* webpackChunkName: "risk-check" */ '@/views/RiskCheck/index.vue'),
        meta: { title: '风控检查' }
      },
      {
        path: '/strategy-center',
        name: 'StrategyCenter',
        component: () => import(/* webpackChunkName: "strategy-center" */ '@/views/StrategyCenter/index.vue'),
        meta: { title: '策略运营中心' }
      },
      {
        path: '/ml',
        name: 'MLEngine',
        component: () => import(/* webpackChunkName: "ml-engine" */ '@/views/MLEngine/index.vue'),
        meta: { title: 'ML引擎' }
      },
      {
        path: '/trades',
        name: 'Trades',
        component: () => import(/* webpackChunkName: "trades" */ '@/views/Trades/index.vue'),
        meta: { title: '交易记录' }
      },
      {
        path: '/quant-pipeline',
        name: 'QuantPipeline',
        component: () => import(/* webpackChunkName: "quant-pipeline" */ '@/views/QuantPipeline/index.vue'),
        meta: { title: '量化链路' }
      },
      {
        path: '/strategy-config',
        name: 'StrategyConfig',
        component: () => import(/* webpackChunkName: "strategy-config" */ '@/views/StrategyConfig/index.vue'),
        meta: { title: '策略配置' }
      },
      {
        path: '/scheduler',
        name: 'Scheduler',
        component: () => import(/* webpackChunkName: "scheduler" */ '@/views/Scheduler/index.vue'),
        meta: { title: '定时任务' }
      },
      {
        path: '/data-update',
        name: 'DataUpdate',
        component: () => import(/* webpackChunkName: "data-update" */ '@/views/DataUpdate/index.vue'),
        meta: { title: '数据更新' }
      },
      {
        path: '/daily-report',
        name: 'DailyReport',
        component: () => import(/* webpackChunkName: "daily-report" */ '@/views/DailyReport/index.vue'),
        meta: { title: '日报' }
      },
      {
        path: '/executions',
        name: 'Executions',
        component: () => import(/* webpackChunkName: "executions" */ '@/views/Executions/index.vue'),
        meta: { title: '执行记录' }
      },
      // 博弈智能系统
      {
        path: '/game-intelligence',
        name: 'GameIntelligence',
        redirect: '/game-intelligence/dashboard',
        meta: { title: '博弈智能' },
        children: [
          {
            path: 'dashboard',
            name: 'GameIntelligenceDashboard',
            component: () => import(/* webpackChunkName: "game-intelligence" */ '@/views/GameIntelligence/Dashboard.vue'),
            meta: { title: '博弈智能 - 总览' }
          },
          {
            path: 'opponent-behavior',
            name: 'OpponentBehavior',
            component: () => import(/* webpackChunkName: "game-intelligence" */ '@/views/GameIntelligence/OpponentBehavior.vue'),
            meta: { title: '博弈智能 - 对手行为' }
          },
          {
            path: 'alerts',
            name: 'AlertCenter',
            component: () => import(/* webpackChunkName: "game-intelligence" */ '@/views/GameIntelligence/AlertCenter.vue'),
            meta: { title: '博弈智能 - 预警中心' }
          },
          {
            path: 'learning-loop',
            name: 'LearningLoop',
            component: () => import(/* webpackChunkName: "game-intelligence" */ '@/views/GameIntelligence/LearningLoop.vue'),
            meta: { title: '博弈智能 - 学习闭环' }
          },
          {
            path: 'automation-monitor',
            name: 'AutomationMonitor',
            component: () => import(/* webpackChunkName: "game-intelligence" */ '@/views/GameIntelligence/AutomationMonitor.vue'),
            meta: { title: '博弈智能 - 自动化监控' }
          },
          {
            path: 'automation-config',
            name: 'AutomationConfig',
            component: () => import(/* webpackChunkName: "game-intelligence" */ '@/views/GameIntelligence/AutomationConfig.vue'),
            meta: { title: '博弈智能 - 自动化配置' }
          }
        ]
      }
    ]
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

// 路由守卫
router.beforeEach((to, _from) => {
  // 清除上一次未触发的 loading timer
  if (loadingTimer) {
    clearTimeout(loadingTimer)
    loadingTimer = null
  }
  // 关闭上一次未关闭的 loading 实例
  if (loadingInstance) {
    loadingInstance.close()
    loadingInstance = null
  }

  // 使用递增序列号追踪本次导航，防止过期 timer 创建 loading
  const seq = ++loadingSequence

  // 显示加载状态（延迟200ms，避免快速切换时闪烁）
  loadingTimer = setTimeout(() => {
    if (loadingSequence === seq) {
      loadingInstance = ElLoading.service({
        lock: true,
        text: '加载中...',
        background: 'rgba(0, 0, 0, 0.7)'
      })
    }
  }, 200)

  // 设置页面标题
  if (to.meta.title) {
    document.title = `${to.meta.title} - 量化交易系统`
  }
})

router.afterEach(() => {
  // 递增序列号，使任何待处理的 loading timer 失效
  loadingSequence++
  if (loadingTimer) {
    clearTimeout(loadingTimer)
    loadingTimer = null
  }
  if (loadingInstance) {
    loadingInstance.close()
    loadingInstance = null
  }
})

// 路由错误处理
router.onError((error) => {
  console.error('路由加载错误:', error)
  if (loadingInstance) {
    loadingInstance.close()
    loadingInstance = null
  }
})

export default router
