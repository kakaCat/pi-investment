<template>
  <div class="skill-editor">
    <el-page-header @back="goBack" title="返回">
      <template #content>
        <span>编辑技能：{{ form.name }}</span>
      </template>
    </el-page-header>

    <el-card v-loading="loading" style="margin-top: 20px">
      <el-form :model="form" label-width="120px">
        <!-- 基本信息 -->
        <el-divider content-position="left">基本信息</el-divider>
        <el-form-item label="技能名称">
          <el-input v-model="form.name" placeholder="输入技能名称" />
        </el-form-item>
        <el-form-item label="分类">
          <el-select v-model="form.category" placeholder="选择分类">
            <el-option label="数据处理" value="data" />
            <el-option label="分析" value="analysis" />
            <el-option label="通知" value="notification" />
            <el-option label="工具" value="utility" />
            <el-option label="其他" value="other" />
          </el-select>
        </el-form-item>
        <el-form-item label="描述">
          <el-input
            v-model="form.description"
            type="textarea"
            :rows="3"
            placeholder="输入技能描述"
          />
        </el-form-item>
        <el-form-item label="所有者">
          <el-input v-model="form.owner" placeholder="输入所有者" />
        </el-form-item>
        <el-form-item label="状态">
          <el-radio-group v-model="form.status">
            <el-radio label="active">活跃</el-radio>
            <el-radio label="deprecated">已废弃</el-radio>
            <el-radio label="draft">草稿</el-radio>
          </el-radio-group>
        </el-form-item>

        <!-- 技能内容 -->
        <el-divider content-position="left">技能内容</el-divider>
        <el-form-item label="内容格式">
          <el-radio-group v-model="form.contentType">
            <el-radio label="markdown">Markdown</el-radio>
            <el-radio label="json">JSON</el-radio>
            <el-radio label="yaml">YAML</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="内容">
          <div class="editor-container">
            <el-input
              v-model="form.content"
              type="textarea"
              :rows="20"
              placeholder="输入技能内容"
              class="code-editor"
            />
            <div class="editor-toolbar">
              <el-button size="small" @click="previewContent">
                <el-icon><View /></el-icon>
                预览
              </el-button>
              <el-button size="small" @click="formatContent">
                <el-icon><Refresh /></el-icon>
                格式化
              </el-button>
            </div>
          </div>
        </el-form-item>

        <!-- 版本信息 -->
        <el-divider content-position="left">版本信息</el-divider>
        <el-form-item label="提交信息">
          <el-input
            v-model="form.commitMessage"
            placeholder="描述本次修改的内容"
            maxlength="200"
            show-word-limit
          />
        </el-form-item>

        <!-- 操作按钮 -->
        <el-form-item>
          <el-button type="primary" @click="saveSkill" :loading="saving">
            <el-icon><Check /></el-icon>
            保存
          </el-button>
          <el-button @click="goBack">
            <el-icon><Close /></el-icon>
            取消
          </el-button>
          <el-button type="info" @click="saveDraft">
            <el-icon><Document /></el-icon>
            保存草稿
          </el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <!-- 预览对话框 -->
    <el-dialog v-model="showPreview" title="内容预览" width="800px">
      <div v-if="form.contentType === 'markdown'" class="markdown-preview" v-html="renderedMarkdown"></div>
      <pre v-else class="code-preview">{{ form.content }}</pre>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { View, Refresh, Check, Close, Document } from '@element-plus/icons-vue'
import { skillApi } from '@/api/skills'

const route = useRoute()
const router = useRouter()
const loading = ref(false)
const saving = ref(false)
const showPreview = ref(false)

const form = ref({
  name: '',
  category: '',
  description: '',
  owner: '',
  status: 'active',
  contentType: 'markdown',
  content: '',
  commitMessage: '',
})

const renderedMarkdown = computed(() => {
  // TODO: 使用 markdown 解析库
  return `<p>${form.value.content}</p>`
})

const loadSkill = async () => {
  loading.value = true
  try {
    const skillId = route.params.id as string
    const result = await skillApi.getSkill(skillId)
    const skill = result.skill
    
    form.value = {
      name: skill.name,
      category: skill.category,
      description: skill.description,
      owner: skill.owner,
      status: skill.status,
      contentType: skill.content_type || 'markdown',
      content: skill.content || '',
      commitMessage: '',
    }
  } catch (e) {
    console.error('加载技能失败:', e)
    ElMessage.error('加载技能失败')
  } finally {
    loading.value = false
  }
}

const saveSkill = async () => {
  if (!form.value.name) {
    ElMessage.warning('请输入技能名称')
    return
  }
  if (!form.value.commitMessage) {
    ElMessage.warning('请输入提交信息')
    return
  }

  saving.value = true
  try {
    const skillId = route.params.id as string
    await skillApi.updateSkill(skillId, {
      name: form.value.name,
      category: form.value.category,
      description: form.value.description,
      owner: form.value.owner,
      status: form.value.status,
      content: form.value.content,
      commit_message: form.value.commitMessage,
    })
    ElMessage.success('保存成功')
    router.back()
  } catch (e) {
    console.error('保存失败:', e)
    ElMessage.error('保存失败')
  } finally {
    saving.value = false
  }
}

const saveDraft = async () => {
  form.value.status = 'draft'
  form.value.commitMessage = '保存草稿'
  await saveSkill()
}

const previewContent = () => {
  showPreview.value = true
}

const formatContent = () => {
  if (form.value.contentType === 'json') {
    try {
      const parsed = JSON.parse(form.value.content)
      form.value.content = JSON.stringify(parsed, null, 2)
      ElMessage.success('格式化成功')
    } catch (e) {
      ElMessage.error('JSON 格式错误')
    }
  } else {
    ElMessage.info('当前格式不支持自动格式化')
  }
}

const goBack = () => {
  router.back()
}

onMounted(() => {
  loadSkill()
})
</script>

<style scoped>
.skill-editor {
  padding: 20px;
}

.editor-container {
  width: 100%;
  position: relative;
}

.code-editor {
  font-family: 'Courier New', monospace;
  font-size: 13px;
}

.code-editor :deep(textarea) {
  font-family: 'Courier New', monospace;
  font-size: 13px;
}

.editor-toolbar {
  margin-top: 10px;
  display: flex;
  gap: 10px;
}

.markdown-preview {
  padding: 20px;
  background: #f9f9f9;
  border-radius: 4px;
  line-height: 1.8;
}

.code-preview {
  padding: 15px;
  background: #1e1e1e;
  color: #d4d4d4;
  border-radius: 4px;
  font-family: 'Courier New', monospace;
  font-size: 13px;
  max-height: 500px;
  overflow: auto;
}
</style>
