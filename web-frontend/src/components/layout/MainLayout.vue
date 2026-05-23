<template>
  <div class="dashboard">
    <el-container>
      <!-- 侧边栏 -->
      <el-aside :width="isCollapsed ? '0px' : '240px'" class="sidebar" :class="{ collapsed: isCollapsed }">
        <div class="logo">
          <div class="logo-mark">Q</div>
          <span class="logo-text">QuantSys Pro</span>
        </div>
        <el-menu
          :default-active="activeMenu"
          router
          class="sidebar-menu"
        >
          <div class="menu-group-title">总览</div>
          <el-menu-item index="/dashboard">
            <el-icon><Odometer /></el-icon>
            <span>仪表盘</span>
          </el-menu-item>

          <div class="menu-group-title">研究分析</div>
          <el-menu-item index="/indicator-ide">
            <el-icon><Edit /></el-icon>
            <span>指标IDE</span>
          </el-menu-item>
          <el-menu-item index="/stock-list">
            <el-icon><TrendCharts /></el-icon>
            <span>图表研究</span>
          </el-menu-item>
          <el-menu-item index="/opportunity-radar">
            <el-icon><Aim /></el-icon>
            <span>机会雷达</span>
          </el-menu-item>
          <el-menu-item index="/backtest">
            <el-icon><Timer /></el-icon>
            <span>回测与快速交易</span>
          </el-menu-item>

          <div class="menu-group-title">交易风控</div>
          <el-menu-item index="/portfolio">
            <el-icon><Briefcase /></el-icon>
            <span>持仓管理</span>
          </el-menu-item>
          <el-menu-item index="/trades">
            <el-icon><List /></el-icon>
            <span>交易记录</span>
          </el-menu-item>
          <el-menu-item index="/orders">
            <el-icon><Document /></el-icon>
            <span>订单管理</span>
          </el-menu-item>
          <el-menu-item index="/risk">
            <el-icon><Warning /></el-icon>
            <span>风控检查</span>
          </el-menu-item>
          <el-menu-item index="/executions">
            <el-icon><List /></el-icon>
            <span>执行记录</span>
          </el-menu-item>

          <div class="menu-group-title">策略运营</div>
          <el-menu-item index="/strategy-center">
            <el-icon><Operation /></el-icon>
            <span>策略运营中心</span>
          </el-menu-item>
          <el-menu-item index="/quant-pipeline">
            <el-icon><Connection /></el-icon>
            <span>量化链路</span>
          </el-menu-item>
          <el-menu-item index="/strategy-config">
            <el-icon><Tools /></el-icon>
            <span>策略配置</span>
          </el-menu-item>
          <el-menu-item index="/ml">
            <el-icon><MagicStick /></el-icon>
            <span>ML 引擎</span>
          </el-menu-item>

          <div class="menu-group-title">系统运维</div>
          <el-menu-item index="/scheduler">
            <el-icon><Clock /></el-icon>
            <span>定时任务</span>
          </el-menu-item>
          <el-menu-item index="/data-update">
            <el-icon><Refresh /></el-icon>
            <span>数据更新</span>
          </el-menu-item>
          <el-menu-item index="/daily-report">
            <el-icon><Notebook /></el-icon>
            <span>日报</span>
          </el-menu-item>
        </el-menu>
      </el-aside>

      <!-- 主内容区 -->
      <el-container>
        <el-header class="header">
          <div class="header-left">
            <el-icon class="hamburger" @click="toggleSidebar" :size="24"><Expand /></el-icon>
            <h3>{{ pageTitle }}</h3>
          </div>
          <div class="header-right">
            <el-badge :value="3" class="notification">
              <el-icon :size="20"><Bell /></el-icon>
            </el-badge>
            <el-avatar :size="32" class="avatar">U</el-avatar>
          </div>
        </el-header>

        <el-main class="main-content">
          <router-view />
        </el-main>
      </el-container>
    </el-container>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, onMounted, onUnmounted } from 'vue'
import { useRoute } from 'vue-router'

const route = useRoute()

const activeMenu = computed(() => route.path)

const pageTitle = computed(() => {
  return (route.meta.title as string) || '量化交易系统'
})

const isCollapsed = ref(false)
const isMobile = ref(false)

const checkMobile = () => {
  isMobile.value = window.innerWidth < 768
  if (isMobile.value) {
    isCollapsed.value = true
  }
}

const toggleSidebar = () => {
  isCollapsed.value = !isCollapsed.value
}

onMounted(() => {
  checkMobile()
  window.addEventListener('resize', checkMobile)
})

onUnmounted(() => {
  window.removeEventListener('resize', checkMobile)
})
</script>

<style scoped>
.dashboard {
  width: 100%;
  height: 100vh;
  background: #f5f7fa;
}

.sidebar {
  background: #0f172a;
  height: 100vh;
  overflow-y: auto;
}

.logo {
  height: 64px;
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 0 20px;
  color: #fff;
  border-bottom: 1px solid rgba(255, 255, 255, 0.1);
}

.logo-mark {
  width: 32px;
  height: 32px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  background: #3b82f6;
  border-radius: 8px;
  color: #fff;
  font-size: 14px;
  font-weight: 700;
}

.logo-text {
  color: #fff;
  font-size: 18px;
  font-weight: 600;
  letter-spacing: 0;
}

.sidebar-menu {
  border: none;
  background: #0f172a;
  padding: 12px 0;
  --el-menu-bg-color: #0f172a;
  --el-menu-hover-bg-color: #1e293b;
  --el-menu-text-color: #cbd5e1;
  --el-menu-active-color: #fff;
}

.menu-group-title {
  padding: 14px 20px 4px;
  color: #94a3b8;
  font-size: 12px;
  line-height: 1.2;
  text-transform: uppercase;
}

:deep(.el-menu-item) {
  height: 40px;
  color: #cbd5e1;
}

:deep(.el-menu-item:hover) {
  color: #fff;
  background: #1e293b;
}

:deep(.el-menu-item.is-active) {
  color: #fff;
  background: #334155;
  border-left: 3px solid #3b82f6;
}

.header {
  background: #fff;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 24px;
  box-shadow: 0 1px 4px rgba(0, 21, 41, 0.08);
}

.header-left {
  display: flex;
  align-items: center;
  gap: 16px;
}

.header-left h3 {
  margin: 0;
  font-size: 18px;
  color: #262626;
}

.hamburger {
  cursor: pointer;
  transition: transform 0.3s;
}

.hamburger:hover {
  transform: scale(1.1);
}

.header-right {
  display: flex;
  align-items: center;
  gap: 20px;
}

.notification {
  cursor: pointer;
}

.avatar {
  cursor: pointer;
}

.main-content {
  padding: 24px;
  overflow-y: auto;
}

.sidebar.collapsed {
  width: 0 !important;
  overflow: hidden;
}

@media (max-width: 768px) {
  .sidebar {
    position: fixed;
    left: 0;
    top: 0;
    z-index: 1000;
    transition: transform 0.3s;
  }

  .sidebar.collapsed {
    transform: translateX(-100%);
  }

  .header-left h3 {
    font-size: 16px;
  }

  .main-content {
    padding: 16px;
  }
}
</style>
