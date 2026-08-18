<template>
  <div class="tag-management">
    <el-card>
      <template #header>
        <div class="header">
          <span>标签管理</span>
          <el-button type="primary" @click="showAddDialog = true">
            <el-icon><Plus /></el-icon>
            添加标签
          </el-button>
        </div>
      </template>

      <el-table :data="tags" v-loading="loading" stripe>
        <el-table-column prop="name" label="标签名称" />
        <el-table-column prop="count" label="使用次数" width="120" sortable />
        <el-table-column prop="created_at" label="创建时间" width="180">
          <template #default="{ row }">
            {{ formatTime(row.created_at) }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="100">
          <template #default="{ row }">
            <el-popconfirm
              title="确定删除这个标签吗？"
              @confirm="deleteTag(row.name)"
            >
              <template #reference>
                <el-button link type="danger" size="small">删除</el-button>
              </template>
            </el-popconfirm>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 添加对话框 -->
    <el-dialog v-model="showAddDialog" title="添加标签" width="400px">
      <el-form :model="form" label-width="80px">
        <el-form-item label="标签名称">
          <el-input v-model="form.name" placeholder="输入标签名称" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showAddDialog = false">取消</el-button>
        <el-button type="primary" @click="addTag">添加</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { Plus } from '@element-plus/icons-vue'
import { memoryApi } from '@/api/memory'
import { formatTime } from '@/utils/format'

const loading = ref(false)
const tags = ref<any[]>([])
const showAddDialog = ref(false)
const form = ref({
  name: '',
})

const loadTags = async () => {
  loading.value = true
  try {
    const result = await memoryApi.getTags()
    tags.value = result.tags || []
  } catch (e) {
    console.error('加载标签失败:', e)
    ElMessage.error('加载标签失败')
  } finally {
    loading.value = false
  }
}

const addTag = async () => {
  if (!form.value.name.trim()) {
    ElMessage.warning('请输入标签名称')
    return
  }

  try {
    await memoryApi.createTag(form.value.name)
    ElMessage.success('添加成功')
    showAddDialog.value = false
    form.value.name = ''
    await loadTags()
  } catch (e) {
    console.error('添加失败:', e)
    ElMessage.error('添加失败')
  }
}

const deleteTag = async (name: string) => {
  try {
    await memoryApi.deleteTag(name)
    ElMessage.success('删除成功')
    await loadTags()
  } catch (e) {
    console.error('删除失败:', e)
    ElMessage.error('删除失败')
  }
}

onMounted(() => {
  loadTags()
})
</script>

<style scoped>
.tag-management {
  padding: 20px;
}

.header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
</style>
