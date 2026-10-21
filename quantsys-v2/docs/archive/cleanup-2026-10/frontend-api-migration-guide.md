# 前端页面迁移到新API指南

**日期**: 2026-06-27  
**目标**: 将现有调度任务管理页面迁移到新的配置API

---

## 一、迁移概述

### 1.1 为什么要迁移？

**新API的优势**:
- ✅ **热重载**: 配置修改立即生效，无需重启
- ✅ **更强大**: 支持批量操作、导入导出
- ✅ **更灵活**: 支持更多配置选项（executor、max_instances等）
- ✅ **更现代**: RESTful设计，标准JSON响应
- ✅ **更完整**: 完整的审计日志（创建人、更新人）

### 1.2 迁移策略

**推荐: 渐进式迁移**
1. 保持旧页面不变（作为备份）
2. 创建新页面使用新API
3. 逐步切换用户到新页面
4. 验证稳定后废弃旧页面

---

## 二、API对比

### 2.1 列出任务

**旧API**:
```javascript
// GET /api/scheduler/tasks?page=1&pageSize=20
{
  "success": true,
  "data": [
    {
      "task_id": 1,
      "name": "daily_data_update",
      "schedule_kind": "cron",
      "schedule_expr": "30 16 * * 1-5",
      "command": "data_update",
      "is_enabled": true
    }
  ],
  "pagination": {
    "total": 22,
    "page": 1,
    "pageSize": 20
  }
}
```

**新API**:
```javascript
// GET /api/scheduler/config/tasks?enabled_only=false
{
  "success": true,
  "total": 22,
  "data": [
    {
      "config_id": 1,
      "task_name": "daily_data_update",
      "cron_expression": "30 16 * * 1-5",
      "command": "data_update",
      "description": "每日数据更新",
      "params": {},
      "is_enabled": true,
      "executor": "default",
      "max_instances": 1,
      "created_at": "2026-06-27T10:00:00",
      "updated_at": "2026-06-27T10:00:00"
    }
  ]
}
```

**差异**:
- ✅ 字段名更清晰（`task_name` vs `name`）
- ✅ 直接使用 `cron_expression`，无需 `schedule_kind`
- ✅ 新增 `description`、`executor`、审计字段

### 2.2 创建任务

**旧API**:
```javascript
// POST /api/scheduler/tasks
{
  "name": "my_task",
  "scheduleKind": "cron",
  "scheduleExpr": "0 9 * * *",
  "command": "data_update",
  "payload": {"key": "value"}
}
```

**新API**:
```javascript
// POST /api/scheduler/config/tasks
{
  "task_name": "my_task",
  "cron_expression": "0 9 * * *",
  "command": "data_update",
  "description": "我的任务",
  "params": {"key": "value"},
  "is_enabled": true,
  "executor": "default",
  "max_instances": 1
}
```

**差异**:
- ✅ 字段名更统一（camelCase → snake_case）
- ✅ `payload` → `params`
- ✅ 新增更多配置选项

### 2.3 更新任务

**旧API**:
```javascript
// PUT /api/scheduler/tasks/1
{
  "scheduleExpr": "0 10 * * *"
}
```

**新API**:
```javascript
// PUT /api/scheduler/config/tasks/my_task
{
  "cron_expression": "0 10 * * *"
}
```

**差异**:
- ✅ 使用 `task_name` 而不是 `task_id`
- ✅ 自动触发热重载

### 2.4 删除任务

**旧API**:
```javascript
// DELETE /api/scheduler/tasks/1
```

**新API**:
```javascript
// DELETE /api/scheduler/config/tasks/my_task
```

**差异**:
- ✅ 使用 `task_name` 而不是 `task_id`
- ✅ 自动从调度器移除

### 2.5 启用/禁用任务

**旧API**:
```javascript
// POST /api/scheduler/tasks/1/enable
// POST /api/scheduler/tasks/1/disable
```

**新API**:
```javascript
// POST /api/scheduler/config/tasks/my_task/enable
// POST /api/scheduler/config/tasks/my_task/disable
```

**差异**:
- ✅ 使用 `task_name`
- ✅ 立即生效（自动注册/移除）

---

## 三、前端代码迁移

### 3.1 API服务层

**创建新的API服务** (`src/api/schedulerConfigApi.js`):

