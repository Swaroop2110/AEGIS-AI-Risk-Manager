import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { launchAttack, getRecentAttacks } from '../api'
import { formatMs, formatPct, shortId } from '../utils'
import { Zap, Target, AlertTriangle, CheckCircle, Clock, BarChart2 } from 'lucide-react'

const ATTACK_VECTORS = [
  {
    key: 'velocity',
    icon: '💳',
    label: 'Velocity Attack',
    sub: 'Carding burst',
    desc: '15-25 rapid micro-transactions from a single device/card in under 2 minutes. Tests velocity rule triggers.',
    color: 'border-orange-700 hover:border-orange-500',
    badgeColor: 'bg-orange-900/30 border-orange-700 text-orange-300',
  },
  {
    key: 'mule_ring',
    icon: '🔗',
    label: 'Mule Ring',
    sub: 'Money laundering',
    desc: 'Dormant account receives large inflow then fans out to multiple VPAs. Tests graph ring detection.',
    color: 'border-red-700 hover:border-red-500',
    badgeColor: 'bg-red-900/30 border-red-700 text-red-300',
  },
  {
    key: 'friendly_fraud',
    icon: '🎭',
    label: 'Friendly Fraud',
    sub: 'Chargeback abuse',
    desc: 'Genuine 3DS-verified purchase, delivery confirmed, then chargeback filed 45 days later. Tests causal engine.',
    color: 'border-yellow-700 hover:border-yellow-500',
    badgeColor: 'bg-yellow-900/30 border-yellow-700 text-yellow-300',
  },
  {
    key: 'device_spoofing',
    icon: '📱',
    label: 'Device Spoofing',
    sub: 'Shared device ring',
    desc: '1 physical device, 10-20 different customer identities — targets high-value electronics merchants.',
    color: 'border-purple-700 hover:border-purple-500',
    badgeColor: 'bg-purple-900/30 border-purple-700 text-purple-300',
  },
  {
    key: 'account_takeover',
    icon: '🕵️',
    label: 'Account Takeover',
    sub: 'ATO simulation',
    desc: 'Legitimate account, sudden behavior shift: new device, unknown IP, 3 AM, 10× normal spend. Tests anomaly detection.',
    color: 'border-pink-700 hover:border-pink-500',
    badgeColor: 'bg-pink-900/30 border-pink-700 text-pink-300',
  },
]

function AttackCard({ vector, onLaunch, loading }) {
  return (
    <div className={`bg-gray-900 border rounded-xl p-5 transition-all flex flex-col gap-3 ${vector.color}`}>
      <div className="flex items-start justify-between">
        <div>
          <span className="text-2xl">{vector.icon}</span>
          <h3 className="font-semibold text-white mt-1">{vector.label}</h3>
          <p className="text-xs text-gray-500">{vector.sub}</p>
        </div>
        <span className={`text-xs px-2 py-0.5 rounded-full border ${vector.badgeColor}`}>ATTACK</span>
      </div>
      <p className="text-sm text-gray-400">{vector.desc}</p>
      <div className="flex gap-2 mt-auto pt-2">
        {['low', 'medium', 'high'].map(intensity => (
          <button
            key={intensity}
            onClick={() => onLaunch(vector.key, intensity, intensity === 'high' ? 20 : intensity === 'medium' ? 10 : 5)}
            disabled={loading}
            className={`flex-1 text-xs py-2 rounded-lg border transition-all font-medium ${
              loading
                ? 'border-gray-700 text-gray-600 cursor-not-allowed'
                : intensity === 'high'
                ? 'border-red-700 text-red-300 hover:bg-red-900/30'
                : intensity === 'medium'
                ? 'border-yellow-700 text-yellow-300 hover:bg-yellow-900/30'
                : 'border-green-800 text-green-400 hover:bg-green-900/20'
            }`}
          >
            {intensity.toUpperCase()}
          </button>
        ))}
      </div>
    </div>
  )
}

function AttackResult({ result }) {
  if (!result) return null
  const detectionPct = result.detection_rate * 100
  const isGood = detectionPct >= 70

  return (
    <div className={`border rounded-xl p-5 ${isGood ? 'bg-green-900/10 border-green-700/50' : 'bg-red-900/10 border-red-700/50'}`}>
      <div className="flex items-center gap-2 mb-3">
        {isGood
          ? <CheckCircle size={18} className="text-green-400" />
          : <AlertTriangle size={18} className="text-yellow-400" />
        }
        <span className="font-semibold text-white">Attack Result: {result.attack_type.replace(/_/g, ' ').toUpperCase()}</span>
      </div>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <div className="bg-gray-900/50 rounded-lg p-3 text-center">
          <div className="text-2xl font-bold text-white">{result.transactions_injected}</div>
          <div className="text-xs text-gray-500">Injected</div>
        </div>
        <div className={`rounded-lg p-3 text-center ${isGood ? 'bg-green-900/30' : 'bg-red-900/30'}`}>
          <div className={`text-2xl font-bold ${isGood ? 'text-green-400' : 'text-red-400'}`}>{result.detected_count}</div>
          <div className="text-xs text-gray-500">Detected</div>
        </div>
        <div className="bg-gray-900/50 rounded-lg p-3 text-center">
          <div className={`text-2xl font-bold ${isGood ? 'text-green-400' : 'text-yellow-400'}`}>{formatPct(result.detection_rate)}</div>
          <div className="text-xs text-gray-500">Detection Rate</div>
        </div>
        <div className="bg-gray-900/50 rounded-lg p-3 text-center">
          <div className="text-2xl font-bold text-blue-400">{result.rings_identified}</div>
          <div className="text-xs text-gray-500">Rings Found</div>
        </div>
      </div>
      <div className="mt-3 flex items-center gap-2 text-sm">
        <Clock size={14} className="text-gray-500" />
        <span className="text-gray-400">Avg detection latency: </span>
        <span className="text-blue-400 font-medium">{formatMs(result.avg_detection_latency_ms)}</span>
      </div>
      {/* Detection bar */}
      <div className="mt-3">
        <div className="flex justify-between text-xs text-gray-500 mb-1">
          <span>Detection Rate</span>
          <span>{formatPct(result.detection_rate)}</span>
        </div>
        <div className="h-2 bg-gray-800 rounded-full overflow-hidden">
          <div
            className={`h-full rounded-full transition-all ${isGood ? 'bg-green-500' : 'bg-yellow-500'}`}
            style={{ width: `${detectionPct}%` }}
          />
        </div>
      </div>
    </div>
  )
}

