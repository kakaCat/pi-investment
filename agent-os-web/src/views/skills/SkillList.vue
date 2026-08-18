<template>
  <div class="skill-list">
    <el-card>
      <template #header>
        <div class="header">
          <span>技能列表</span>
          <el-button type="primary" @click="showCreateDialog = true">
            <el-icon><Plus /></el-icon>
            新建技能
          </el-button>
        </div>
      </template>

      <!-- 搜索和筛选 -->
      <div class="filters">
        <el-input
          v-model="searchText"
          placeholder="搜索技能名称"
          clearable
          style="width: 300px"
        >
          <template #prefix>
            <el-icon><Search /></el-icon>
          </template>
        </el-input>
        <el-select v-model="categoryFilter" placeholder="分类筛选" clearable style="width: 150px">
          <el-option label="全部分类" value="" />
          <el-option label="数据分析" value="data-analysis" />
          <el-option label="市场监控" value="market-monitor" />
          <el-option label="决策支持" value="decision-support" />
        </el-select>
      </div>

      <!-- 技能表格 -->
      <el-table :data="filteredSkills" stripe style="margin-top: 16px">
        <el-table-column prop="name" label="名称" width="200" />
        <el-table-column prop="category" label="分类" width="150" />
        <el-table-column prop="current_version" label="版本" width="100" />
        <el-table-column prop="status" label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="row.status === 'active' ? 'success' : 'info'">
              {{ row.status }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="owner" label="所有者" width="120" />
        <el-table-column prop="description" label="描述" show-overflow-tooltip />
        <el-table-column prop="created_at" label="创建时间" width="180">
          <template #default="{ row }">
            {{ formatTime(row.created_at) }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="200">
          <template #default="{ row }">
            <el-button size="small" type="primary" @click="viewSkill(row.id)">
              查看
            </el-button>
            <el-button size="small" type="danger" @click="deleteSkill(row.id)">
              删除
            </el-button>
          </template>
        </el-table-column>
      </el-table>

      <!-- 分页 -->
      <el-pagination
        v-model:current-page="currentPage"
        :page-size="pageSize"
        :total="skills.length"
        layout="total, prev, pager, next"
        style="margin-top: 16px; justify-content: center"
      />
    </el-card>

    <!-- 新建技能对话框 -->
    <el-dialog v-model="showCreateDialog" title="新建技能" width="600px">
      <el-form :model="newSkill" label-width="100px">
        <el-form-item label="名称" required>
          <el-input v-model="newSkill.name" placeholder="技能名称" />
        </el-form-item>
        <el-form-item label="分类" required>
          <el-select v-model="newSkill.category" placeholder="选择分类">
            <el-option label="数据分析" value="data-analysis" />
            <el-option label="市场监控" value="market-monitor" />
            <el-option label="决策支持" value="decision-support" />
          </el-select>
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="newSkill.description" type="textarea" :rows="3" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showCreateDialog = false">取消</el-button>
        <el-button type="primary" @click="createSkill">创建</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Search } from '@element-plus/icons-vue'
import { skillApi } from '@/api/skills'
import type { Skill } from '@/types'
import { formatTime } from '@/utils/format'

const skills = ref<Skill[]>([])
const searchText = ref('')
const categoryFilter = ref('')
const currentPage = ref(1)
const pageSize = ref(10)
const showCreateDialog = ref(false)

const newSkill = ref({
  name: '',
  category: '',
  description: '',
})

const filteredSkills = computed(() => {
  let result = skills.value

  if (searchText.value) {
    result = result.filter((s) => s.name.includes(searchText.value))
  }

  if (categoryFilter.value) {
    result = result.filter((s) => s.category === categoryFilter.value)
  }

  const start = (currentPage.value - 1) * pageSize.value
  return result.slice(start, start + pageSize.value)
})

const loadSkills = async () => {
  try {
    // Mock 数据
    skills.value = Array.from({ length: 20 }, (_, i) => ({
      id: `skill-${i}`,
      name: `skill_${i}`,
      description: `技能描述 ${i}`,
      category: ['data-analysis', 'market-monitor', 'decision-support'][i % 3],
      owner: 'agent-ts',
      status: i % 5 === 0 ? 'inactive' : 'active',
      current_version: '1.0.0',
      created_at: new Date(Date.now() - i * 86400000).toISOString(),
    }))
  } catch (e) {
    console.error('加载技能失败:', e)
  }
}

const createSkill = async () => {
  try {
    // await skillApi.create(newSkill.value)
    ElMessage.success('技能创建成功（Mock）')
    showCreateDialog.value = false
    await loadSkills()
  } catch (e) {
    ElMessage.error('创建失败')
  }
}

const viewSkill = (id: string) => {
  ElMessage.info(`查看技能 ${id}（功能开发中）`)
}

const deleteSkill = async (id: string) => {
  try {
    await ElMessageBox.confirm('确认删除该技能？', '警告', {
      type: 'warning',
    })
    // await skillApi.delete(id)
    ElMessage.success('技能已删除（Mock）')
    await loadSkills()
  } catch (e) {
    if (e !== 'cancel') {
      ElMessage.error('删除失败')
    }
  }
}

onMounted(() => {
  loadSkills()
})
</script>

<style scoped>
.skill-list {
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
</style>