```javascript
import axios from 'axios';

const BASE_URL = '/api/scheduler/config';

export const schedulerConfigApi = {
  // 列出所有任务
  listTasks(enabledOnly = false, command = null) {
    const params = {};
    if (enabledOnly) params.enabled_only = true;
    if (command) params.command = command;
    
    return axios.get(`${BASE_URL}/tasks`, { params });
  },

  // 获取单个任务
  getTask(taskName) {
    return axios.get(`${BASE_URL}/tasks/${taskName}`);
  },

  // 创建任务
  createTask(task) {
    return axios.post(`${BASE_URL}/tasks`, task);
  },

  // 更新任务
  updateTask(taskName, updates) {
    return axios.put(`${BASE_URL}/tasks/${taskName}`, updates);
  },

  // 删除任务
  deleteTask(taskName) {
    return axios.delete(`${BASE_URL}/tasks/${taskName}`);
  },

  // 启用任务
  enableTask(taskName) {
    return axios.post(`${BASE_URL}/tasks/${taskName}/enable`);
  },

  // 禁用任务
  disableTask(taskName) {
    return axios.post(`${BASE_URL}/tasks/${taskName}/disable`);
  },

  // 热重载调度器
  reloadScheduler() {
    return axios.post(`${BASE_URL}/reload`);
  },

  // 从旧表导入
  importLegacyTasks() {
    return axios.post(`${BASE_URL}/import/legacy`);
  },

  // 导出配置
  exportConfig() {
    return axios.get(`${BASE_URL}/export`);
  },

  // 导入配置
  importConfig(data, overwrite = false) {
    return axios.post(`${BASE_URL}/import`, {
      ...data,
      overwrite
    });
  }
};
```

### 3.2 Vue 3 组件示例

**任务列表组件** (`src/views/SchedulerConfig.vue`):

