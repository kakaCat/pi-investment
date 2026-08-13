<template>
  <div class="memory-page">
    <!-- Tab 切换 -->
    <el-tabs v-model="activeTab" class="mb-4">
      <el-tab-pane label="记忆条目" name="entries">
        <!-- 降级提示 -->
        <div
          v-if="degraded"
          class="bg-amber-50 border border-amber-200 rounded-lg p-3 mb-4 text-sm text-amber-700"
        >
          <span class="font-medium">检索降级：</span>ollama 向量服务不可达，当前为纯 BM25 关键词检索。
        </div>

        <!-- 顶部过滤栏 -->
    <div class="bg-white rounded-xl shadow-sm border border-slate-200 p-5 mb-4">
      <div class="flex items-center justify-between mb-4">
        <h2 class="font-semibold text-slate-800">统一记忆</h2>
        <span class="text-xs text-slate-400">
          {{ total }} 条 · 策略 {{ strategy }}
        </span>
      </div>

      <el-radio-group v-model="filters.kind" size="small" @change="load">
        <el-radio-button value="">全部</el-radio-button>
        <el-radio-button value="rule">规则</el-radio-button>
        <el-radio-button value="episode">事件</el-radio-button>
        <el-radio-button value="experience">经验</el-radio-button>
        <el-radio-button value="stock_note">个股笔记</el-radio-button>
      </el-radio-group>

      <div class="flex items-center gap-2 mt-3">
        <el-select v-model="filters.status" placeholder="全部状态" size="small" style="width: 130px" @change="load">
          <el-option label="全部状态" value="" />
          <el-option label="testing 待确认" value="testing" />
          <el-option label="active 生效中" value="active" />
          <el-option label="deprecated 已废弃" value="deprecated" />
          <el-option label="archived 已归档" value="archived" />
        </el-select>
        <el-input
          v-model="filters.scope"
          placeholder="scope：global / stock:600519 / strategy:v13"
          size="small"
          style="width: 260px"
          clearable
          @change="load"
        />
        <el-input
          v-model="filters.q"
          placeholder="关键词检索（回车触发，BM25+向量混合）"
          size="small"
          style="width: 320px"
          clearable
          @keyup.enter="load"
          @clear="load"
        />
        <button
          class="px-4 py-1.5 bg-blue-500 text-white rounded-lg text-sm font-medium hover:bg-blue-600"
          @click="load"
        >
          搜索
        </button>
      </div>
    </div>

    <!-- 记忆列表 -->
    <div class="bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden mb-4">
      <el-table :data="items" v-loading="loading" size="small" @row-click="openDetail" row-class-name="cursor-pointer">
        <el-table-column prop="id" label="ID" width="60" />
        <el-table-column label="类型" width="90">
          <template #default="{ row }">
            <span class="text-xs px-2 py-0.5 rounded-full" :class="kindClass(row.kind)">{{ kindLabel(row.kind) }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="title" label="标题" min-width="280" show-overflow-tooltip />
        <el-table-column prop="scope" label="范围" width="140" show-overflow-tooltip />
        <el-table-column label="状态" width="100">
          <template #default="{ row }">
            <span class="text-xs px-2 py-0.5 rounded-full" :class="statusClass(row.status)">{{ row.status }}</span>
          </template>
        </el-table-column>
        <el-table-column label="置信度" width="80">
          <template #default="{ row }">{{ row.confidence?.toFixed(2) ?? '-' }}</template>
        </el-table-column>
        <el-table-column label="验证" width="80">
          <template #default="{ row }">{{ row.success_count }}/{{ row.validation_count }}</template>
        </el-table-column>
        <el-table-column label="命中" width="80">
          <template #default="{ row }">
            <span v-if="row.match_source" class="text-xs text-slate-500">{{ row.match_source }}</span>
            <span v-else class="text-xs text-slate-300">-</span>
          </template>
        </el-table-column>
        <el-table-column label="更新时间" width="150">
          <template #default="{ row }">{{ formatTime(row.updated_at) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="180" fixed="right">
          <template #default="{ row }">
            <div class="flex items-center gap-1" @click.stop>
              <button class="text-xs px-2 py-1 border border-slate-200 rounded hover:bg-slate-100" @click="openDetail(row)">
                详情
              </button>
              <template v-if="row.status === 'testing'">
                <button
                  class="text-xs px-2 py-1 border border-green-300 text-green-600 rounded hover:bg-green-50"
                  :disabled="acting"
                  @click="handlePromote(row)"
                >
                  确认生效
                </button>
                <button
                  class="text-xs px-2 py-1 border border-red-200 text-red-500 rounded hover:bg-red-50"
                  :disabled="acting"
                  @click="handleDeprecate(row)"
                >
                  废弃
                </button>
              </template>
            </div>
          </template>
        </el-table-column>
      </el-table>
      <el-empty v-if="!loading && items.length === 0" description="无匹配记忆条目" :image-size="60" />
    </div>

    <!-- T4.4 调度观测简表 -->
    <div class="bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden">
      <div class="flex items-center justify-between px-5 pt-4 pb-2">
        <h3 class="font-semibold text-slate-800 text-sm">调度运行观测（近 {{ runs.length }} 条）</h3>
        <button class="text-xs px-2 py-1 border border-slate-200 rounded hover:bg-slate-100" @click="loadRuns">
          刷新
        </button>
      </div>
      <el-table :data="runs" size="small" max-height="320">
        <el-table-column prop="taskName" label="任务" min-width="180" show-overflow-tooltip />
        <el-table-column label="状态" width="90">
          <template #default="{ row }">
            <span class="text-xs px-2 py-0.5 rounded-full" :class="runStatusClass(row.status)">{{ row.status }}</span>
          </template>
        </el-table-column>
        <el-table-column label="开始时间" width="160">
          <template #default="{ row }">{{ formatTime(row.startedAt) }}</template>
        </el-table-column>
        <el-table-column label="耗时" width="100">
          <template #default="{ row }">{{ formatDuration(row.durationMs) }}</template>
        </el-table-column>
        <el-table-column label="错误" min-width="200">
          <template #default="{ row }">
            <span v-if="row.error" class="text-xs text-red-500" :title="row.error">{{ row.error }}</span>
            <span v-else class="text-xs text-slate-300">-</span>
          </template>
        </el-table-column>
      </el-table>
    </div>
    </el-tab-pane>

    <el-tab-pane label="召回审计" name="audit">
      <RecallAudit />
    </el-tab-pane>
  </el-tabs>

    <!-- T4.2 详情抽屉 -->
    <el-drawer v-model="drawerVisible" size="560px" :title="detail?.title || '记忆详情'">
      <div v-if="detail" class="memory-detail">
        <div class="flex items-center gap-2 mb-3">
          <span class="text-xs px-2 py-0.5 rounded-full" :class="kindClass(detail.kind)">{{ kindLabel(detail.kind) }}</span>
          <span class="text-xs px-2 py-0.5 rounded-full" :class="statusClass(detail.status)">{{ detail.status }}</span>
          <span class="text-xs text-slate-400">{{ detail.scope }}</span>
        </div>

        <div class="detail-section">
          <div class="detail-label">内容</div>
          <div class="text-sm text-slate-700 whitespace-pre-wrap">{{ detail.content }}</div>
        </div>

        <div class="grid grid-cols-3 gap-2 text-xs text-slate-500 mb-3">
          <div>置信度 <strong class="text-slate-700">{{ detail.confidence?.toFixed(2) }}</strong></div>
          <div>验证 <strong class="text-slate-700">{{ detail.success_count }}/{{ detail.validation_count }}</strong></div>
          <div>来源 <strong class="text-slate-700">{{ detail.source || '-' }}</strong></div>
          <div>召回 <strong class="text-slate-700">{{ detail.last_recalled_at ? formatTime(detail.last_recalled_at) : '从未' }}</strong></div>
          <div>创建 <strong class="text-slate-700">{{ formatTime(detail.created_at) }}</strong></div>
          <div>更新 <strong class="text-slate-700">{{ formatTime(detail.updated_at) }}</strong></div>
        </div>

        <div v-if="detail.provenance" class="detail-section">
          <div class="detail-label">出处（provenance）</div>
          <pre class="json-block">{{ pretty(detail.provenance) }}</pre>
        </div>

        <div v-if="hasKeys(detail.payload)" class="detail-section">
          <div class="detail-label">载荷（payload）</div>
          <pre class="json-block">{{ pretty(detail.payload) }}</pre>
        </div>

        <div v-if="hasKeys(detail.evidence)" class="detail-section">
          <div class="detail-label">证据链（evidence）</div>
          <pre class="json-block">{{ pretty(detail.evidence) }}</pre>
          <div v-if="evidenceDecisionIds.length > 0" class="mt-2 flex flex-wrap gap-1">
            <button
              v-for="id in evidenceDecisionIds"
              :key="id"
              class="text-xs px-2 py-1 border border-blue-200 text-blue-600 rounded hover:bg-blue-50"
              @click="openDecision(id)"
            >
              决策 #{{ id }}
            </button>
          </div>
        </div>

        <!-- T4.3 抽屉内也可执行门禁操作 -->
        <div v-if="detail.status === 'testing'" class="flex gap-2 mt-4 pt-3 border-t border-slate-100">
          <button
            class="px-4 py-2 bg-green-500 text-white rounded-lg text-sm font-medium hover:bg-green-600"
            :disabled="acting"
            @click="handlePromote(detail)"
          >
            确认生效（testing → active）
          </button>
          <button
            class="px-4 py-2 bg-red-500 text-white rounded-lg text-sm font-medium hover:bg-red-600"
            :disabled="acting"
            @click="handleDeprecate(detail)"
          >
            废弃
          </button>
        </div>
      </div>
    </el-drawer>

    <!-- 决策详情弹窗（证据链下钻） -->
    <el-dialog v-model="decisionVisible" :title="`决策 #${decisionId}`" width="600px" append-to-body>
      <el-skeleton v-if="decisionLoading" :rows="5" animated />
      <pre v-else-if="decisionData" class="json-block">{{ pretty(decisionData) }}</pre>
      <el-empty v-else description="决策不存在或查询失败" :image-size="60" />
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  memoryApi,
  schedulerRunApi,
  fetchDecision,
  type MemoryEntry,
  type SchedulerRun,
} from '@/services/api/memory'
import RecallAudit from './RecallAudit.vue'

