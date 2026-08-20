<template>
  <div class="dependency-graph">
    <el-card>
      <template #header>
        <div class="header">
          <span>任务依赖图谱</span>
          <div class="controls">
            <el-button size="small" @click="resetZoom">
              <el-icon><Refresh /></el-icon>
              重置视图
            </el-button>
            <el-button size="small" @click="fitView">
              <el-icon><FullScreen /></el-icon>
              适应画布
            </el-button>
          </div>
        </div>
      </template>

      <el-alert
        title="提示"
        type="info"
        :closable="false"
        style="margin-bottom: 20px"
      >
        点击节点查看任务详情，拖动节点调整布局，滚轮缩放视图
      </el-alert>

      <!-- 图谱容器 -->
      <div ref="graphContainer" class="graph-container" v-loading="loading">
        <div v-if="!loading && tasks.length === 0" class="empty-state">
          <el-empty description="暂无任务依赖关系" />
        </div>
      </div>

      <!-- 图例 -->
      <div class="legend">
        <div class="legend-item">
          <div class="legend-color" style="background: #67c23a"></div>
          <span>正常</span>
        </div>
        <div class="legend-item">
          <div class="legend-color" style="background: #e6a23c"></div>
          <span>禁用</span>
        </div>
        <div class="legend-item">
          <div class="legend-color" style="background: #f56c6c"></div>
          <span>失败</span>
        </div>
      </div>
    </el-card>

    <!-- 任务详情侧边栏 -->
    <el-drawer v-model="showDetail" title="任务详情" size="400px">
      <el-descriptions v-if="selectedTask" :column="1" border>
        <el-descriptions-item label="任务名称">{{ selectedTask.name }}</el-descriptions-item>
        <el-descriptions-item label="Cron">{{ selectedTask.cron }}</el-descriptions-item>
        <el-descriptions-item label="状态">
          <el-tag :type="selectedTask.enabled ? 'success' : 'info'">
            {{ selectedTask.enabled ? '启用' : '禁用' }}
          </el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="技能">{{ selectedTask.skill_name }}</el-descriptions-item>
        <el-descriptions-item label="依赖任务" v-if="selectedTask.dependencies && selectedTask.dependencies.length > 0">
          <el-tag
            v-for="dep in selectedTask.dependencies"
            :key="dep"
            size="small"
            style="margin-right: 5px"
          >
            {{ dep }}
          </el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="创建时间">
          {{ formatTime(selectedTask.created_at) }}
        </el-descriptions-item>
      </el-descriptions>
    </el-drawer>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import { ElMessage } from 'element-plus'
import { Refresh, FullScreen } from '@element-plus/icons-vue'
import { schedulerApi } from '@/api/scheduler'
import { formatTime } from '@/utils/format'

const loading = ref(false)
const tasks = ref<any[]>([])
const graphContainer = ref<HTMLElement>()
const showDetail = ref(false)
const selectedTask = ref<any>(null)

// 简化的图谱实现（使用 SVG）
let svg: any = null
let zoom: any = null

const loadTasks = async () => {
  loading.value = true
  try {
    const result = await schedulerApi.listTasks()
    tasks.value = result.tasks || []
    
    // 渲染图谱
    if (tasks.value.length > 0) {
      renderGraph()
    }
  } catch (e) {
    console.error('加载任务失败:', e)
    ElMessage.error('加载任务失败')
  } finally {
    loading.value = false
  }
}

const renderGraph = () => {
  if (!graphContainer.value) return

  // 清空容器
  graphContainer.value.innerHTML = ''

  // 创建 SVG
  const width = graphContainer.value.clientWidth
  const height = 500

  const svgEl = document.createElementNS('http://www.w3.org/2000/svg', 'svg')
  svgEl.setAttribute('width', String(width))
  svgEl.setAttribute('height', String(height))
  svgEl.style.border = '1px solid #ddd'
  svgEl.style.background = '#f9f9f9'
  
  graphContainer.value.appendChild(svgEl)

  // 网格布局（避免随机位置重叠）
  const nodes = tasks.value.map((task, i) => {
    const cols = Math.max(3, Math.floor(width / 180))
    const col = i % cols
    const row = Math.floor(i / cols)
    return {
      id: task.id,
      name: task.name,
      x: 90 + col * (width / cols),
      y: 70 + row * 120,
      enabled: task.enabled,
      task: task,
    }
  })

  // 绘制节点
  nodes.forEach(node => {
    const g = document.createElementNS('http://www.w3.org/2000/svg', 'g')
    g.style.cursor = 'pointer'
    
    const circle = document.createElementNS('http://www.w3.org/2000/svg', 'circle')
    circle.setAttribute('cx', String(node.x))
    circle.setAttribute('cy', String(node.y))
    circle.setAttribute('r', '30')
    circle.setAttribute('fill', node.enabled ? '#67c23a' : '#e6a23c')
    circle.setAttribute('stroke', '#fff')
    circle.setAttribute('stroke-width', '2')
    
    const text = document.createElementNS('http://www.w3.org/2000/svg', 'text')
    text.setAttribute('x', String(node.x))
    text.setAttribute('y', String(node.y + 50))
    text.setAttribute('text-anchor', 'middle')
    text.setAttribute('fill', '#333')
    text.setAttribute('font-size', '12')
    text.textContent = node.name.length > 10 ? node.name.substring(0, 10) + '...' : node.name
    
    g.appendChild(circle)
    g.appendChild(text)
    svgEl.appendChild(g)
    
    g.addEventListener('click', () => {
      selectedTask.value = node.task
      showDetail.value = true
    })
  })

  // 依赖连线：后端任务模型暂未提供依赖关系字段（dependencies/depends_on），
  // 待后端补充任务依赖数据后在此绘制连线。
  // 示例：tasks.value.forEach(task => task.dependencies?.forEach(dep => drawEdge(...)))
}

const resetZoom = () => {
  if (tasks.value.length > 0) {
    renderGraph()
  }
}

const fitView = () => {
  resetZoom()
}

onMounted(() => {
  loadTasks()
  
  // 监听窗口大小变化
  window.addEventListener('resize', () => {
    if (tasks.value.length > 0) {
      renderGraph()
    }
  })
})

onUnmounted(() => {
  window.removeEventListener('resize', renderGraph)
})
</script>

<style scoped>
.dependency-graph {
  padding: 20px;
}

.header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.controls {
  display: flex;
  gap: 10px;
}

.graph-container {
  min-height: 500px;
  position: relative;
}

.empty-state {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 500px;
}

.legend {
  display: flex;
  gap: 20px;
  margin-top: 20px;
  padding: 15px;
  background: #f5f7fa;
  border-radius: 4px;
}

.legend-item {
  display: flex;
  align-items: center;
  gap: 8px;
}

.legend-color {
  width: 20px;
  height: 20px;
  border-radius: 50%;
}
</style>
