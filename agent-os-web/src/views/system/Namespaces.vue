<template>
  <div class="namespaces">
    <el-card>
      <template #header>
        <div class="header">
          <span>命名空间</span>
          <el-button type="primary" @click="showAddDialog = true">
            <el-icon><Plus /></el-icon>
            添加命名空间
          </el-button>
        </div>
      </template>

      <el-table :data="namespaces" v-loading="loading" stripe>
        <el-table-column prop="name" label="名称" width="200" />
        <el-table-column prop="description" label="描述" min-width="250" />
        <el-table-column prop="status" label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="row.status === 'active' ? 'success' : 'info'">
              {{ row.status === 'active' ? '活跃' : '停用' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="创建时间" width="180">
          <template #default="{ row }">
            {{ formatTime(row.created_at) }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="150" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" size="small" @click="editNamespace(row)">
              编辑
            </el-button>
            <el-popconfirm
              title="确定删除这个命名空间吗？"
              @confirm="deleteNamespace(row.name)"
            >
              <template #reference>
                <el-button link type="danger" size="small">删除</el-button>
              </template>
            </el-popconfirm>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 添加/编辑对话框 -->
    <el-dialog
      v-model="showAddDialog"
      :title="editingNamespace ? '编辑命名空间' : '添加命名空间'"
      width="500px"
    >
      <el-form :model="form" label-width="100px">
        <el-form-item label="名称">
          <el-input v-model="form.name" :disabled="!!editingNamespace" />
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="form.description" type="textarea" :rows="3" />
        </el-form-item>
        <el-form-item label="状态">
          <el-switch
            v-model="form.active"
            active-text="活跃"
            inactive-text="停用"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showAddDialog = false">取消</el-button>
        <el-button type="primary" @click="saveNamespace">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { Plus } from '@element-plus/icons-vue'
import { systemApi } from '@/api/system'
import { formatTime } from '@/utils/format'

const loading = ref(false)
const namespaces = ref<any[]>([])
const showAddDialog = ref(false)
const editingNamespace = ref<any>(null)
const form = ref({
  name: '',
  description: '',
  active: true,
})

const loadNamespaces = async () => {
  loading.value = true
  try {
    const result = await systemApi.getNamespaces()
    namespaces.value = result.namespaces || []
  } catch (e) {
    console.error('加载命名空间失败:', e)
    ElMessage.error('加载命名空间失败')
  } finally {
    loading.value = false
  }
}

const editNamespace = (namespace: any) => {
  editingNamespace.value = namespace
  form.value = {
    name: namespace.name,
    description: namespace.description,
    active: namespace.status === 'active',
  }
  showAddDialog.value = true
}

const saveNamespace = async () => {
  if (!form.value.name) {
    ElMessage.warning('请输入命名空间名称')
    return
  }

  if (editingNamespace.value) {
    ElMessage.info('后端暂不支持编辑命名空间，请删除后重新创建')
    showAddDialog.value = false
    editingNamespace.value = null
    return
  }

  try {
    await systemApi.createNamespace({
      name: form.value.name,
      description: form.value.description || undefined,
    })
    ElMessage.success('添加成功')
    showAddDialog.value = false
    editingNamespace.value = null
    form.value = { name: '', description: '', active: true }
    await loadNamespaces()
  } catch (e) {
    console.error('保存失败:', e)
    ElMessage.error('保存失败')
  }
}

const deleteNamespace = async (name: string) => {
  try {
    await systemApi.deleteNamespace(name)
    ElMessage.success('删除成功')
    await loadNamespaces()
  } catch (e) {
    console.error('删除失败:', e)
    ElMessage.error('删除失败')
  }
}

onMounted(() => {
  loadNamespaces()
})
</script>

<style scoped>
.namespaces {
  padding: 20px;
}

.header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
</style>