```vue
<template>
  <div class="scheduler-config">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>定时任务配置</span>
          <div class="actions">
            <el-button 
              type="primary" 
              @click="showCreateDialog"
            >
              新建任务
            </el-button>
            <el-button 
              @click="handleReload"
              :loading="reloading"
            >
              热重载
            </el-button>
            <el-button 
              @click="handleImportLegacy"
            >
              导入旧任务
            </el-button>
            <el-button 
              @click="handleExport"
            >
              导出配置
            </el-button>
          </div>
        </div>
      </template>

      <!-- 过滤器 -->
      <el-form inline class="filter-form">
        <el-form-item label="状态">
          <el-select 
            v-model="filters.enabledOnly" 
            @change="loadTasks"
          >
            <el-option label="全部" :value="false" />
            <el-option label="仅启用" :value="true" />
          </el-select>
        </el-form-item>
        <el-form-item label="命令">
          <el-select 
            v-model="filters.command" 
            clearable
            @change="loadTasks"
          >
            <el-option 
              v-for="cmd in availableCommands" 
              :key="cmd" 
              :label="cmd" 
              :value="cmd" 
            />
          </el-select>
        </el-form-item>
      </el-form>

      <!-- 任务列表 -->
      <el-table 
        :data="tasks" 
        v-loading="loading"
        style="width: 100%"
      >
        <el-table-column 
          prop="task_name" 
          label="任务名称" 
          width="200"
        />
        <el-table-column 
          prop="description" 
          label="描述" 
          width="200"
        />
        <el-table-column 
          prop="cron_expression" 
          label="Cron表达式" 
          width="150"
        />
        <el-table-column 
          prop="command" 
          label="命令" 
          width="150"
        />
        <el-table-column 
          prop="is_enabled" 
          label="状态" 
          width="100"
        >
          <template #default="{ row }">
            <el-tag :type="row.is_enabled ? 'success' : 'info'">
              {{ row.is_enabled ? '启用' : '禁用' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column 
          prop="executor" 
          label="执行器" 
          width="100"
        />
        <el-table-column 
          label="操作" 
          width="250"
          fixed="right"
        >
          <template #default="{ row }">
            <el-button 
              size="small" 
              @click="handleEdit(row)"
            >
              编辑
            </el-button>
            <el-button 
              size="small" 
              :type="row.is_enabled ? 'warning' : 'success'"
              @click="handleToggleEnable(row)"
            >
              {{ row.is_enabled ? '禁用' : '启用' }}
            </el-button>
            <el-button 
              size="small" 
              type="danger"
              @click="handleDelete(row)"
            >
              删除
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 创建/编辑对话框 -->
    <el-dialog 
      v-model="dialogVisible" 
      :title="dialogMode === 'create' ? '新建任务' : '编辑任务'"
      width="600px"
    >
      <el-form 
        :model="form" 
        :rules="rules" 
        ref="formRef"
        label-width="120px"
      >
        <el-form-item label="任务名称" prop="task_name">
          <el-input 
            v-model="form.task_name" 
            :disabled="dialogMode === 'edit'"
            placeholder="例如: daily_data_update"
          />
        </el-form-item>
        
        <el-form-item label="描述" prop="description">
          <el-input 
            v-model="form.description" 
            placeholder="任务描述"
          />
        </el-form-item>
        
        <el-form-item label="Cron表达式" prop="cron_expression">
          <el-input 
            v-model="form.cron_expression" 
            placeholder="例如: 0 9 * * *"
          />
          <span class="form-tip">
            格式: 分 时 日 月 星期 (例如: 0 9 * * * 表示每天9:00)
          </span>
        </el-form-item>
        
        <el-form-item label="命令" prop="command">
          <el-select v-model="form.command" style="width: 100%">
            <el-option 
              v-for="cmd in availableCommands" 
              :key="cmd" 
              :label="cmd" 
              :value="cmd" 
            />
          </el-select>
        </el-form-item>
        
        <el-form-item label="参数">
          <el-input 
            v-model="paramsJson" 
            type="textarea" 
            :rows="4"
            placeholder='{"key": "value"}'
          />
          <span class="form-tip">JSON格式的参数</span>
        </el-form-item>
        
        <el-form-item label="执行器">
          <el-select v-model="form.executor">
            <el-option label="默认（线程池）" value="default" />
            <el-option label="进程池" value="processpool" />
          </el-select>
        </el-form-item>
        
        <el-form-item label="最大实例数">
          <el-input-number 
            v-model="form.max_instances" 
            :min="1" 
            :max="10"
          />
        </el-form-item>
        
        <el-form-item label="启用">
          <el-switch v-model="form.is_enabled" />
        </el-form-item>
      </el-form>
      
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button 
          type="primary" 
          @click="handleSubmit"
          :loading="submitting"
        >
          确定
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue';
import { ElMessage, ElMessageBox } from 'element-plus';
import { schedulerConfigApi } from '@/api/schedulerConfigApi';

// 数据
const loading = ref(false);
const reloading = ref(false);
const submitting = ref(false);
const tasks = ref([]);
const dialogVisible = ref(false);
const dialogMode = ref('create'); // 'create' | 'edit'
const formRef = ref(null);

// 过滤器
const filters = reactive({
  enabledOnly: false,
  command: null
});

// 可用命令列表
const availableCommands = ref([
  'data_quality_check',
  'data_update',
  'data_pipeline_daily',
  'data_pipeline_weekly',
  'signal_generate',
  'signal_execution_daily',
  'factor_compute',
  'financial_data_update',
  'market_scan_preopen',
  'signal_monitor_realtime',
  'strategy_validate_daily',
  'strategy_discover_weekly',
  'risk_check',
  'report_daily',
  'backtest_run',
  'v13_daily_check'
]);

// 表单
const form = reactive({
  task_name: '',
  description: '',
  cron_expression: '',
  command: '',
  params: {},
  is_enabled: true,
  executor: 'default',
  max_instances: 1
});

const paramsJson = ref('{}');

// 表单验证规则
const rules = {
  task_name: [
    { required: true, message: '请输入任务名称', trigger: 'blur' }
  ],
  cron_expression: [
    { required: true, message: '请输入Cron表达式', trigger: 'blur' }
  ],
  command: [
    { required: true, message: '请选择命令', trigger: 'change' }
  ]
};

// 方法
const loadTasks = async () => {
  loading.value = true;
  try {
    const response = await schedulerConfigApi.listTasks(
      filters.enabledOnly,
      filters.command
    );
    tasks.value = response.data.data;
  } catch (error) {
    ElMessage.error('加载任务失败: ' + error.message);
  } finally {
    loading.value = false;
  }
};

const showCreateDialog = () => {
  dialogMode.value = 'create';
  resetForm();
  dialogVisible.value = true;
};

const handleEdit = (row) => {
  dialogMode.value = 'edit';
  Object.assign(form, row);
  paramsJson.value = JSON.stringify(row.params || {}, null, 2);
  dialogVisible.value = true;
};

const resetForm = () => {
  Object.assign(form, {
    task_name: '',
    description: '',
    cron_expression: '',
    command: '',
    params: {},
    is_enabled: true,
    executor: 'default',
    max_instances: 1
  });
  paramsJson.value = '{}';
};

const handleSubmit = async () => {
  try {
    await formRef.value.validate();
    
    // 解析params JSON
    try {
      form.params = JSON.parse(paramsJson.value);
    } catch (e) {
      ElMessage.error('参数JSON格式错误');
      return;
    }
    
    submitting.value = true;
    
    if (dialogMode.value === 'create') {
      await schedulerConfigApi.createTask(form);
      ElMessage.success('任务创建成功');
    } else {
      await schedulerConfigApi.updateTask(form.task_name, form);
      ElMessage.success('任务更新成功');
    }
    
    dialogVisible.value = false;
    await loadTasks();
  } catch (error) {
    ElMessage.error('操作失败: ' + error.message);
  } finally {
    submitting.value = false;
  }
};

const handleToggleEnable = async (row) => {
  try {
    if (row.is_enabled) {
      await schedulerConfigApi.disableTask(row.task_name);
      ElMessage.success('任务已禁用');
    } else {
      await schedulerConfigApi.enableTask(row.task_name);
      ElMessage.success('任务已启用');
    }
    await loadTasks();
  } catch (error) {
    ElMessage.error('操作失败: ' + error.message);
  }
};

const handleDelete = async (row) => {
  try {
    await ElMessageBox.confirm(
      `确定要删除任务 "${row.task_name}" 吗？`,
      '警告',
      {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        type: 'warning'
      }
    );
    
    await schedulerConfigApi.deleteTask(row.task_name);
    ElMessage.success('任务已删除');
    await loadTasks();
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('删除失败: ' + error.message);
    }
  }
};

const handleReload = async () => {
  try {
    await ElMessageBox.confirm(
      '确定要重新加载所有任务配置吗？',
      '提示',
      {
        confirmButtonText: '确定',
        cancelButtonText: '取消'
      }
    );
    
    reloading.value = true;
    await schedulerConfigApi.reloadScheduler();
    ElMessage.success('调度器已重新加载');
    await loadTasks();
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('重新加载失败: ' + error.message);
    }
  } finally {
    reloading.value = false;
  }
};

const handleImportLegacy = async () => {
  try {
    await ElMessageBox.confirm(
      '确定要从旧的scheduler_tasks表导入任务吗？',
      '提示',
      {
        confirmButtonText: '确定',
        cancelButtonText: '取消'
      }
    );
    
    const response = await schedulerConfigApi.importLegacyTasks();
    ElMessage.success(`已导入 ${response.data.imported} 个任务`);
    await loadTasks();
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('导入失败: ' + error.message);
    }
  }
};

const handleExport = async () => {
  try {
    const response = await schedulerConfigApi.exportConfig();
    const dataStr = JSON.stringify(response.data, null, 2);
    const blob = new Blob([dataStr], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `scheduler-config-${Date.now()}.json`;
    a.click();
    URL.revokeObjectURL(url);
    ElMessage.success('配置已导出');
  } catch (error) {
    ElMessage.error('导出失败: ' + error.message);
  }
};

// 生命周期
onMounted(() => {
  loadTasks();
});
</script>

<style scoped>
.scheduler-config {
  padding: 20px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.actions {
  display: flex;
  gap: 10px;
}

.filter-form {
  margin-bottom: 20px;
}

.form-tip {
  font-size: 12px;
  color: #999;
  margin-top: 5px;
  display: block;
}
</style>
```

