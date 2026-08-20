<template>
  <div class="version-history">
    <el-page-header @back="goBack" title="返回">
      <template #content>
        <span>技能版本历史：{{ skillName }}</span>
      </template>
    </el-page-header>

    <el-card v-loading="loading" style="margin-top: 20px">
      <template #header>
        <span>版本列表</span>
      </template>

      <el-timeline>
        <el-timeline-item
          v-for="version in versions"
          :key="version.version"
          :timestamp="formatTime(version.created_at)"
          placement="top"
        >
          <el-card>
            <div class="version-header">
              <div>
                <el-tag type="primary">v{{ version.version }}</el-tag>
                <span style="margin-left: 10px; font-weight: 600">{{ version.message }}</span>
              </div>
              <div class="version-actions">
                <el-button size="small" @click="viewDiff(version)">查看差异</el-button>
                <el-button size="small" @click="viewContent(version)">查看内容</el-button>
                <el-popconfirm
                  title="确定回滚到此版本吗？"
                  @confirm="rollback(version)"
                >
                  <template #reference>
                    <el-button size="small" type="warning">回滚</el-button>
                  </template>
                </el-popconfirm>
              </div>
            </div>
            <div class="version-meta">
              <el-text type="info" size="small">作者: {{ version.author }}</el-text>
              <el-text type="info" size="small" style="margin-left: 20px">
                Hash: {{ version.hash }}
              </el-text>
            </div>
          </el-card>
        </el-timeline-item>
      </el-timeline>

      <el-empty v-if="versions.length === 0 && !loading" description="暂无版本历史" />
    </el-card>

    <!-- 查看内容对话框 -->
    <el-dialog v-model="showContentDialog" title="版本内容" width="800px">
      <pre class="content-viewer">{{ selectedContent }}</pre>
    </el-dialog>

    <!-- 查看差异对话框 -->
    <el-dialog v-model="showDiffDialog" title="版本差异" width="800px">
      <el-alert
        title="差异对比"
        type="info"
        :closable="false"
        style="margin-bottom: 15px"
      >
        绿色表示新增，红色表示删除
      </el-alert>
      <pre class="diff-viewer">{{ diffContent }}</pre>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { skillApi } from '@/api/skills'
import { formatTime } from '@/utils/format'

const route = useRoute()
const router = useRouter()
const loading = ref(false)
const skillName = ref('')
const versions = ref<any[]>([])
const showContentDialog = ref(false)
const showDiffDialog = ref(false)
const selectedContent = ref('')
const diffContent = ref('')

const loadVersions = async () => {
  loading.value = true
  try {
    const skillId = route.params.id as string
    const result = await skillApi.getSkill(skillId)
    const skill = result.skill
    
    skillName.value = skill.name
    versions.value = skill.versions || []
  } catch (e) {
    console.error('加载版本历史失败:', e)
    ElMessage.error('加载版本历史失败')
  } finally {
    loading.value = false
  }
}

const viewContent = (version: any) => {
  selectedContent.value = version.content || '无内容'
  showContentDialog.value = true
}

const viewDiff = (version: any) => {
  // 与上一个版本做简单行级对比
  const currentIndex = versions.value.findIndex((v) => v.version === version.version)
  const prevVersion = currentIndex > 0 ? versions.value[currentIndex - 1] : null

  const currentLines = String(version.content || '').split('\n')
  const prevLines = String(prevVersion?.content || '').split('\n')

  let diff = ''
  if (!prevVersion) {
    diff = currentLines.map((line: string) => `+ ${line}`).join('\n')
  } else {
    const prevSet = new Set(prevLines)
    const currentSet = new Set(currentLines)
    prevLines.forEach((line: string) => {
      if (!currentSet.has(line)) diff += `- ${line}\n`
    })
    currentLines.forEach((line: string) => {
      if (!prevSet.has(line)) diff += `+ ${line}\n`
    })
  }
  diffContent.value = diff || '（无差异）'
  showDiffDialog.value = true
}

const rollback = async (version: any) => {
  ElMessage.info(`后端暂未提供版本回滚接口（目标 v${version.version}）`)
  await loadVersions()
}

const goBack = () => {
  router.back()
}

onMounted(() => {
  loadVersions()
})
</script>

<style scoped>
.version-history {
  padding: 20px;
}

.version-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 10px;
}

.version-actions {
  display: flex;
  gap: 5px;
}

.version-meta {
  display: flex;
  gap: 15px;
  padding-top: 10px;
  border-top: 1px solid #eee;
}

.content-viewer,
.diff-viewer {
  padding: 15px;
  background: #f5f7fa;
  border-radius: 4px;
  font-family: 'Courier New', monospace;
  font-size: 13px;
  max-height: 500px;
  overflow: auto;
  white-space: pre-wrap;
  word-wrap: break-word;
}

.diff-viewer {
  background: #1e1e1e;
  color: #d4d4d4;
}
</style>
