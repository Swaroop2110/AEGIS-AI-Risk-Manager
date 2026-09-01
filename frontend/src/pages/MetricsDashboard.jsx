import { useQuery } from '@tanstack/react-query'
import { evaluateModel, getAblation, getRoi } from '../api'
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  RadarChart, Radar, PolarGrid, PolarAngleAxis, PolarRadiusAxis
} from 'recharts'
import { formatINR, formatPct } from '../utils'
import { BarChart2, Target, TrendingUp, AlertTriangle } from 'lucide-react'

function MetricCard({ label, value, color = 'text-white', sub }) {
  return (
    <div className="bg-gray-900 border border-gray-800 rounded-xl p-4 text-center">
      <div className={`text-3xl font-bold ${color}`}>{value}</div>
      <div className="text-xs text-gray-500 mt-1 uppercase tracking-wide">{label}</div>
      {sub && <div className="text-xs text-gray-600 mt-1">{sub}</div>}
    </div>
  )
}

function ConfusionMatrix({ matrix }) {
  if (!matrix) return null
  const { tp, fp, tn, fn } = matrix
  return (
    <div className="bg-gray-900 border border-gray-800 rounded-xl p-5">
      <h3 className="text-sm font-semibold text-white mb-4">Confusion Matrix</h3>
      <div className="grid grid-cols-3 gap-2 text-center text-xs">
        <div className="text-gray-500" />
        <div className="text-gray-400 font-medium py-2">Predicted Fraud</div>
        <div className="text-gray-400 font-medium py-2">Predicted Legit</div>
        <div className="text-gray-400 font-medium flex items-center">Actual Fraud</div>
        <div className="bg-green-900/40 border border-green-700/50 rounded-lg p-3">
          <div className="text-xl font-bold text-green-400">{tp?.toLocaleString()}</div>
          <div className="text-gray-500 mt-1">True Positive</div>
        </div>
        <div className="bg-red-900/40 border border-red-700/50 rounded-lg p-3">
          <div className="text-xl font-bold text-red-400">{fn?.toLocaleString()}</div>
          <div className="text-gray-500 mt-1">False Negative</div>
        </div>
        <div className="text-gray-400 font-medium flex items-center">Actual Legit</div>
        <div className="bg-yellow-900/40 border border-yellow-700/50 rounded-lg p-3">
          <div className="text-xl font-bold text-yellow-400">{fp?.toLocaleString()}</div>
          <div className="text-gray-500 mt-1">False Positive</div>
        </div>
        <div className="bg-gray-800 border border-gray-700 rounded-lg p-3">
          <div className="text-xl font-bold text-gray-300">{tn?.toLocaleString()}</div>
          <div className="text-gray-500 mt-1">True Negative</div>
        </div>
      </div>
    </div>
  )
}