// ---------- Tab 切换 ----------
const activeTab = ref('entries')

// ---------- 列表与过滤（T4.1） ----------
const items = ref<MemoryEntry[]>([])
const total = ref(0)
const degraded = ref(false)
const strategy = ref('')
const loading = ref(false)

const filters = reactive({
  kind: '',
  status: '',
  scope: '',
  q: '',
})

async function load() {
  loading.value = true
  try {
    const resp = await memoryApi.search({
      q: filters.q || undefined,
      kind: filters.kind || undefined,
      status: filters.status || undefined,
      scope: filters.scope || undefined,
      limit: 100,
    })
    items.value = resp.items || []
    total.value = resp.total ?? items.value.length
    degraded.value = !!resp.degraded
    strategy.value = resp.strategy || ''
  } finally {
    loading.value = false
  }
}

// ---------- 详情抽屉（T4.2） ----------
const drawerVisible = ref(false)
const detail = ref<MemoryEntry | null>(null)
const evidenceDecisionIds = ref<number[]>([])

function openDetail(row: MemoryEntry) {
  detail.value = row
  evidenceDecisionIds.value = extractDecisionIds(row.evidence)
  drawerVisible.value = true
}

/** 从 evidence 中提取决策 id：{decision_id: 123} 或 {refs: [1,2]} 两种形态 */
function extractDecisionIds(evidence: Record<string, any> | null): number[] {
  if (!evidence) return []
  const ids = new Set<number>()
  for (const [key, value] of Object.entries(evidence)) {
    if (/decision/i.test(key) && Number.isFinite(Number(value))) {
      ids.add(Number(value))
    }
    if (key === 'refs' && Array.isArray(value)) {
      for (const v of value) {
        if (Number.isFinite(Number(v))) ids.add(Number(v))
      }
    }
  }
  return [...ids]
}

