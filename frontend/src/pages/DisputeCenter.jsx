import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { listDisputes, autoDefendDispute } from '../api'
import { formatINR, formatPct, shortId, riskBadgeClass, actionBadgeClass } from '../utils'
import { FileText, Shield, AlertTriangle, CheckCircle, ExternalLink, RefreshCw } from 'lucide-react'

function WinProbBar({ prob }) {
  if (prob == null) return <span className="text-gray-600">—</span>
  const pct = Math.round(prob * 100)
  const color = prob >= 0.7 ? 'bg-green-500' : prob >= 0.4 ? 'bg-yellow-500' : 'bg-red-500'
  return (
    <div className="flex items-center gap-2">
      <div className="flex-1 h-1.5 bg-gray-800 rounded-full overflow-hidden">
        <div className={`h-full ${color} rounded-full`} style={{ width: `${pct}%` }} />
      </div>
      <span className={`text-xs tabular-nums ${prob >= 0.7 ? 'text-green-400' : prob >= 0.4 ? 'text-yellow-400' : 'text-red-400'}`}>
        {pct}%
      </span>
    </div>
  )
}

function EvidenceBar({ completeness }) {
  if (completeness == null) return <span className="text-gray-600">—</span>
  const pct = Math.round(completeness * 100)
  return (
    <div className="flex items-center gap-2">
      <div className="flex-1 h-1.5 bg-gray-800 rounded-full overflow-hidden">
        <div className="h-full bg-blue-500 rounded-full" style={{ width: `${pct}%` }} />
      </div>
      <span className="text-xs text-blue-400">{pct}%</span>
    </div>
  )
}

