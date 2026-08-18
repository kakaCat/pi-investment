<template>
  <el-card shadow="hover" class="chart-card">
    <template #header v-if="title || $slots.actions">
      <div class="chart-header">
        <span class="chart-title">{{ title }}</span>
        <div class="chart-actions">
          <slot name="actions"></slot>
        </div>
      </div>
    </template>
    <div class="chart-content" :style="{ height: height }">
      <slot></slot>
    </div>
  </el-card>
</template>

<script setup lang="ts">
interface Props {
  title?: string
  height?: string
}

withDefaults(defineProps<Props>(), {
  height: '300px',
})
</script>

<style scoped>
.chart-card {
  height: 100%;
}

.chart-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.chart-title {
  font-size: 16px;
  font-weight: 600;
  color: #303133;
}

.chart-actions {
  display: flex;
  gap: 8px;
}

.chart-content {
  position: relative;
}
</style>
