import axios from 'axios'

const api = axios.create({
  baseURL: '/api/v1',
  headers: { 'Content-Type': 'application/json' },
})

// Dashboard
export const getDashboardStats = () => api.get('/dashboard/stats').then(r => r.data)
export const getRecentTransactions = (limit = 50) =>
  api.get(`/dashboard/transactions/recent?limit=${limit}`).then(r => r.data)
export const getFraudRings = () => api.get('/dashboard/graph/rings').then(r => r.data)
export const getEntitySubgraph = (entityId, hops = 2) =>
  api.get(`/dashboard/graph/nodes/${entityId}?hops=${hops}`).then(r => r.data)
export const getModelMetrics = () => api.get('/dashboard/metrics/model').then(r => r.data)
export const getRecentAttacks = (limit = 10) =>
  api.get(`/dashboard/attacks/recent?limit=${limit}`).then(r => r.data)
export const getDisputeAnalytics = () => api.get('/dashboard/disputes/analytics').then(r => r.data)

// Scoring
export const scoreTransaction = (payload) =>
  api.post('/scoring/score', payload).then(r => r.data)
export const scoreTransactionById = (id) =>
  api.get(`/scoring/score/${id}`).then(r => r.data)
export const scoreBatch = (limit = 100) =>
  api.post(`/scoring/score/batch?limit=${limit}`).then(r => r.data)
export const trainModel = () => api.post('/scoring/train').then(r => r.data)

// Disputes
export const listDisputes = () => api.get('/disputes/list').then(r => r.data)
export const getDispute = (id) => api.get(`/disputes/${id}`).then(r => r.data)
export const autoDefendDispute = (payload) =>
  api.post('/disputes/auto-defend', payload).then(r => r.data)

// Simulator
export const launchAttack = (payload) =>
  api.post('/simulator/attack', payload).then(r => r.data)
export const listAttacks = () => api.get('/simulator/attacks').then(r => r.data)

// Data generation
export const generateData = (payload) =>
  api.post('/data/generate', payload).then(r => r.data)
export const getDataStats = () => api.get('/data/stats').then(r => r.data)

// Metrics
export const evaluateModel = (threshold = 0.7) =>
  api.get(`/metrics/evaluate?threshold=${threshold}`).then(r => r.data)
export const getAblation = () => api.get('/metrics/ablation').then(r => r.data)
export const getRoi = () => api.get('/metrics/roi').then(r => r.data)
