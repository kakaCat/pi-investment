<template>
  <el-card class="signal-card" :class="[`signal-${signal.type}`, `status-${signal.status}`]">
    <template #header>
      <div class="card-header">
        <div class="header-left">
          <el-tag :type="signal.type === 'buy' ? 'success' : 'danger'" size="large">
            {{ signal.type === 'buy' ? '买入' : '卖出' }}
          </el-tag>
          <span class="symbol">{{ signal.symbol }}</span>
          <span class="symbol-name">{{ signal.symbolName }}</span>
        </div>
        <div class="header-right">
          <el-tag :type="getStatusType(signal.status)" size="small">
            {{ getStatusText(signal.status) }}
          </el-tag>
        </div>
      </div>
    </template>

    <div class="card-body">
      <div class="info-row">
        <div class="info-item">
          <span class="label">价格</span>
          <span class="value price">¥{{ signal.price.toFixed(2) }}</span>
        </div>
        <div class="info-item">
          <span class="label">置信度</span>
          <span class="value confidence">
            <el-progress
              :percentage="signal.confidence * 100"
              :color="getConfidenceColor(signal.confidence)"
              :stroke-width="8"
            />
          </span>
        </div>
        <div class="info-item">
          <span class="label">操作者</span>
          <span class="value">
            <el-tag :type="signal.operator === 'agent' ? 'info' : 'warning'" size="small">
              {{ signal.operator === 'agent' ? 'Agent' : '手动' }}
            </el-tag>
          </span>
        </div>
      </div>

      <div class="info-row">
        <div class="info-item full-width">
          <span class="label">创建时间</span>
          <span class="value">{{ formatTime(signal.createdAt) }}</span>
        </div>
      </div>

      <div v-if="signal.reasons && signal.reasons.length > 0" class="reasons-section">
        <div class="label">信号原因</div>
        <ul class="reasons-list">
          <li v-for="(reason, index) in signal.reasons" :key="index">
            {{ reason }}
          </li>
        </ul>
      </div>

      <div v-if="signal.analysis" class="analysis-section">
        <el-collapse>
          <el-collapse-item title="详细分析" name="analysis">
            <div class="analysis-content">
              <div class="analysis-group">
                <h4>技术指标</h4>
                <div class="analysis-items">
                  <div class="analysis-item">
                    <span>RSI:</span>
                    <span>{{ signal.analysis.technical.rsi.toFixed(2) }}</span>
                  </div>
                  <div class="analysis-item">
                    <span>MACD:</span>
                    <span>{{ signal.analysis.technical.macd.value.toFixed(2) }}</span>
                  </div>
                  <div class="analysis-item">
                    <span>MA5:</span>
                    <span>{{ signal.analysis.technical.ma.ma5.toFixed(2) }}</span>
                  </div>
                  <div class="analysis-item">
                    <span>MA20:</span>
                    <span>{{ signal.analysis.technical.ma.ma20.toFixed(2) }}</span>
                  </div>
                </div>
              </div>

              <div class="analysis-group">
                <h4>基本面</h4>
                <div class="analysis-items">
                  <div class="analysis-item">
                    <span>PE:</span>
                    <span>{{ signal.analysis.fundamental.pe.toFixed(2) }}</span>
                  </div>
                  <div class="analysis-item">
                    <span>ROE:</span>
                    <span>{{ (signal.analysis.fundamental.roe * 100).toFixed(2) }}%</span>
                  </div>
                  <div class="analysis-item">
                    <span>毛利率:</span>
                    <span>{{ (signal.analysis.fundamental.grossMargin * 100).toFixed(2) }}%</span>
                  </div>
                </div>
              </div>

              <div class="analysis-group">
                <h4>市场情绪</h4>
                <div class="analysis-items">
                  <div class="analysis-item">
                    <span>资金流向:</span>
                    <span :class="signal.analysis.sentiment.fundFlow > 0 ? 'positive' : 'negative'">
                      {{ (signal.analysis.sentiment.fundFlow / 10000).toFixed(2) }}万
                    </span>
                  </div>
                  <div class="analysis-item">
                    <span>龙虎榜:</span>
                    <span>{{ signal.analysis.sentiment.dragonTiger ? '是' : '否' }}</span>
                  </div>
                </div>
              </div>
            </div>
          </el-collapse-item>
        </el-collapse>
      </div>

      <div v-if="signal.pnl" class="pnl-section">
        <div class="pnl-item">
          <span class="label">未实现盈亏</span>
          <span class="value" :class="signal.pnl.unrealizedPnL >= 0 ? 'positive' : 'negative'">
            ¥{{ signal.pnl.unrealizedPnL.toFixed(2) }}
            ({{ signal.pnl.unrealizedPnLPercent >= 0 ? '+' : '' }}{{ (signal.pnl.unrealizedPnLPercent * 100).toFixed(2) }}%)
          </span>
        </div>
      </div>
    </div>

    <template #footer>
      <div class="card-footer">
        <el-button
          v-if="signal.status === 'pending'"
          type="success"
          :icon="Check"
          @click="handleApprove"
        >
          批准
        </el-button>
        <el-button
          v-if="signal.status === 'pending'"
          type="danger"
          :icon="Close"
          @click="handleReject"
        >
          拒绝
        </el-button>
        <el-button
          v-if="signal.status === 'pending'"
          type="primary"
          :icon="View"
          @click="handleVerify"
        >
          验证
        </el-button>
        <el-button
          v-if="signal.status === 'approved' || signal.status === 'executed'"
          type="info"
          :icon="Document"
          @click="handleViewDetail"
        >
          查看详情
        </el-button>
      </div>
    </template>
  </el-card>
