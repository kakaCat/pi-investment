<template>
  <div class="api-docs">
    <el-card>
      <template #header>
        <div class="header">
          <span>API 文档</span>
          <el-input
            v-model="searchQuery"
            placeholder="搜索 API..."
            style="width: 300px"
            clearable
          >
            <template #prefix>
              <el-icon><Search /></el-icon>
            </template>
          </el-input>
        </div>
      </template>

      <el-collapse v-model="activeGroups">
        <el-collapse-item
          v-for="group in filteredApiGroups"
          :key="group.name"
          :name="group.name"
        >
          <template #title>
            <div class="group-title">
              <span>{{ group.name }}</span>
              <el-tag size="small" style="margin-left: 10px">{{ group.apis.length }} 个接口</el-tag>
            </div>
          </template>
          
          <div class="api-list">
            <el-card
              v-for="api in group.apis"
              :key="api.path"
              shadow="hover"
              class="api-card"
            >
              <div class="api-header">
                <el-tag :type="getMethodType(api.method)">{{ api.method }}</el-tag>
                <code class="api-path">{{ api.path }}</code>
              </div>
              <p class="api-description">{{ api.description }}</p>
              
              <el-divider />
              
              <!-- 请求参数 -->
              <div v-if="api.params && api.params.length > 0" class="api-section">
                <h4>请求参数</h4>
                <el-table :data="api.params" size="small" border>
                  <el-table-column prop="name" label="参数名" width="150" />
                  <el-table-column prop="type" label="类型" width="100" />
                  <el-table-column prop="required" label="必填" width="80">
                    <template #default="{ row }">
                      <el-tag :type="row.required ? 'danger' : 'info'" size="small">
                        {{ row.required ? '是' : '否' }}
                      </el-tag>
                    </template>
                  </el-table-column>
                  <el-table-column prop="description" label="说明" />
                </el-table>
              </div>

              <!-- 响应示例 -->
              <div v-if="api.response" class="api-section">
                <h4>响应示例</h4>
                <pre class="code-block">{{ api.response }}</pre>
              </div>

              <!-- 测试按钮 -->
              <div class="api-actions">
                <el-button size="small" @click="testApi(api)">测试接口</el-button>
              </div>
            </el-card>
          </div>
        </el-collapse-item>
      </el-collapse>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Search } from '@element-plus/icons-vue'

const searchQuery = ref('')
const activeGroups = ref<string[]>([])

const apiGroups = [
  {
    name: '调度器 API',
    apis: [
      {
        method: 'GET',
        path: '/api/v1/scheduler/tasks',
        description: '获取任务列表',
        params: [
          { name: 'enabled', type: 'boolean', required: false, description: '是否启用' },
          { name: 'limit', type: 'number', required: false, description: '返回数量限制' },
        ],
        response: '{\n  "success": true,\n  "data": {\n    "tasks": [...]\n  }\n}',
      },
      {
        method: 'POST',
        path: '/api/v1/scheduler/tasks',
        description: '创建新任务',
        params: [
          { name: 'name', type: 'string', required: true, description: '任务名称' },
          { name: 'cron', type: 'string', required: true, description: 'Cron 表达式' },
          { name: 'skill_id', type: 'string', required: true, description: '技能 ID' },
        ],
        response: '{\n  "success": true,\n  "data": {\n    "task": {...}\n  }\n}',
      },
    ],
  },
  {
    name: '技能 API',
    apis: [
      {
        method: 'GET',
        path: '/api/v1/skills',
        description: '获取技能列表',
        params: [],
        response: '{\n  "success": true,\n  "data": {\n    "skills": [...]\n  }\n}',
      },
    ],
  },
  {
    name: '通知 API',
    apis: [
      {
        method: 'GET',
        path: '/api/v1/notifications/channels',
        description: '获取通知渠道列表',
        params: [],
        response: '{\n  "success": true,\n  "data": {\n    "channels": [...]\n  }\n}',
      },
      {
        method: 'POST',
        path: '/api/v1/notifications/send',
        description: '发送通知',
        params: [
          { name: 'channel', type: 'string', required: true, description: '渠道 ID' },
          { name: 'title', type: 'string', required: true, description: '通知标题' },
          { name: 'content', type: 'string', required: true, description: '通知内容' },
        ],
        response: '{\n  "success": true,\n  "message": "发送成功"\n}',
      },
    ],
  },
]

const filteredApiGroups = computed(() => {
  if (!searchQuery.value) return apiGroups
  
  return apiGroups
    .map(group => ({
      ...group,
      apis: group.apis.filter(api =>
        api.path.toLowerCase().includes(searchQuery.value.toLowerCase()) ||
        api.description.toLowerCase().includes(searchQuery.value.toLowerCase())
      ),
    }))
    .filter(group => group.apis.length > 0)
})

const getMethodType = (method: string) => {
  const types: Record<string, any> = {
    GET: 'success',
    POST: 'primary',
    PUT: 'warning',
    DELETE: 'danger',
  }
  return types[method] || 'info'
}

const testApi = async (api: any) => {
  if (api.method !== 'GET') {
    ElMessage.info(`「${api.method} ${api.path}」暂仅支持 GET 接口在线测试`)
    return
  }
  try {
    const response = await fetch(api.path)
    const data = await response.json()
    ElMessageBox.alert(
      `<pre style="text-align:left;max-height:300px;overflow:auto">${JSON.stringify(data, null, 2)}</pre>`,
      `测试结果: ${api.method} ${api.path}`,
      { dangerouslyUseHTMLString: true, customClass: 'api-test-result' }
    )
  } catch (e) {
    console.error('测试接口失败:', e)
    ElMessage.error(`测试失败: ${e instanceof Error ? e.message : String(e)}`)
  }
}
</script>

<style scoped>
.api-docs {
  padding: 20px;
}

.header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.group-title {
  display: flex;
  align-items: center;
}

.api-list {
  display: flex;
  flex-direction: column;
  gap: 15px;
}

.api-card {
  margin-bottom: 0;
}

.api-header {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 10px;
}

.api-path {
  font-family: 'Courier New', monospace;
  font-size: 14px;
  font-weight: 600;
}

.api-description {
  color: #666;
  margin: 10px 0;
}

.api-section {
  margin: 15px 0;
}

.api-section h4 {
  margin: 0 0 10px 0;
  font-size: 14px;
  font-weight: 600;
}

.code-block {
  padding: 12px;
  background: #f5f7fa;
  border-radius: 4px;
  font-size: 12px;
  overflow-x: auto;
}

.api-actions {
  margin-top: 15px;
}
</style>
