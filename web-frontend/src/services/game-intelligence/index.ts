/**
 * 博弈智能 API 服务
 */
import axios from 'axios'

const API_BASE = 'http://localhost:5001'

// 对手行为分析
export async function getOpponentBehavior() {
  const response = await axios.get(`${API_BASE}/api/game/market/opponent-behavior`)
  return response.data
}

// 博弈预警检查
export async function getAlerts() {
  const response = await axios.get(`${API_BASE}/api/alerts/check`)
  return response.data
}

// 预警统计
export async function getAlertStatistics() {
  const response = await axios.get(`${API_BASE}/api/alerts/statistics`)
  return response.data
}

// 知识库查询
export async function getKnowledgeActive(domain?: string) {
  const params = domain ? { domain } : {}
  const response = await axios.get(`${API_BASE}/api/knowledge/active`, { params })
  return response.data
}

// 知识库摘要
export async function getKnowledgeSummary() {
  const response = await axios.get(`${API_BASE}/api/knowledge/summary`)
  return response.data
}

// 学习报告
export async function getLearningReport() {
  const response = await axios.get(`${API_BASE}/api/learning/report`)
  return response.data
}

// 决策历史
export async function getDecisionHistory(params?: { limit?: number; offset?: number }) {
  const response = await axios.get(`${API_BASE}/api/decisions/history`, { params })
  return response.data
}

// 决策报告
export async function getDecisionReport(startDate?: string, endDate?: string) {
  const params = { start_date: startDate, end_date: endDate }
  const response = await axios.get(`${API_BASE}/api/decisions/report`, { params })
  return response.data
}

// 池子战场评估
export async function getPoolBattlefield(poolId: number) {
  const response = await axios.get(`${API_BASE}/api/game/pools/${poolId}/battlefield-assessment`)
  return response.data
}

// 操纵检测
export async function getManipulationDetect() {
  const response = await axios.get(`${API_BASE}/api/game/market/manipulation-detect`)
  return response.data
}

// 获取自动化配置
export async function getAutomationConfig() {
  const response = await axios.get(`${API_BASE}/api/config/automation`)
  return response.data
}

// 保存自动化配置
export async function saveAutomationConfig(config: any) {
  const response = await axios.post(`${API_BASE}/api/config/automation`, config)
  return response.data
}

// 获取通知配置
export async function getNotificationConfig() {
  const response = await axios.get(`${API_BASE}/api/config/notification`)
  return response.data
}

// 保存通知配置
export async function saveNotificationConfigAPI(config: any) {
  const response = await axios.post(`${API_BASE}/api/config/notification`, config)
  return response.data
}