function DefenseModal({ dispute, onClose, onDefend }) {
  const [defending, setDefending] = useState(false)
  const [result, setResult] = useState(null)

  const handleDefend = async () => {
    setDefending(true)
    try {
      const r = await onDefend(dispute)
      setResult(r)
    } catch (err) {
      alert(err.response?.data?.detail || 'Defense failed')
    } finally {
      setDefending(false)
    }
  }

  return (
    <div className="fixed inset-0 bg-black/70 flex items-center justify-center z-50 p-4">
      <div className="bg-gray-900 border border-gray-700 rounded-2xl w-full max-w-2xl max-h-[90vh] overflow-y-auto">
        <div className="px-6 py-4 border-b border-gray-800 flex items-center justify-between">
          <h3 className="font-semibold text-white flex items-center gap-2">
            <Shield size={16} className="text-blue-400" />
            Dispute Defense — {shortId(dispute.id)}
          </h3>
          <button onClick={onClose} className="text-gray-500 hover:text-gray-300 text-xl leading-none">×</button>
        </div>
        <div className="p-6 space-y-4">
          {/* Dispute info */}
          <div className="grid grid-cols-2 gap-3 text-sm">
            {[
              ['Dispute ID', shortId(dispute.id)],
              ['Transaction ID', shortId(dispute.transaction_id)],
              ['Amount', formatINR(dispute.amount)],
              ['Reason Code', dispute.reason_code],
              ['Card Network', dispute.card_network || '—'],
              ['Status', dispute.status],
            ].map(([k, v]) => (
              <div key={k} className="bg-gray-800/50 rounded-lg p-3">
                <div className="text-xs text-gray-500 mb-1">{k}</div>
                <div className="text-white font-medium">{v}</div>
              </div>
            ))}
          </div>

          {result ? (
            <div className="space-y-3">
              <div className={`border rounded-xl p-4 ${
                result.win_probability >= 0.7 ? 'bg-green-900/20 border-green-700' :
                result.win_probability >= 0.4 ? 'bg-yellow-900/20 border-yellow-700' :
                'bg-red-900/20 border-red-700'
              }`}>
                <div className="flex items-center gap-2 mb-2">
                  {result.win_probability >= 0.7
                    ? <CheckCircle size={16} className="text-green-400" />
                    : <AlertTriangle size={16} className="text-yellow-400" />}
                  <span className="font-semibold text-white">
                    Recommended: {result.recommended_action.replace(/_/g, ' ').toUpperCase()}
                  </span>
                </div>
                <div className="grid grid-cols-3 gap-2 text-sm mt-3">
                  <div className="text-center">
                    <div className="text-xl font-bold text-white">{formatPct(result.win_probability)}</div>
                    <div className="text-xs text-gray-500">Win Probability</div>
                  </div>
                  <div className="text-center">
                    <div className="text-xl font-bold text-blue-400">{formatPct(result.evidence_completeness)}</div>
                    <div className="text-xs text-gray-500">Evidence Complete</div>
                  </div>
                  <div className="text-center">
                    <div className="text-xl font-bold text-green-400">
                      {formatINR(result.cost_benefit?.expected_value)}
                    </div>
                    <div className="text-xs text-gray-500">Expected Value</div>
                  </div>
                </div>
              </div>
              {result.evidence_pdf_url && (
                <a
                  href={result.evidence_pdf_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="flex items-center gap-2 text-blue-400 hover:text-blue-300 text-sm bg-blue-900/20 border border-blue-800/50 rounded-lg px-4 py-3 transition-colors"
                >
                  <FileText size={16} />
                  Download Evidence PDF
                  <ExternalLink size={12} />
                </a>
              )}
              {result.defense_strategy && (
                <div className="bg-gray-800 rounded-xl p-4 text-sm space-y-2">
                  <div className="font-semibold text-white">Strategy</div>
                  <div className="text-gray-400"><strong className="text-gray-300">Primary:</strong> {result.defense_strategy.primary}</div>
                  {result.defense_strategy.selected_evidence?.length > 0 && (
                    <div>
                      <span className="text-gray-300 font-medium">Evidence selected: </span>
                      <span className="text-green-400">{result.defense_strategy.selected_evidence.join(', ')}</span>
                    </div>
                  )}
                  {result.defense_strategy.missing_evidence?.length > 0 && (
                    <div>
                      <span className="text-gray-300 font-medium">Missing: </span>
                      <span className="text-red-400">{result.defense_strategy.missing_evidence.join(', ')}</span>
                    </div>
                  )}
                </div>
              )}
            </div>
          ) : (
            <button
              onClick={handleDefend}
              disabled={defending}
              className="w-full py-3 bg-blue-600 hover:bg-blue-700 disabled:bg-gray-700 text-white rounded-xl font-semibold transition-colors flex items-center justify-center gap-2"
            >
              {defending ? (
                <><RefreshCw size={16} className="animate-spin" /> Running Defense Pipeline...</>
              ) : (
                <><Shield size={16} /> Auto-Generate Defense</>
              )}
            </button>
          )}
        </div>
      </div>
    </div>
  )
}

export default function DisputeCenter() {
  const [selected, setSelected] = useState(null)
  const qc = useQueryClient()
  const disputesQ = useQuery({ queryKey: ['disputes'], queryFn: listDisputes, refetchInterval: 20000 })
  const disputes = disputesQ.data?.disputes || []

  const handleDefend = async (dispute) => {
    const result = await autoDefendDispute({
      dispute_id: dispute.id,
      transaction_id: dispute.transaction_id,
      reason_code: dispute.reason_code,
      card_network: dispute.card_network || 'Visa',
      amount: dispute.amount,
    })
    qc.invalidateQueries(['disputes'])
    return result
  }

  const open = disputes.filter(d => ['open', 'under_review', 'action_required'].includes(d.status))
  const closed = disputes.filter(d => ['won', 'lost', 'closed'].includes(d.status))

  return (
    <div className="p-6 space-y-6">
      {selected && (
        <DefenseModal
          dispute={selected}
          onClose={() => setSelected(null)}
          onDefend={handleDefend}
        />
      )}

      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white flex items-center gap-2">
            <FileText className="text-blue-400" size={24} />
            Dispute Defense Center
          </h1>
          <p className="text-gray-500 text-sm mt-1">
            Autonomous chargeback representment with AI-generated evidence packets
          </p>
        </div>
        <div className="flex gap-3 text-sm">
          <div className="bg-gray-900 border border-gray-800 rounded-lg px-4 py-2 text-center">
            <div className="text-xl font-bold text-yellow-400">{open.length}</div>
            <div className="text-xs text-gray-500">Active</div>
          </div>
          <div className="bg-gray-900 border border-gray-800 rounded-lg px-4 py-2 text-center">
            <div className="text-xl font-bold text-green-400">{closed.filter(d => d.status === 'won').length}</div>
            <div className="text-xs text-gray-500">Won</div>
          </div>
          <div className="bg-gray-900 border border-gray-800 rounded-lg px-4 py-2 text-center">
            <div className="text-xl font-bold text-red-400">{closed.filter(d => d.status === 'lost').length}</div>
            <div className="text-xs text-gray-500">Lost</div>
          </div>
        </div>
      </div>

      {/* Active disputes */}
      <DisputeTable
        title="Active Disputes"
        disputes={open}
        loading={disputesQ.isLoading}
        onDefend={setSelected}
        showDefend
      />

      {/* Closed disputes */}
      {closed.length > 0 && (
        <DisputeTable
          title="Resolved Disputes"
          disputes={closed}
          loading={false}
          onDefend={setSelected}
          showDefend={false}
        />
      )}
    </div>
  )
}

function DisputeTable({ title, disputes, loading, onDefend, showDefend }) {
  return (
    <div className="bg-gray-900 border border-gray-800 rounded-xl overflow-hidden">
      <div className="px-4 py-3 border-b border-gray-800">
        <h2 className="font-semibold text-white text-sm">{title} ({disputes.length})</h2>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-gray-800">
              {['Dispute ID', 'Transaction', 'Amount', 'Reason', 'Network', 'Status', 'Win Prob', 'Evidence', 'Action'].map(h => (
                <th key={h} className="px-3 py-2 text-left text-xs text-gray-500">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr><td colSpan={9} className="px-3 py-8 text-center text-gray-600">Loading disputes...</td></tr>
            ) : disputes.length === 0 ? (
              <tr>
                <td colSpan={9} className="px-3 py-8 text-center text-gray-600">
                  No disputes yet. Generate data with fraud injection to create disputes.
                </td>
              </tr>
            ) : disputes.map(d => (
              <tr key={d.id} className="border-b border-gray-800/50 hover:bg-gray-800/20">
                <td className="px-3 py-2 font-mono text-xs text-gray-400">{shortId(d.id)}</td>
                <td className="px-3 py-2 font-mono text-xs text-gray-500">{shortId(d.transaction_id)}</td>
                <td className="px-3 py-2 text-white font-medium">{formatINR(d.amount)}</td>
                <td className="px-3 py-2">
                  <span className="text-xs bg-gray-800 px-2 py-0.5 rounded text-gray-300">{d.reason_code}</span>
                </td>
                <td className="px-3 py-2 text-gray-400 text-xs">{d.card_network || '—'}</td>
                <td className="px-3 py-2">
                  <span className={`text-xs px-2 py-0.5 rounded ${
                    d.status === 'won' ? 'bg-green-900/40 text-green-300' :
                    d.status === 'lost' ? 'bg-red-900/40 text-red-300' :
                    d.status === 'under_review' ? 'bg-blue-900/40 text-blue-300' :
                    'bg-gray-700 text-gray-300'
                  }`}>{d.status.replace(/_/g, ' ')}</span>
                </td>
                <td className="px-3 py-2 min-w-[100px]"><WinProbBar prob={d.win_probability} /></td>
                <td className="px-3 py-2 min-w-[100px]"><EvidenceBar completeness={d.evidence_completeness} /></td>
                <td className="px-3 py-2">
                  <div className="flex gap-2">
                    {showDefend && (
                      <button
                        onClick={() => onDefend(d)}
                        className="text-xs px-2 py-1 bg-blue-600/20 border border-blue-700/50 text-blue-400 hover:bg-blue-600/30 rounded transition-colors"
                      >
                        Defend
                      </button>
                    )}
                    {d.evidence_pdf_url && (
                      <a
                        href={d.evidence_pdf_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-xs px-2 py-1 bg-gray-700 text-gray-300 hover:bg-gray-600 rounded transition-colors flex items-center gap-1"
                      >
                        PDF <ExternalLink size={10} />
                      </a>
                    )}
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
