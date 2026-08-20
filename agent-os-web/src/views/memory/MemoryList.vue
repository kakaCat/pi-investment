<template>
  <div class="memory-list">
    <el-card>
      <template #header>
        <div class="header">
          <span>记忆中心</span>
          <div class="header-actions">
            <el-tag v-if="loading" type="info" effect="plain">加载中...</el-tag>
            <el-tag v-else type="success" effect="plain">共 {{ total }} 条</el-tag>
          </div>
        </div>
      </template>

      <!-- 搜索和筛选 -->
      <div class="filters">
        <el-input
          v-model="searchText"
          placeholder="搜索记忆内容"
          clearable
          style="width: 300px"
          @keyup.enter="handleSearch"
          @clear="handleSearch"
        >
          <template #prefix>
            <el-icon><Search /></el-icon>
          </template>
        </el-input>
        <el-select v-model="categoryFilter" placeholder="分类" clearable style="width: 150px" @change="loadMemories">
          <el-option label="全部" value="" />
          <el-option label="知识" value="knowledge" />
          <el-option label="经验" value="experience" />
          <el-option label="决策" value="decision" />
          <el-option label="数据" value="data" />
        </el-select>
        <el-button type="primary" @click="handleSearch" style="margin-left: 10px">
          查询
        </el-button>
        <el-button @click="clearFilters">重置</el-button>
      </div>

      <!-- 记忆卡片列表 -->
      <div v-loading="loading" class="memory-cards" style="margin-top: 16px; min-height: 200px">
        <el-card
          v-for="memory in memories"
          :key="memory.id"
          shadow="hover"
          class="memory-card"
        >
          <template #header>
            <div class="memory-header">
              <span class="memory-title">{{ memory.title }}</span>
              <el-tag size="small" :type="getCategoryType(memory.category)">
                {{ getCategoryLabel(memory.category) }}
              </el-tag>
            </div>
          </template>
          <p class="memory-content">{{ memory.content }}</p>
          <div class="memory-footer">
            <div class="tags">
              <el-tag v-for="tag in memory.tags" :key="tag" size="small" type="info" effect="plain" style="margin-right: 4px">
                {{ tag }}
              </el-tag>
            </div>
            <span class="time">{{ formatTime(memory.created_at) }}</span>
          </div>
        </el-card>

        <el-empty v-if="!loading && memories.length === 0" description="暂无记忆" />
      </div>

      <!-- 分页 -->
      <div class="pagination">
        <el-pagination
          v-model:current-page="currentPage"
          v-model:page-size="pageSize"
          :total="total"
          :page-sizes="[6, 12, 24, 50]"
          layout="total, sizes, prev, pager, next"
          @size-change="loadMemories"
          @current-change="loadMemories"
        />
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
const memories = ref<any[]>([])
const total = ref(0)
const searchText = ref('')
const categoryFilter = ref('')
const currentPage = ref(1)
const pageSize = ref(12)

const getCategoryType = (category: string) => {
  const map: Record<string, string> = {
    knowledge: 'primary',
    experience: 'success',
    decision: 'warning',
    data: 'info',
  }
  return map[category] || 'info'
}

const getCategoryLabel = (category: string) => {
  const map: Record<string, string> = {
    knowledge: '知识',
    experience: '经验',
    decision: '决策',
    data: '数据',
  }
  return map[category] || category
}

const loadMemories = async () => {
  loading.value = true
  try {
    const params: any = { limit: pageSize.value }
    if (categoryFilter.value) params.category = categoryFilter.value

    const result = await memoryApi.list(params)
    memories.value = result.memories || []
    total.value = result.total || 0
  } catch (e) {
    console.error('加载记忆失败:', e)
    ElMessage.error('加载记忆失败')
  } finally {
    loading.value = false
  }
}

const handleSearch = async () => {
  currentPage.value = 1
  loading.value = true
  try {
    if (searchText.value) {
      // 有关键词走搜索接口
      const result = await memoryApi.search(searchText.value)
      memories.value = result.memories || []
      total.value = result.total || 0
    } else {
      await loadMemories()
    }
  } catch (e) {
    console.error('搜索记忆失败:', e)
    ElMessage.error('搜索记忆失败')
  } finally {
    loading.value = false
  }
}

const clearFilters = () => {
  searchText.value = ''
  categoryFilter.value = ''
  currentPage.value = 1
  loadMemories()
}

onMounted(() => {
  loadMemories()
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
  align-items: center;
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
.memory-title {
  font-weight: 600;
  flex: 1;
  margin-right: 8px;
}
.memory-content {
  min-height: 60px;
  line-height: 1.6;
  color: #606266;
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.memory-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: 12px;
  font-size: 12px;
  color: #909399;
}
.tags {
  flex: 1;
  overflow: hidden;
  white-space: nowrap;
}
.pagination {
  margin-top: 16px;
  display: flex;
  justify-content: flex-end;
}
</style>
