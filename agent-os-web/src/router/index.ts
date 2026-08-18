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
        {
          path: 'overview',
          name: 'Overview',
          component: () => import('@/views/overview/Dashboard.vue'),
        },
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
          path: 'skills',
          name: 'SkillList',
          component: () => import('@/views/skills/SkillList.vue'),
        },
        {
          path: 'events',
          name: 'EventStream',
          component: () => import('@/views/events/EventStream.vue'),
        },
        {
          path: 'system/status',
          name: 'SystemStatus',
          component: () => import('@/views/system/SystemStatus.vue'),
        },
      ],
    },
  ],
})

export default router
