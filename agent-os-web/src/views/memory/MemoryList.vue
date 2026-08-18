<template>
  <div class="memory-list">
    <el-card>
      <template #header>
        <div class="header">
          <span>记忆中心</span>
          <el-tag type="info">Mock 数据</el-tag>
        </div>
      </template>

      <el-alert
        type="info"
        :closable="false"
        show-icon
        title="记忆中心功能开发中"
        description="Agent OS 记忆模块 HTTP API 尚未提供，当前展示为模拟数据。"
        style="margin-bottom: 16px"
      />

      <!-- 搜索 -->
      <div class="filters">
        <el-input
          v-model="searchText"
          placeholder="搜索记忆内容"
          clearable
          style="width: 300px"
        >
          <template #prefix>
            <el-icon><Search /></el-icon>
          </template>
        </el-input>
        <el-select v-model="categoryFilter" placeholder="分类" clearable style="width: 150px">
          <el-option label="全部" value="" />
          <el-option label="经验" value="experience" />
          <el-option label="规则" value="rule" />
          <el-option label="教训" value="lesson" />
        </el-select>
      </div>

      <!-- 记忆卡片列表 -->
      <div class="memory-cards" style="margin-top: 16px">
        <el-card
          v-for="memory in filteredMemories"
          :key="memory.id"
          shadow="hover"
          class="memory-card"
        >
          <template #header>
            <div class="memory-header">
              <span>{{ memory.title }}</span>
              <el-tag size="small">{{ memory.category }}</el-tag>
            </div>
          </template>
          <p>{{ memory.content }}</p>
          <div class="memory-footer">
            <span class="confidence">置信度: {{ memory.confidence }}</span>
            <span class="time">{{ formatTime(memory.created_at) }}</span>
          </div>
        </el-card>
      </div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { Search } from '@element-plus/icons-vue'
import { formatTime } from '@/utils/format'

const memories = ref<any[]>([])
const searchText = ref('')
const categoryFilter = ref('')

const filteredMemories = computed(() => {
  let result = memories.value
  if (searchText.value) {
    result = result.filter((m) => m.title.includes(searchText.value) || m.content.includes(searchText.value))
  }
  if (categoryFilter.value) {
    result = result.filter((m) => m.category === categoryFilter.value)
  }
  return result
})

onMounted(() => {
  // Mock 数据
  memories.value = [
    { id: '1', title: 'ROE > 15% 选股有效', content: '过去3个月，ROE > 15% 的股票池平均跑赢大盘 8%', category: 'experience', confidence: 0.85, created_at: '2026-08-15T10:00:00Z' },
    { id: '2', title: '机构出货信号', content: '连续3天大宗交易折价 > 5% 是机构出货信号', category: 'rule', confidence: 0.72, created_at: '2026-08-14T15:00:00Z' },
    { id: '3', title: '追涨杀跌教训', content: '2026-07 追高 AI 概念股导致回撤 12%，应避免情绪交易', category: 'lesson', confidence: 0.90, created_at: '2026-08-10T09:00:00Z' },
  ]
})
</script>

<style scoped>
.memory-list {
  padding: 20px;
}
.header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.filters {
  display: flex;
  gap: 12px;
}
.memory-cards {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: 16px;
}
.memory-card {
  margin-bottom: 0;
}
.memory-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.memory-footer {
  display: flex;
  justify-content: space-between;
  margin-top: 12px;
  font-size: 12px;
  color: #909399;
}
</style>
