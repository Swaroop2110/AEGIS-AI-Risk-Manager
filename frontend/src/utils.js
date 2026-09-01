// Utility helpers shared across all components

export function formatINR(paise) {
  if (paise == null) return '—'
  const inr = paise / 100
  if (inr >= 1e7) return `₹${(inr / 1e7).toFixed(2)}Cr`
  if (inr >= 1e5) return `₹${(inr / 1e5).toFixed(2)}L`
  if (inr >= 1e3) return `₹${(inr / 1e3).toFixed(1)}K`
  return `₹${inr.toFixed(2)}`
}

export function formatPct(value) {
  if (value == null) return '—'
  return `${(value * 100).toFixed(1)}%`
}

export function formatMs(ms) {
  if (ms == null) return '—'
  if (ms < 1) return `${(ms * 1000).toFixed(0)}μs`
  return `${ms.toFixed(1)}ms`
}

export function riskColor(score) {
  if (score == null) return 'text-gray-400'
  if (score >= 0.85) return 'text-red-400'
  if (score >= 0.7) return 'text-red-300'
  if (score >= 0.5) return 'text-yellow-400'
  if (score >= 0.3) return 'text-yellow-300'
  return 'text-green-400'
}

export function riskBg(score) {
  if (score == null) return 'bg-gray-700'
  if (score >= 0.85) return 'bg-red-900/60 border border-red-500'
  if (score >= 0.7) return 'bg-red-900/40 border border-red-700'
  if (score >= 0.5) return 'bg-yellow-900/40 border border-yellow-700'
  if (score >= 0.3) return 'bg-yellow-900/20 border border-yellow-900'
  return 'bg-green-900/20 border border-green-900'
}

export function riskLabel(score) {
  if (score == null) return 'Unknown'
  if (score >= 0.85) return 'CRITICAL'
  if (score >= 0.7) return 'HIGH'
  if (score >= 0.5) return 'MEDIUM'
  if (score >= 0.3) return 'ELEVATED'
  return 'LOW'
}

export function riskBadgeClass(level) {
  if (!level) return 'bg-gray-700 text-gray-300'
  switch (level.toLowerCase()) {
    case 'critical': return 'bg-red-600 text-white'
    case 'high': return 'bg-red-500/80 text-white'
    case 'medium': return 'bg-yellow-600/80 text-white'
    case 'low': return 'bg-green-700/80 text-white'
    default: return 'bg-gray-600 text-gray-200'
  }
}

export function actionBadgeClass(action) {
  if (!action) return 'bg-gray-700 text-gray-300'
  switch (action.toLowerCase()) {
    case 'block': return 'bg-red-700 text-white'
    case 'step_up_auth': return 'bg-orange-600 text-white'
    case 'review': return 'bg-yellow-600 text-white'
    case 'approve': return 'bg-green-700 text-white'
    case 'auto_defend': return 'bg-blue-600 text-white'
    case 'accept': return 'bg-gray-600 text-gray-200'
    default: return 'bg-gray-600 text-gray-200'
  }
}

export function shortId(id) {
  if (!id) return '—'
  return id.split('_').slice(-1)[0].slice(0, 8).toUpperCase()
}

export function timeAgo(isoStr) {
  if (!isoStr) return '—'
  const diff = (Date.now() - new Date(isoStr)) / 1000
  if (diff < 60) return `${Math.floor(diff)}s ago`
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`
  return `${Math.floor(diff / 86400)}d ago`
}

export function paymentIcon(method) {
  if (!method) return '💳'
  switch (method) {
    case 'upi': return '📱'
    case 'credit_card': return '💳'
    case 'debit_card': return '🏧'
    case 'wallet': return '👛'
    case 'netbanking': return '🏦'
    default: return '💰'
  }
}