const decisionVisible = ref(false)
const decisionLoading = ref(false)
const decisionId = ref<number>(0)
const decisionData = ref<Record<string, any> | null>(null)

async function openDecision(id: number) {
  decisionId.value = id
  decisionData.value = null
  decisionVisible.value = true
  decisionLoading.value = true
  try {
    decisionData.value = await fetchDecision(id)
  } catch {
    decisionData.value = null
  } finally {
    decisionLoading.value = false
  }
}

// ---------- 确认门禁（T4.3） ----------
const acting = ref(false)

async function handlePromote(row: MemoryEntry) {
  try {
    await ElMessageBox.confirm(
      `确认生效后「${row.title}」将进入 active 状态，参与 agent 召回。`,
      '确认生效',
      { confirmButtonText: '确认生效', cancelButtonText: '取消', type: 'warning' }
    )
  } catch {
    return
  }
  acting.value = true
  try {
    await memoryApi.promote(row.id)
    ElMessage.success(`#${row.id} 已生效（active）`)
    await load()
    if (detail.value?.id === row.id) detail.value = { ...detail.value, status: 'active' }
  } finally {
    acting.value = false
  }
}

async function handleDeprecate(row: MemoryEntry) {
  try {
    await ElMessageBox.confirm(
      `废弃后「${row.title}」将标记为 deprecated，不再参与召回。`,
      '废弃记忆',
      { confirmButtonText: '废弃', cancelButtonText: '取消', type: 'error' }
    )
  } catch {
    return
  }
  acting.value = true
  try {
    await memoryApi.deprecate(row.id)
    ElMessage.success(`#${row.id} 已废弃（deprecated）`)
    await load()
    if (detail.value?.id === row.id) detail.value = { ...detail.value, status: 'deprecated' }
  } finally {
    acting.value = false
  }
}