export default function MetricsDashboard() {
  const evalQ = useQuery({ queryKey: ['evaluate'], queryFn: () => evaluateModel(0.7) })
  const ablationQ = useQuery({ queryKey: ['ablation'], queryFn: getAblation })
  const roiQ = useQuery({ queryKey: ['roi'], queryFn: getRoi })

  const ev = evalQ.data || {}
  const abl = ablationQ.data?.ablation || {}
  const roi = roiQ.data || {}

  // Radar chart data for model performance
  const radarData = [
    { metric: 'Precision', value: (ev.precision || 0) * 100 },
    { metric: 'Recall', value: (ev.recall || 0) * 100 },
    { metric: 'F1', value: (ev.f1 || 0) * 100 },
    { metric: 'FPR⁻¹', value: (1 - (ev.false_positive_rate || 0)) * 100 },
  ]

  // Ablation bar chart data
  const ablationData = Object.entries(abl)
    .filter(([, v]) => v.f1 != null)
    .map(([name, v]) => ({
      name: name.replace('AEGIS Full', 'AEGIS').replace(' Only', ''),
      f1: Math.round((v.f1 || 0) * 1000) / 10,
      precision: Math.round((v.precision || 0) * 1000) / 10,
      recall: Math.round((v.recall || 0) * 1000) / 10,
    }))

  return (
    <div className="p-6 space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-white flex items-center gap-2">
          <BarChart2 className="text-blue-400" size={24} />
          Metrics & ROI
        </h1>
        <p className="text-gray-500 text-sm mt-1">
          Model performance evaluation and business impact analysis
        </p>
      </div>

      {evalQ.isLoading ? (
        <div className="text-gray-500 text-center py-12">Computing metrics from stored scores...</div>
      ) : (ev.scored_transactions || 0) === 0 ? (
        <div className="bg-yellow-900/20 border border-yellow-800 rounded-xl p-6 text-center text-yellow-400">
          <AlertTriangle size={24} className="mx-auto mb-2" />
          <p>No scored transactions found. Generate data then score some transactions first.</p>
        </div>
      ) : (
        <>
          {/* Model Metrics Row */}
          <div>
            <h2 className="text-sm font-semibold text-gray-400 uppercase mb-3">Model Performance</h2>
            <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-5 gap-3">
              <MetricCard label="Precision" value={formatPct(ev.precision)} color="text-blue-400" />
              <MetricCard label="Recall" value={formatPct(ev.recall)} color="text-green-400" />
              <MetricCard label="F1 Score" value={formatPct(ev.f1)} color="text-purple-400" />
              <MetricCard label="False Positive Rate" value={formatPct(ev.false_positive_rate)} color="text-yellow-400" />
              <MetricCard label="Avg Latency" value={`${(ev.avg_score_latency_ms || 0).toFixed(1)}ms`} color="text-cyan-400" sub={`Scored: ${ev.scored_transactions?.toLocaleString()}`} />
            </div>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Confusion Matrix */}
            <ConfusionMatrix matrix={ev.confusion_matrix} />

            {/* Radar chart */}
            <div className="bg-gray-900 border border-gray-800 rounded-xl p-5">
              <h3 className="text-sm font-semibold text-white mb-4">Performance Radar</h3>
              <ResponsiveContainer width="100%" height={220}>
                <RadarChart data={radarData}>
                  <PolarGrid stroke="#1f2937" />
                  <PolarAngleAxis dataKey="metric" tick={{ fill: '#9ca3af', fontSize: 11 }} />
                  <PolarRadiusAxis angle={90} domain={[0, 100]} tick={{ fill: '#6b7280', fontSize: 9 }} />
                  <Radar name="AEGIS" dataKey="value" stroke="#3b82f6" fill="#3b82f6" fillOpacity={0.3} />
                </RadarChart>
              </ResponsiveContainer>
            </div>
          </div>

          {/* Cost Analysis */}
          {ev.cost_analysis && (
            <div className="bg-gray-900 border border-gray-800 rounded-xl p-5">
              <h3 className="text-sm font-semibold text-white mb-4 flex items-center gap-2">
                <TrendingUp size={16} className="text-green-400" />
                Cost-Weighted Analysis
              </h3>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                <div className="bg-green-900/20 border border-green-800/50 rounded-xl p-4 text-center">
                  <div className="text-2xl font-bold text-green-400">{formatINR(ev.cost_analysis.fraud_prevented_paise)}</div>
                  <div className="text-xs text-gray-500 mt-1">Fraud Prevented (×2.5)</div>
                </div>
                <div className="bg-yellow-900/20 border border-yellow-800/50 rounded-xl p-4 text-center">
                  <div className="text-2xl font-bold text-yellow-400">{formatINR(ev.cost_analysis.false_positive_cost_paise)}</div>
                  <div className="text-xs text-gray-500 mt-1">FP Revenue Lost</div>
                </div>
                <div className="bg-red-900/20 border border-red-800/50 rounded-xl p-4 text-center">
                  <div className="text-2xl font-bold text-red-400">{formatINR(ev.cost_analysis.missed_fraud_cost_paise)}</div>
                  <div className="text-xs text-gray-500 mt-1">Missed Fraud Cost</div>
                </div>
                <div className={`border rounded-xl p-4 text-center ${
                  (ev.cost_analysis.net_impact_paise || 0) >= 0
                    ? 'bg-green-900/20 border-green-800/50'
                    : 'bg-red-900/20 border-red-800/50'
                }`}>
                  <div className={`text-2xl font-bold ${
                    (ev.cost_analysis.net_impact_paise || 0) >= 0 ? 'text-green-400' : 'text-red-400'
                  }`}>{formatINR(Math.abs(ev.cost_analysis.net_impact_paise))}</div>
                  <div className="text-xs text-gray-500 mt-1">Net Impact</div>
                </div>
              </div>
            </div>
          )}

          {/* Ablation study */}
          {ablationData.length > 0 && (
            <div className="bg-gray-900 border border-gray-800 rounded-xl p-5">
              <h3 className="text-sm font-semibold text-white mb-4 flex items-center gap-2">
                <Target size={16} className="text-purple-400" />
                Ablation Study — Layer Comparison
              </h3>
              <ResponsiveContainer width="100%" height={250}>
                <BarChart data={ablationData} margin={{ top: 5, right: 20, bottom: 5, left: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" />
                  <XAxis dataKey="name" tick={{ fill: '#9ca3af', fontSize: 11 }} />
                  <YAxis domain={[0, 100]} tick={{ fill: '#6b7280', fontSize: 10 }} unit="%" />
                  <Tooltip
                    contentStyle={{ background: '#1f2937', border: '1px solid #374151', borderRadius: 8 }}
                    labelStyle={{ color: '#e5e7eb' }}
                  />
                  <Bar dataKey="precision" fill="#3b82f6" name="Precision %" radius={[4, 4, 0, 0]} />
                  <Bar dataKey="recall" fill="#10b981" name="Recall %" radius={[4, 4, 0, 0]} />
                  <Bar dataKey="f1" fill="#a855f7" name="F1 %" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
              <div className="flex gap-4 mt-3 justify-center text-xs text-gray-500">
                <span className="flex items-center gap-1"><span className="w-3 h-3 rounded bg-blue-500" /> Precision</span>
                <span className="flex items-center gap-1"><span className="w-3 h-3 rounded bg-green-500" /> Recall</span>
                <span className="flex items-center gap-1"><span className="w-3 h-3 rounded bg-purple-500" /> F1</span>
              </div>
            </div>
          )}

          {/* ROI Dashboard */}
          {roi.summary && (
            <div className="bg-gray-900 border border-gray-800 rounded-xl p-5">
              <h3 className="text-sm font-semibold text-white mb-4 flex items-center gap-2">
                <TrendingUp size={16} className="text-green-400" />
                ROI Calculator
              </h3>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-4">
                <MetricCard label="Total Volume" value={formatINR(roi.summary.total_amount_paise)} color="text-white" sub={`${roi.summary.total_transactions?.toLocaleString()} txns`} />
                <MetricCard label="Chargebacks Prevented" value={roi.prevention?.chargebacks_prevented?.toLocaleString() || '—'} color="text-green-400" />
                <MetricCard label="Money Saved (2.5×)" value={formatINR(roi.prevention?.money_saved_paise)} color="text-green-400" />
                <MetricCard label="Arb Fees Saved" value={formatINR(roi.dispute_defense?.arbitration_fees_saved_paise)} color="text-blue-400" sub={`${roi.dispute_defense?.disputes_auto_defended} defended`} />
              </div>
              <div className="bg-green-900/20 border border-green-700/50 rounded-xl p-4 text-center">
                <div className="text-xs text-gray-500 mb-1">Total Value Protected</div>
                <div className="text-3xl font-bold text-green-400">
                  {formatINR(roi.roi_summary?.total_value_protected_paise)}
                </div>
                <div className="text-xs text-gray-500 mt-1">fraud prevented + arbitration fees saved</div>
              </div>
            </div>
          )}
        </>
      )}
    </div>
  )
}