---

## 四、迁移步骤

### Step 1: 创建新的API服务层

1. 创建 `src/api/schedulerConfigApi.js`（见上文）
2. 测试API调用是否正常

### Step 2: 创建新的Vue组件

1. 创建 `src/views/SchedulerConfig.vue`（见上文）
2. 添加路由配置

### Step 3: 添加路由

```javascript
// router/index.js
{
  path: '/scheduler/config',
  name: 'SchedulerConfig',
  component: () => import('@/views/SchedulerConfig.vue'),
  meta: { title: '定时任务配置（新）' }
}
```

### Step 4: 测试新页面

1. 访问新页面
2. 测试各项功能：
   - ✅ 列表加载
   - ✅ 创建任务
   - ✅ 编辑任务
   - ✅ 启用/禁用
   - ✅ 删除任务
   - ✅ 热重载
   - ✅ 导入/导出

### Step 5: 切换用户

1. 在导航菜单中添加新页面链接
2. 保留旧页面链接（暂时）
3. 引导用户使用新页面

### Step 6: 废弃旧页面（可选）

1. 观察1-2周
2. 确认新页面稳定
3. 移除旧页面链接
4. 标记旧API为deprecated

---

## 五、迁移完成！

完成以上步骤后，你的前端就完全迁移到新API了，可以享受：

✅ 热重载功能  
✅ 更强大的配置选项  
✅ 更好的用户体验  
✅ 现代化的API设计

---

**文档版本**: 1.0  
**最后更新**: 2026-06-27