export default function AttackSimulator() {
  const [lastResult, setLastResult] = useState(null)
  const [loadingVector, setLoadingVector] = useState(null)
  const qc = useQueryClient()
  const historyQ = useQuery({ queryKey: ['attack-history'], queryFn: getRecentAttacks })

  const mutation = useMutation({
    mutationFn: ({ type, intensity, count }) => launchAttack({
      attack_type: type, intensity, num_transactions: count
    }),
    onSuccess: (data) => {
      setLastResult(data)
      setLoadingVector(null)
      qc.invalidateQueries(['attack-history'])
      qc.invalidateQueries(['stats'])
      qc.invalidateQueries(['recent-txns'])
      qc.invalidateQueries(['rings'])
    },
    onError: (err) => {
      setLoadingVector(null)
      alert(err.response?.data?.detail || 'Attack failed. Generate Phase 1 data first.')
    }
  })

  const handleLaunch = (type, intensity, count) => {
    setLoadingVector(type)
    setLastResult(null)
    mutation.mutate({ type, intensity, count })
  }

  return (
    <div className="p-6 space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-white flex items-center gap-2">
          <Zap className="text-yellow-400" size={24} />
          Attack Simulator
        </h1>
        <p className="text-gray-500 text-sm mt-1">
          Chaos engineering — inject fraud attacks and watch AEGIS respond in real-time
        </p>
        <div className="mt-2 p-3 bg-yellow-900/20 border border-yellow-800/50 rounded-lg text-xs text-yellow-400">
          ⚠️ Requires Phase 1 data to be generated first. Go to <strong>Data Manager</strong> if you haven't yet.
        </div>
      </div>

      {/* Live result */}
      {(mutation.isPending || lastResult) && (
        <div>
          {mutation.isPending ? (
            <div className="bg-gray-900 border border-blue-700/50 rounded-xl p-5 flex items-center gap-3">
              <div className="w-4 h-4 border-2 border-blue-400 border-t-transparent rounded-full animate-spin" />
              <span className="text-blue-300">
                Launching <strong>{loadingVector?.replace(/_/g, ' ')}</strong> attack and scoring through AEGIS pipeline...
              </span>
            </div>
          ) : (
            <AttackResult result={lastResult} />
          )}
        </div>
      )}

      {/* Attack cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {ATTACK_VECTORS.map(v => (
          <AttackCard
            key={v.key}
            vector={v}
            onLaunch={handleLaunch}
            loading={mutation.isPending}
          />
        ))}
      </div>

      {/* History table */}
      <div className="bg-gray-900 border border-gray-800 rounded-xl overflow-hidden">
        <div className="px-4 py-3 border-b border-gray-800 flex items-center gap-2">
          <BarChart2 size={16} className="text-blue-400" />
          <h2 className="font-semibold text-white text-sm">Attack History</h2>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-800">
                {['Attack ID', 'Type', 'Intensity', 'Injected', 'Detected', 'Rate', 'Rings', 'Latency', 'Time'].map(h => (
                  <th key={h} className="px-3 py-2 text-left text-xs text-gray-500">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {(historyQ.data?.attacks || []).length === 0 ? (
                <tr>
                  <td colSpan={9} className="px-3 py-8 text-center text-gray-600">
                    No attacks launched yet. Use the buttons above to inject a fraud attack.
                  </td>
                </tr>
              ) : (historyQ.data?.attacks || []).map(a => (
                <tr key={a.attack_id} className="border-b border-gray-800/50 hover:bg-gray-800/20">
                  <td className="px-3 py-2 font-mono text-xs text-gray-400">{shortId(a.attack_id)}</td>
                  <td className="px-3 py-2 text-white">{a.attack_type.replace(/_/g, ' ')}</td>
                  <td className="px-3 py-2">
                    <span className={`text-xs px-2 py-0.5 rounded ${
                      a.intensity === 'high' ? 'bg-red-900/40 text-red-300' :
                      a.intensity === 'medium' ? 'bg-yellow-900/40 text-yellow-300' :
                      'bg-green-900/40 text-green-300'
                    }`}>{a.intensity}</span>
                  </td>
                  <td className="px-3 py-2 text-gray-300">{a.transactions_injected}</td>
                  <td className="px-3 py-2 text-gray-300">{a.detected_count}</td>
                  <td className="px-3 py-2">
                    <span className={a.detection_rate >= 0.7 ? 'text-green-400' : 'text-yellow-400'}>
                      {formatPct(a.detection_rate)}
                    </span>
                  </td>
                  <td className="px-3 py-2 text-blue-400">{a.rings_identified}</td>
                  <td className="px-3 py-2 text-gray-400">{formatMs(a.avg_detection_latency_ms)}</td>
                  <td className="px-3 py-2 text-gray-500 text-xs">{a.created_at?.slice(0, 16) || '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
