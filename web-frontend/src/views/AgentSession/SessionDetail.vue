<template>
  <div class="session-detail-page">
    <el-card>
      <template #header>
        <div class="header-row">
          <span class="title" :title="sessionKey">{{ sessionKey }}</span>
          <el-button size="small" :loading="loading" @click="loadAll">刷新</el-button>
        </div>
      </template>

      <el-tabs v-model="activeTab">
        <!-- ============ Tab 1: 会话回放 ============ -->
        <el-tab-pane label="会话回放" name="replay">
          <div class="filter-row">
            <el-select v-model="eventFilter" size="small" style="width: 130px">
              <el-option label="全部" value="" />
              <el-option label="仅对话" value="dialog" />
              <el-option label="仅工具" value="tool" />
              <el-option label="仅错误" value="error" />
            </el-select>
          </div>

          <el-empty v-if="!loading && filteredTurns.length === 0" description="该会话暂无事件" />

          <el-timeline v-else>
            <template v-for="(turn, i) in filteredTurns" :key="i">
              <el-timeline-item v-if="turn.userText !== null && showDialog" type="primary" :timestamp="formatTime(turn.userTime)">
                <div class="user-msg">👤 {{ turn.userText }}</div>
              </el-timeline-item>

              <el-timeline-item
                v-for="tc in (showTool ? turn.toolCalls : [])"
                :key="`tc-${tc.seq}`"
                :type="tc.success ? 'success' : 'danger'"
                size="small"
              >
                🔧 {{ tc.toolName }}
                <el-tag size="small" :type="tc.success ? 'success' : 'danger'">
                  {{ tc.success ? '✓' : '✗' }} {{ tc.durationMs }}ms
                </el-tag>
                <span v-if="tc.error" class="err-text">{{ tc.error }}</span>
              </el-timeline-item>

              <el-timeline-item v-if="turn.reply && showDialog" type="success" :timestamp="formatTime(turn.replyTime)">
                <div class="reply" :class="{ collapsed: isCollapsed(i) }">🤖 {{ turn.reply }}</div>
                <el-button v-if="turn.reply.length > 200" link type="primary" size="small" @click="toggleCollapse(i)">
                  {{ isCollapsed(i) ? '展开全文' : '收起' }}
                </el-button>
              </el-timeline-item>

              <el-timeline-item
                v-for="(err, j) in (showError ? turn.errors : [])"
                :key="`err-${j}`"
                type="danger"
                :timestamp="formatTime(err.time)"
              >
                ⚠️ [{{ err.stage }}] {{ err.message }}
              </el-timeline-item>
            </template>
          </el-timeline>
        </el-tab-pane>

        <!-- ============ Tab 2: 智能诊断 ============ -->
        <el-tab-pane label="智能诊断" name="diagnosis">
          <div v-if="diagnosis" class="diagnosis-body">
            <div class="metric-cards">
              <el-card class="metric"><div class="metric-value">{{ rateText }}</div><div class="metric-label">工具成功率</div></el-card>
              <el-card class="metric"><div class="metric-value">{{ diagnosis.tool_call_count }}</div><div class="metric-label">工具调用</div></el-card>
              <el-card class="metric"><div class="metric-value">{{ diagnosis.avg_tool_duration_ms }}ms</div><div class="metric-label">平均耗时</div></el-card>
              <el-card class="metric"><div class="metric-value" :style="{ color: diagnosis.error_count > 0 ? '#f56c6c' : 'inherit' }">{{ diagnosis.error_count }}</div><div class="metric-label">错误</div></el-card>
            </div>

            <el-alert v-if="diagnosis.insight" :title="diagnosis.insight" type="info" :closable="false" class="mt-12" />

            <!-- AI 诊断 -->
            <div class="ai-section mt-12">
              <el-button type="primary" :loading="aiLoading" @click="runAiDiagnosis">
                {{ aiResult ? '重新生成 AI 诊断' : 'AI 诊断' }}
              </el-button>
              <span v-if="aiResult" class="ai-time">{{ aiResult.cached ? '缓存于' : '生成于' }} {{ formatTime(aiResult.generated_at) }}</span>
              <el-alert v-if="aiError" :title="aiError" type="error" :closable="false" class="mt-12" />
              <div v-if="aiResult" class="ai-result mt-12">{{ aiResult.analysis }}</div>
            </div>

            <div class="panels mt-20">
              <div class="panel">
                <h4>慢工具 TOP5</h4>
                <div ref="chartRef" class="chart"></div>
              </div>
              <div class="panel">
                <h4>错误聚类</h4>
                <el-table :data="diagnosis.top_errors" size="small">
                  <el-table-column prop="message" label="错误" min-width="200" />
                  <el-table-column prop="cnt" label="次数" width="80" align="center" />
                </el-table>
                <el-empty v-if="diagnosis.top_errors.length === 0" description="无错误" :image-size="60" />
              </div>
            </div>

            <h4 class="mt-20">关联决策</h4>
            <el-table :data="diagnosis.decisions" size="small">
              <el-table-column prop="decision_type" label="类型" width="140" />
              <el-table-column prop="reasoning" label="理由" min-width="240" show-overflow-tooltip />
              <el-table-column label="状态" width="100">
                <template #default="{ row }">
                  <el-tag size="small" :type="statusTagType(row)">{{ statusLabel(row) }}</el-tag>
                </template>
              </el-table-column>
            </el-table>
            <el-empty v-if="diagnosis.decisions.length === 0" description="无关联决策" :image-size="60" />
          </div>
        </el-tab-pane>
      </el-tabs>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, nextTick } from 'vue'
