<template>
  <el-aside width="220px" class="sidebar">
    <div class="logo">🧠 Agent OS</div>
    <el-menu
      :default-active="$route.path"
      :default-openeds="defaultOpeneds"
      router
      background-color="#1a1a2e"
      text-color="#fff"
      active-text-color="#409eff"
    >
      <!-- 概览中心 -->
      <el-sub-menu index="overview">
        <template #title>
          <el-icon><DataLine /></el-icon>
          <span>概览中心</span>
        </template>
        <el-menu-item index="/overview">系统总览</el-menu-item>
        <el-menu-item index="/overview/monitor">实时监控</el-menu-item>
      </el-sub-menu>

      <!-- 调度中心 -->
      <el-sub-menu index="scheduler">
        <template #title>
          <el-icon><Timer /></el-icon>
          <span>调度中心</span>
        </template>
        <el-menu-item index="/scheduler/tasks">任务列表</el-menu-item>
        <el-menu-item index="/scheduler/executions">执行历史</el-menu-item>
        <el-menu-item index="/scheduler/statistics">任务统计</el-menu-item>
        <el-menu-item index="/scheduler/dependencies">依赖图谱</el-menu-item>
      </el-sub-menu>

      <!-- 技能中心 -->
      <el-sub-menu index="skills">
        <template #title>
          <el-icon><Cpu /></el-icon>
          <span>技能中心</span>
        </template>
        <el-menu-item index="/skills">技能列表</el-menu-item>
      </el-sub-menu>

      <!-- 决策中心 -->
      <el-sub-menu index="decisions">
        <template #title>
          <el-icon><Aim /></el-icon>
          <span>决策中心</span>
        </template>
        <el-menu-item index="/decisions">决策列表</el-menu-item>
        <el-menu-item index="/decisions/statistics">决策统计</el-menu-item>
      </el-sub-menu>

      <!-- 记忆中心 -->
      <el-sub-menu index="memory">
        <template #title>
          <el-icon><Collection /></el-icon>
          <span>记忆中心</span>
        </template>
        <el-menu-item index="/memory">记忆列表</el-menu-item>
        <el-menu-item index="/memory/search">记忆搜索</el-menu-item>
        <el-menu-item index="/memory/tags">标签管理</el-menu-item>
      </el-sub-menu>

      <!-- 事件中心 -->
      <el-sub-menu index="events">
        <template #title>
          <el-icon><Bell /></el-icon>
          <span>事件中心</span>
        </template>
        <el-menu-item index="/events">实时事件流</el-menu-item>
        <el-menu-item index="/events/history">事件历史</el-menu-item>
        <el-menu-item index="/events/alerts">告警规则</el-menu-item>
      </el-sub-menu>

      <!-- 通知中心 -->
      <el-sub-menu index="notifications">
        <template #title>
          <el-icon><Message /></el-icon>
          <span>通知中心</span>
        </template>
        <el-menu-item index="/notifications/channels">通知渠道</el-menu-item>
        <el-menu-item index="/notifications/logs">通知日志</el-menu-item>
        <el-menu-item index="/notifications/send">发送通知</el-menu-item>
      </el-sub-menu>

      <!-- 系统中心 -->
      <el-sub-menu index="system">
        <template #title>
          <el-icon><Setting /></el-icon>
          <span>系统中心</span>
        </template>
        <el-menu-item index="/system/status">系统状态</el-menu-item>
        <el-menu-item index="/system/quotas">资源配额</el-menu-item>
        <el-menu-item index="/system/namespaces">命名空间</el-menu-item>
        <el-menu-item index="/system/api-docs">API 文档</el-menu-item>
        <el-menu-item index="/system/logs">系统日志</el-menu-item>
      </el-sub-menu>

      <!-- 个人中心 -->
      <el-sub-menu index="profile">
        <template #title>
          <el-icon><User /></el-icon>
          <span>个人中心</span>
        </template>
        <el-menu-item index="/profile">个人设置</el-menu-item>
        <el-menu-item index="/profile/activity">操作记录</el-menu-item>
      </el-sub-menu>
    </el-menu>
  </el-aside>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import { DataLine, Timer, Cpu, Aim, Collection, Bell, Message, Setting, User } from '@element-plus/icons-vue'

const route = useRoute()

// 根据当前路由自动展开对应的一级菜单
const defaultOpeneds = computed(() => {
  const path = route.path
  if (path.startsWith('/overview')) return ['overview']
  if (path.startsWith('/scheduler')) return ['scheduler']
  if (path.startsWith('/skills')) return ['skills']
  if (path.startsWith('/decisions')) return ['decisions']
  if (path.startsWith('/memory')) return ['memory']
  if (path.startsWith('/events')) return ['events']
  if (path.startsWith('/notifications')) return ['notifications']
  if (path.startsWith('/system')) return ['system']
  if (path.startsWith('/profile')) return ['profile']
  return []
})
</script>

<style scoped>
.sidebar {
  background: #1a1a2e;
  height: 100vh;
  overflow-y: auto;
}

.logo {
  padding: 20px;
  color: #fff;
  font-size: 18px;
  font-weight: bold;
  text-align: center;
  border-bottom: 1px solid rgba(255, 255, 255, 0.1);
}

/* 滚动条样式 */
.sidebar::-webkit-scrollbar {
  width: 6px;
}

.sidebar::-webkit-scrollbar-thumb {
  background: rgba(255, 255, 255, 0.2);
  border-radius: 3px;
}

.sidebar::-webkit-scrollbar-thumb:hover {
  background: rgba(255, 255, 255, 0.3);
}
</style>