// ---------- 调度观测（T4.4） ----------
const runs = ref<SchedulerRun[]>([])

async function loadRuns() {
  try {
    const resp = await schedulerRunApi.listRuns(50)
    runs.value = resp.runs || []
  } catch {
    runs.value = []
  }
}

// ---------- 展示辅助 ----------
function kindLabel(kind: string) {
  return { rule: '规则', episode: '事件', experience: '经验', stock_note: '个股' }[kind] || kind
}

function kindClass(kind: string) {
  return {
    rule: 'bg-purple-100 text-purple-700',
    episode: 'bg-blue-100 text-blue-700',
    experience: 'bg-teal-100 text-teal-700',
    stock_note: 'bg-orange-100 text-orange-700',
  }[kind] || 'bg-slate-100 text-slate-600'
}

function statusClass(status: string) {
  return {
    testing: 'bg-amber-100 text-amber-700',
    active: 'bg-green-100 text-green-700',
    deprecated: 'bg-red-100 text-red-500',
    archived: 'bg-slate-100 text-slate-500',
  }[status] || 'bg-slate-100 text-slate-600'
}

function runStatusClass(status: string) {
  return {
    success: 'bg-green-100 text-green-700',
    failed: 'bg-red-100 text-red-600',
    running: 'bg-blue-100 text-blue-600',
    skipped: 'bg-slate-100 text-slate-500',
  }[status] || 'bg-slate-100 text-slate-600'
}

function formatTime(t: string | null | undefined) {
  if (!t) return '-'
  const d = new Date(t)
  if (Number.isNaN(d.getTime())) return t
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${d.getMonth() + 1}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`
}

function formatDuration(ms: number | null | undefined) {
  if (ms == null) return '-'
  if (ms < 1000) return `${ms}ms`
  if (ms < 60_000) return `${(ms / 1000).toFixed(1)}s`
  return `${(ms / 60_000).toFixed(1)}min`
}

function pretty(obj: any) {
  return JSON.stringify(obj, null, 2)
}

function hasKeys(obj: Record<string, any> | null) {
  return !!obj && Object.keys(obj).length > 0
}

onMounted(() => {
  load()
  loadRuns()
})
</script>

<style scoped>
.detail-section {
  margin-bottom: 12px;
}
.detail-label {
  font-size: 12px;
  color: #94a3b8;
  margin-bottom: 4px;
}
.json-block {
  font-size: 12px;
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  padding: 8px;
  max-height: 240px;
  overflow: auto;
  white-space: pre-wrap;
  word-break: break-all;
}
</style>
