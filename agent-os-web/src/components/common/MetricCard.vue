<template>
  <el-card shadow="hover" class="metric-card">
    <div class="metric-content">
      <div class="metric-icon" :style="{ background: iconBg }">
        <el-icon :size="24" :color="iconColor">
          <component :is="icon" />
        </el-icon>
      </div>
      <div class="metric-data">
        <div class="metric-value">
          {{ value }}
          <span v-if="suffix" class="metric-suffix">{{ suffix }}</span>
        </div>
        <div class="metric-label">{{ label }}</div>
        <div v-if="trend !== undefined" class="metric-trend" :class="trendClass">
          <el-icon :size="12">
            <component :is="trendIcon" />
          </el-icon>
          <span>{{ Math.abs(trend) }}%</span>
        </div>
      </div>
    </div>
  </el-card>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { ArrowUp, ArrowDown } from '@element-plus/icons-vue'

interface Props {
  label: string
  value: number | string
  suffix?: string
  icon?: any
  iconColor?: string
  iconBg?: string
  trend?: number
}

const props = withDefaults(defineProps<Props>(), {
  iconColor: '#409eff',
  iconBg: 'rgba(64, 158, 255, 0.1)',
})

const trendIcon = computed(() => {
  return props.trend && props.trend > 0 ? ArrowUp : ArrowDown
})

const trendClass = computed(() => {
  if (!props.trend) return ''
  return props.trend > 0 ? 'trend-up' : 'trend-down'
})
</script>

<style scoped>
.metric-card {
  cursor: default;
  transition: all 0.3s;
}

.metric-card:hover {
  transform: translateY(-4px);
}

.metric-content {
  display: flex;
  align-items: center;
  gap: 16px;
}

.metric-icon {
  width: 56px;
  height: 56px;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.metric-data {
  flex: 1;
}

.metric-value {
  font-size: 28px;
  font-weight: 600;
  color: #303133;
  line-height: 1.2;
  margin-bottom: 4px;
}

.metric-suffix {
  font-size: 16px;
  font-weight: 400;
  color: #909399;
  margin-left: 4px;
}

.metric-label {
  font-size: 14px;
  color: #606266;
  margin-bottom: 4px;
}

.metric-trend {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: 12px;
  font-weight: 500;
}

.trend-up {
  color: #67c23a;
}

.trend-down {
  color: #f56c6c;
}
</style>