</template>

<script setup lang="ts">
import { Check, Close, View, Document } from '@element-plus/icons-vue'
import type { TradingSignal } from '@/types/models'
import dayjs from 'dayjs'

interface Props {
  signal: TradingSignal
}

interface Emits {
  (e: 'approve', signal: TradingSignal): void
  (e: 'reject', signal: TradingSignal): void
  (e: 'verify', signal: TradingSignal): void
  (e: 'view-detail', signal: TradingSignal): void
}

const props = defineProps<Props>()
const emit = defineEmits<Emits>()

const getStatusType = (status: string) => {
  const typeMap: Record<string, any> = {
    pending: 'warning',
    approved: 'success',
    rejected: 'danger',
    executed: 'info'
  }
  return typeMap[status] || 'info'
}

const getStatusText = (status: string) => {
  const textMap: Record<string, string> = {
    pending: '待处理',
    approved: '已批准',
    rejected: '已拒绝',
    executed: '已执行'
  }
  return textMap[status] || status
}

const getConfidenceColor = (confidence: number) => {
  if (confidence >= 0.8) return '#52c41a'
  if (confidence >= 0.6) return '#faad14'
  return '#f5222d'
}

const formatTime = (time: string) => {
  return dayjs(time).format('YYYY-MM-DD HH:mm:ss')
}

const handleApprove = () => {
  emit('approve', props.signal)
}

const handleReject = () => {
  emit('reject', props.signal)
}

const handleVerify = () => {
  emit('verify', props.signal)
}

const handleViewDetail = () => {
  emit('view-detail', props.signal)
}
</script>

<style scoped>
.signal-card {
  margin-bottom: 16px;
  transition: all 0.3s;
}

.signal-card:hover {
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
}

.signal-buy {
  border-left: 4px solid #52c41a;
}

.signal-sell {
  border-left: 4px solid #f5222d;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 12px;
}

.symbol {
  font-size: 18px;
  font-weight: bold;
  color: #262626;
}

.symbol-name {
  font-size: 14px;
  color: #8c8c8c;
}

.card-body {
  padding: 16px 0;
}

.info-row {
  display: flex;
  gap: 24px;
  margin-bottom: 16px;
}

.info-item {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.info-item.full-width {
  flex: none;
  width: 100%;
}

.label {
  font-size: 12px;
  color: #8c8c8c;
}

.value {
  font-size: 14px;
  color: #262626;
  font-weight: 500;
}

.value.price {
  font-size: 20px;
  font-weight: bold;
  color: #1890ff;
}

.value.confidence {
  width: 100%;
}

.reasons-section {
  margin-top: 16px;
  padding: 12px;
  background: #f5f5f5;
  border-radius: 4px;
}

.reasons-list {
  margin: 8px 0 0 0;
  padding-left: 20px;
}

.reasons-list li {
  margin-bottom: 4px;
  color: #595959;
  font-size: 13px;
}

.analysis-section {
  margin-top: 16px;
}

.analysis-content {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.analysis-group h4 {
  margin: 0 0 8px 0;
  font-size: 14px;
  color: #262626;
}

.analysis-items {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 8px;
}

.analysis-item {
  display: flex;
  justify-content: space-between;
  padding: 4px 8px;
  background: #fafafa;
  border-radius: 4px;
  font-size: 13px;
}

.pnl-section {
  margin-top: 16px;
  padding: 12px;
  background: #f0f5ff;
  border-radius: 4px;
}

.pnl-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.positive {
  color: #52c41a;
  font-weight: bold;
}

.negative {
  color: #f5222d;
  font-weight: bold;
}

.card-footer {
  display: flex;
  gap: 8px;
  justify-content: flex-end;
}
</style>
