import { useEffect, useRef, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { getDashboardStats, getRecentTransactions } from '../api'
import {
  formatINR, formatPct, formatMs, riskBadgeClass, actionBadgeClass,
  shortId, timeAgo, paymentIcon, riskColor
} from '../utils'
import { Activity, AlertTriangle, TrendingUp, Shield, Clock, Zap, CheckCircle, XCircle } from 'lucide-react'

function KpiCard({ label, value, sub, icon: Icon, color = 'text-blue-400', trend }) {
  return (
    <div className="bg-gray-900 border border-gray-800 rounded-xl p-4 flex flex-col gap-1">
      <div className="flex items-center justify-between">
        <span className="text-xs text-gray-500 uppercase tracking-wide">{label}</span>
        {Icon && <Icon size={16} className={color} />}
      </div>
      <div className={`text-2xl font-bold ${color}`}>{value}</div>
      {sub && <div className="text-xs text-gray-500">{sub}</div>}
    </div>
  )
}

function RiskScoreBar({ score }) {
  if (score == null) return <span className="text-gray-600 text-xs">—</span>
  const pct = Math.round(score * 100)
  const color =
    score >= 0.85 ? 'bg-red-500' :
    score >= 0.7 ? 'bg-red-400' :
    score >= 0.5 ? 'bg-yellow-400' :
    score >= 0.3 ? 'bg-yellow-600' : 'bg-green-500'
  return (
    <div className="flex items-center gap-2">
      <div className="flex-1 h-1.5 bg-gray-800 rounded-full overflow-hidden">
        <div className={`h-full ${color} rounded-full`} style={{ width: `${pct}%` }} />
      </div>
      <span className={`text-xs tabular-nums ${riskColor(score)}`}>{pct}</span>
    </div>
  )
}

export default function WarRoom() {
  const statsQ = useQuery({ queryKey: ['stats'], queryFn: getDashboardStats, refetchInterval: 10000 })
  const txnQ = useQuery({ queryKey: ['recent-txns'], queryFn: () => getRecentTransactions(100), refetchInterval: 8000 })

  const stats = statsQ.data || {}
  const txns = txnQ.data?.transactions || []

  // WebSocket live ticker
  const [liveTicker, setLiveTicker] = useState([])
  const wsRef = useRef(null)

  useEffect(() => {
    const ws = new WebSocket(`ws://${window.location.hostname}:8000/api/v1/dashboard/ws/stream`)
    wsRef.current = ws
    ws.onmessage = (e) => {
      try {
        const msg = JSON.parse(e.data)
        if (msg.type === 'transaction') {
          setLiveTicker(prev => [msg.data, ...prev].slice(0, 10))
        }
      } catch { /* ignore */ }
    }
    return () => ws.close()
  }, [])

  const highRisk = txns.filter(t => (t.aegis_score || 0) >= 0.7)
  const rings = txns.filter(t => t.ring_detected)

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white flex items-center gap-2">
            <Shield className="text-blue-400" size={26} />
            Fraud War Room
          </h1>
          <p className="text-gray-500 text-sm mt-1">Real-time transaction risk monitoring</p>
        </div>
        <div className="flex items-center gap-2 text-xs">
          <span className="w-2 h-2 rounded-full bg-green-400 animate-pulse" />
          <span className="text-gray-400">Live</span>
        </div>
      </div>

      {/* KPI Row */}
      <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-3">
        <KpiCard
          label="Total Transactions"
          value={(stats.total_transactions || 0).toLocaleString()}
          icon={Activity}
          color="text-blue-400"
        />
        <KpiCard
          label="Fraud Detected"
          value={(stats.fraud_detected || 0).toLocaleString()}
          sub={`Rate: ${formatPct(stats.fraud_rate)}`}
          icon={AlertTriangle}
          color="text-red-400"
        />
        <KpiCard
          label="Money Saved"
          value={formatINR(stats.money_saved)}
          sub="from blocked fraud"
          icon={TrendingUp}
          color="text-green-400"
        />
        <KpiCard
          label="Disputes Won"
          value={(stats.disputes_won || 0).toLocaleString()}
          sub={`Win rate: ${formatPct(stats.win_rate)}`}
          icon={CheckCircle}
          color="text-emerald-400"
        />
        <KpiCard
          label="Avg Score Latency"
          value={formatMs(stats.avg_score_latency_ms)}
          icon={Zap}
          color="text-yellow-400"
        />
        <KpiCard
          label="Model F1"
          value={stats.model_f1 ? stats.model_f1.toFixed(3) : '—'}
          sub={`P: ${stats.model_precision?.toFixed(2) || '—'} R: ${stats.model_recall?.toFixed(2) || '—'}`}
          icon={Shield}
          color="text-purple-400"
        />
      </div>

      {/* Alert banners */}
      {highRisk.length > 0 && (
        <div className="bg-red-900/30 border border-red-700/50 rounded-xl p-3 flex items-center gap-3">
          <AlertTriangle size={18} className="text-red-400 shrink-0" />
          <span className="text-red-300 text-sm">
            <strong>{highRisk.length} high-risk transactions</strong> detected in recent activity.
            {rings.length > 0 && ` · ${rings.length} abuse ring(s) identified.`}
          </span>
        </div>
      )}

      {/* Live Transaction Feed */}
      <div className="bg-gray-900 border border-gray-800 rounded-xl overflow-hidden">
        <div className="px-4 py-3 border-b border-gray-800 flex items-center justify-between">
          <h2 className="font-semibold text-white text-sm flex items-center gap-2">
            <Activity size={16} className="text-blue-400" />
            Live Transaction Feed
          </h2>
          <span className="text-xs text-gray-500">{txns.length} shown</span>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-800">
                {['ID', 'Amount', 'Method', 'Risk Score', 'Risk Level', 'Action', 'Ring', 'Fraud', 'Time'].map(h => (
                  <th key={h} className="px-3 py-2 text-left text-xs text-gray-500 font-medium">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {txns.length === 0 ? (
                <tr>
                  <td colSpan={9} className="px-3 py-8 text-center text-gray-600">
                    No transactions yet — generate data and score transactions to see the feed.
                  </td>
                </tr>
              ) : txns.map(t => (
                <tr key={t.id} className="border-b border-gray-800/50 hover:bg-gray-800/30 transition-colors">
                  <td className="px-3 py-2 font-mono text-xs text-gray-400">{shortId(t.id)}</td>
                  <td className="px-3 py-2 font-medium text-white">{formatINR(t.amount)}</td>
                  <td className="px-3 py-2 text-gray-400">
                    <span>{paymentIcon(t.payment_method)} {t.payment_method}</span>
                  </td>
                  <td className="px-3 py-2 min-w-[100px]">
                    <RiskScoreBar score={t.aegis_score} />
                  </td>
                  <td className="px-3 py-2">
                    {t.risk_level ? (
                      <span className={`text-xs px-2 py-0.5 rounded font-medium ${riskBadgeClass(t.risk_level)}`}>
                        {t.risk_level.toUpperCase()}
                      </span>
                    ) : <span className="text-gray-600">—</span>}
                  </td>
                  <td className="px-3 py-2">
                    {t.recommended_action ? (
                      <span className={`text-xs px-2 py-0.5 rounded font-medium ${actionBadgeClass(t.recommended_action)}`}>
                        {t.recommended_action.replace(/_/g, ' ')}
                      </span>
                    ) : <span className="text-gray-600">—</span>}
                  </td>
                  <td className="px-3 py-2 text-center">
                    {t.ring_detected ? (
                      <span className="text-red-400 text-xs ring-pulse">🔴 ring</span>
                    ) : <span className="text-gray-700">—</span>}
                  </td>
                  <td className="px-3 py-2 text-center">
                    {t.is_fraud ? (
                      <span className="text-red-400 text-xs">⚠️ {t.fraud_type?.replace(/_/g, ' ')}</span>
                    ) : <span className="text-green-700 text-xs">✓ legit</span>}
                  </td>
                  <td className="px-3 py-2 text-gray-500 text-xs whitespace-nowrap">
                    {timeAgo(t.created_at)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
