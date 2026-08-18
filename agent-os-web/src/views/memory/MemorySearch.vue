<template>
  <div class="memory-search">
    <el-card>
      <template #header>
        <span>记忆搜索</span>
      </template>

      <!-- 搜索框 -->
      <el-input
        v-model="searchQuery"
        placeholder="输入关键词搜索..."
        size="large"
        clearable
        @keyup.enter="search"
      >
        <template #append>
          <el-button :icon="Search" @click="search" :loading="loading">搜索</el-button>
        </template>
      </el-input>

      <!-- 高级筛选 -->
      <div class="filters" style="margin-top: 15px">
        <el-select v-model="filters.category" placeholder="分类" clearable style="width: 150px">
          <el-option label="知识" value="knowledge" />
          <el-option label="经验" value="experience" />
          <el-option label="决策" value="decision" />
          <el-option label="数据" value="data" />
        </el-select>
        <el-select v-model="filters.tag" placeholder="标签" clearable style="width: 150px; margin-left: 10px">
          <el-option v-for="tag in tags" :key="tag" :label="tag" :value="tag" />
        </el-select>
        <el-date-picker
          v-model="filters.dateRange"
          type="daterange"
          range-separator="至"
          start-placeholder="开始日期"
          end-placeholder="结束日期"
          style="margin-left: 10px"
        />
      </div>

      <!-- 搜索结果 -->
      <div v-if="searched" style="margin-top: 20px">
        <el-alert
          v-if="results.length === 0"
          title="没有找到相关记忆"
          type="info"
          :closable="false"
        />
        <div v-else>
          <el-text type="info">找到 {{ results.length }} 条记忆</el-text>
          <el-divider />
          <div class="results">
            <el-card
              v-for="item in results"
              :key="item.id"
              shadow="hover"
              class="result-card"
            >
              <template #header>
                <div class="result-header">
                  <span>{{ item.title }}</span>
                  <el-tag size="small">{{ item.category }}</el-tag>
                </div>
              </template>
              <p class="result-content">{{ item.content }}</p>
              <div class="result-footer">
                <div class="tags">
                  <el-tag
                    v-for="tag in item.tags"
                    :key="tag"
                    size="small"
                    type="info"
                    style="margin-right: 5px"
                  >
                    {{ tag }}
                  </el-tag>
                </div>
                <el-text type="info" size="small">{{ formatTime(item.created_at) }}</el-text>
              </div>
            </el-card>
          </div>
        </div>
      </div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { Search } from '@element-plus/icons-vue'
import { memoryApi } from '@/api/memory'
import { formatTime } from '@/utils/format'

const loading = ref(false)
const searched = ref(false)
const searchQuery = ref('')
const filters = ref({
  category: '',
  tag: '',
  dateRange: null as [Date, Date] | null,
})
const tags = ref<string[]>([])
const results = ref<any[]>([])

const loadTags = async () => {
  try {
    const result = await memoryApi.getTags()
    tags.value = result.tags || []
  } catch (e) {
    console.error('加载标签失败:', e)
  }
}

const search = async () => {
  if (!searchQuery.value.trim()) {
    ElMessage.warning('请输入搜索关键词')
    return
  }

  loading.value = true
  searched.value = true
  try {
    const result = await memoryApi.search(searchQuery.value)
    results.value = result.memories || []
  } catch (e) {
    console.error('搜索失败:', e)
    ElMessage.error('搜索失败')
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  loadTags()
})
</script>

<style scoped>
.memory-search {
  padding: 20px;
}

.filters {
  display: flex;
  align-items: center;
}

.results {
  display: flex;
  flex-direction: column;
  gap: 15px;
}

.result-card {
  transition: all 0.3s;
}

.result-card:hover {
  transform: translateY(-2px);
}

.result-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.result-content {
  margin: 10px 0;
  color: #666;
  line-height: 1.6;
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.result-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: 10px;
}

.tags {
  display: flex;
  flex-wrap: wrap;
  gap: 5px;
}
</style>
