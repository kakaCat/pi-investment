import { createRouter, createWebHistory } from 'vue-router'
import AppLayout from '@/components/layout/AppLayout.vue'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/',
      component: AppLayout,
      redirect: '/overview',
      children: [
        // 概览中心
        {
          path: 'overview',
          name: 'Overview',
          component: () => import('@/views/overview/Dashboard.vue'),
        },
        {
          path: 'overview/monitor',
          name: 'RealTimeMonitor',
          component: () => import('@/views/overview/Monitor.vue'),
        },
        
        // 调度中心
        {
          path: 'scheduler/tasks',
          name: 'TaskList',
          component: () => import('@/views/scheduler/TaskList.vue'),
        },
        {
          path: 'scheduler/executions',
          name: 'ExecutionHistory',
          component: () => import('@/views/scheduler/ExecutionHistory.vue'),
        },
        {
          path: 'scheduler/statistics',
          name: 'TaskStatistics',
          component: () => import('@/views/scheduler/TaskStatistics.vue'),
        },
        {
          path: 'scheduler/dependencies',
          name: 'DependencyGraph',
          component: () => import('@/views/scheduler/DependencyGraph.vue'),
        },
        
        // 技能中心
        {
          path: 'skills',
          name: 'SkillList',
          component: () => import('@/views/skills/SkillList.vue'),
        },
        {
          path: 'skills/:id/versions',
          name: 'VersionHistory',
          component: () => import('@/views/skills/VersionHistory.vue'),
        },
        {
          path: 'skills/:id/edit',
          name: 'SkillEditor',
          component: () => import('@/views/skills/SkillEditor.vue'),
        },
        
        // 决策中心
        {
          path: 'decisions',
          name: 'DecisionList',
          component: () => import('@/views/decisions/DecisionList.vue'),
        },
        {
          path: 'decisions/statistics',
          name: 'DecisionStatistics',
          component: () => import('@/views/decisions/DecisionStatistics.vue'),
        },
        {
          path: 'decisions/:id',
          name: 'DecisionDetail',
          component: () => import('@/views/decisions/DecisionDetail.vue'),
        },
        
        // 记忆中心
        {
          path: 'memory',
          name: 'MemoryList',
          component: () => import('@/views/memory/MemoryList.vue'),
        },
        {
          path: 'memory/search',
          name: 'MemorySearch',
          component: () => import('@/views/memory/MemorySearch.vue'),
        },
        {
          path: 'memory/tags',
          name: 'TagManagement',
          component: () => import('@/views/memory/TagManagement.vue'),
        },
        
        // 事件中心
        {
          path: 'events',
          name: 'EventStream',
          component: () => import('@/views/events/EventStream.vue'),
        },
        {
          path: 'events/history',
          name: 'EventHistory',
          component: () => import('@/views/events/EventHistory.vue'),
        },
        {
          path: 'events/alerts',
          name: 'AlertRules',
          component: () => import('@/views/events/AlertRules.vue'),
        },
        
        // 通知中心
        {
          path: 'notifications/channels',
          name: 'ChannelList',
          component: () => import('@/views/notifications/ChannelList.vue'),
        },
        {
          path: 'notifications/logs',
          name: 'NotificationLogs',
          component: () => import('@/views/notifications/NotificationLogs.vue'),
        },
        {
          path: 'notifications/send',
          name: 'SendNotification',
          component: () => import('@/views/notifications/SendNotification.vue'),
        },
        
        // 系统中心
        {
          path: 'system/status',
          name: 'SystemStatus',
          component: () => import('@/views/system/SystemStatus.vue'),
        },
        {
          path: 'system/quotas',
          name: 'ResourceQuotas',
          component: () => import('@/views/system/ResourceQuotas.vue'),
        },
        {
          path: 'system/namespaces',
          name: 'Namespaces',
          component: () => import('@/views/system/Namespaces.vue'),
        },
        {
          path: 'system/api-docs',
          name: 'ApiDocs',
          component: () => import('@/views/system/ApiDocs.vue'),
        },
        {
          path: 'system/logs',
          name: 'SystemLogs',
          component: () => import('@/views/system/SystemLogs.vue'),
        },
        
        // 个人中心
        {
          path: 'profile',
          name: 'ProfileSettings',
          component: () => import('@/views/profile/ProfileSettings.vue'),
        },
        {
          path: 'profile/activity',
          name: 'ActivityLog',
          component: () => import('@/views/profile/ActivityLog.vue'),
        },
      ],
    },
    {
      path: '/:pathMatch(.*)*',
      name: 'NotFound',
      component: () => import('@/views/NotFound.vue'),
    },
  ],
})

export default router