import { useRoute } from 'vue-router'
import { agentSessionApi } from '@/services/api/agentSession'
import { groupEventsToTurns, type Turn } from '@/services/agentSession/replay'
import { useChart } from '@/composables/useChart'
import type { SessionDiagnosis, AiDiagnosis, SessionEvent } from '@/types'

const route = useRoute()
const sessionKey = decodeURIComponent(route.params.key as string)

const activeTab = ref('replay')
const loading = ref(false)
const events = ref<SessionEvent[]>([])
const turns = ref<Turn[]>([])
const diagnosis = ref<SessionDiagnosis | null>(null)
const eventFilter = ref('')

const aiLoading = ref(false)
const aiResult = ref<AiDiagnosis | null>(null)
const aiError = ref('')

const collapsedSet = ref<Set<number>>(new Set())
const isCollapsed = (i: number) => !collapsedSet.value.has(i)
const toggleCollapse = (i: number) => {
  if (isCollapsed(i)) {
    collapsedSet.value.add(i)
  } else {
    collapsedSet.value.delete(i)
  }
}

const showDialog = computed(() => eventFilter.value === '' || eventFilter.value === 'dialog')
const showTool = computed(() => eventFilter.value === '' || eventFilter.value === 'tool')
const showError = computed(() => eventFilter.value === '' || eventFilter.value === 'error')

const filteredTurns = computed(() => {
  if (eventFilter.value === 'error') return turns.value.filter(t => t.errors.length > 0)
  if (eventFilter.value === 'tool') return turns.value.filter(t => t.toolCalls.length > 0)
  return turns.value
})

const rateText = computed(() =>
  diagnosis.value?.tool_success_rate == null ? '-' : `${(diagnosis.value.tool_success_rate * 100).toFixed(0)}%`
)

const { chartRef, setOption } = useChart()

async function loadAll() {
  loading.value = true
  try {
    const [eventsData, diagData] = await Promise.all([
      agentSessionApi.getEvents(sessionKey, { limit: 1000 }),
      agentSessionApi.getDiagnosis(sessionKey),
    ])
    events.value = eventsData.events
    turns.value = groupEventsToTurns(eventsData.events)
    diagnosis.value = diagData
    await nextTick()
    renderSlowToolChart()
  } finally {
    loading.value = false
  }
}

function renderSlowToolChart() {
  if (!chartRef.value) return
  const toolMax = new Map<string, number>()
  for (const e of events.value) {
    if (e.event_type !== 'tool_call') continue
    const name = e.payload.toolName ?? 'unknown'
    const ms = e.payload.durationMs ?? 0
    toolMax.set(name, Math.max(toolMax.get(name) ?? 0, ms))
  }
  const top5 = [...toolMax.entries()].sort((a, b) => b[1] - a[1]).slice(0, 5)
  if (top5.length === 0) return
  setOption({
    grid: { left: 120, right: 30, top: 10, bottom: 20 },
    xAxis: { type: 'value', name: 'ms' },
    yAxis: { type: 'category', data: top5.map(([n]) => n).reverse() },
    series: [{ type: 'bar', data: top5.map(([, v]) => v).reverse(), itemStyle: { color: '#5470c6' } }],
  })
}

async function runAiDiagnosis() {
  aiLoading.value = true
  aiError.value = ''
  try {
    aiResult.value = await agentSessionApi.aiDiagnosis(sessionKey, !!aiResult.value)
  } catch (e: any) {
    aiError.value = e?.message ?? 'AI 诊断失败，请稍后重试'
  } finally {
    aiLoading.value = false
  }
}

function statusLabel(row: { evaluation_status: string; success: boolean | null }): string {
  if (row.evaluation_status === 'evaluated') return row.success ? '成功' : '失败'
  return '待评估'
}
function statusTagType(row: { evaluation_status: string; success: boolean | null }): any {
  if (row.evaluation_status === 'evaluated') return row.success ? 'success' : 'danger'
  return 'info'
}

function formatTime(iso: string | null): string {
  if (!iso) return ''
  const d = new Date(iso)
  return isNaN(d.getTime()) ? String(iso) : d.toLocaleString('zh-CN', { hour: '2-digit', minute: '2-digit', second: '2-digit' })
}

onMounted(loadAll)
</script>

<style scoped>
.header-row { display: flex; justify-content: space-between; align-items: center; }
.title { font-weight: 600; font-size: 13px; word-break: break-all; }
.filter-row { margin-bottom: 12px; }
.user-msg { font-weight: 600; }
.reply.collapsed { display: -webkit-box; -webkit-line-clamp: 3; -webkit-box-orient: vertical; overflow: hidden; }
.err-text { color: #f56c6c; margin-left: 8px; }
.metric-cards { display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; }
.metric { text-align: center; }
.metric-value { font-size: 24px; font-weight: 700; }
.metric-label { color: #909399; font-size: 12px; margin-top: 4px; }
.mt-12 { margin-top: 12px; }
.mt-20 { margin-top: 20px; }
.panels { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }
.chart { height: 200px; }
.ai-section .ai-time { margin-left: 12px; color: #909399; font-size: 12px; }
.ai-result { white-space: pre-wrap; background: #f5f7fa; padding: 16px; border-radius: 4px; line-height: 1.8; }
</style>
