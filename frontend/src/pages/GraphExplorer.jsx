import { useState, useEffect, useRef } from 'react'
import { useQuery } from '@tanstack/react-query'
import { getFraudRings, getEntitySubgraph } from '../api'
import { formatINR, shortId } from '../utils'
import { Share2, Users, Smartphone, Globe, CreditCard, AlertTriangle } from 'lucide-react'
import CytoscapeComponent from 'react-cytoscapejs'

const NODE_COLORS = {
  user: '#3b82f6',
  device: '#10b981',
  ip: '#f59e0b',
  card: '#a855f7',
  merchant: '#6b7280',
  vpa: '#ec4899',
}

function RingCard({ ring, onSelect, selected }) {
  return (
    <div
      onClick={() => onSelect(ring)}
      className={`cursor-pointer border rounded-xl p-4 transition-all ${
        selected?.ring_id === ring.ring_id
          ? 'border-red-500 bg-red-900/20'
          : 'border-gray-800 bg-gray-900 hover:border-gray-600'
      }`}
    >
      <div className="flex items-start justify-between mb-2">
        <span className="text-xs font-mono text-red-400 ring-pulse">⬤ RING</span>
        <span className="text-xs text-gray-500">{ring.transaction_count} txns</span>
      </div>
      <div className="text-sm font-mono text-gray-400 mb-2">{ring.ring_id.slice(-12)}</div>
      <div className="grid grid-cols-2 gap-1 text-xs text-gray-500">
        <span><Users size={10} className="inline mr-1" />{ring.unique_customers} customers</span>
        <span><Smartphone size={10} className="inline mr-1" />{ring.unique_devices} devices</span>
        <span><Globe size={10} className="inline mr-1" />{ring.unique_ips} IPs</span>
        <span><CreditCard size={10} className="inline mr-1" />{formatINR(ring.total_amount)}</span>
      </div>
    </div>
  )
}

export default function GraphExplorer() {
  const ringsQ = useQuery({ queryKey: ['rings'], queryFn: getFraudRings })
  const [selected, setSelected] = useState(null)
  const [cyElements, setCyElements] = useState([])
  const cyRef = useRef(null)

  const rings = ringsQ.data?.rings || []

  // Build cytoscape elements from ring transactions
  useEffect(() => {
    if (!selected) return
    const nodes = new Map()
    const edges = []

    const addNode = (id, type, label) => {
      if (!nodes.has(id)) {
        nodes.set(id, {
          data: {
            id,
            label: label || id.slice(-8),
            type,
            color: NODE_COLORS[type] || '#6b7280',
          },
        })
      }
    }

    selected.transactions.forEach(txn => {
      const userId = `user_${txn.customer_id.slice(-6)}`
      const merchantId = `merch_${txn.customer_id.slice(-4)}`
      addNode(userId, 'user', `User\n${txn.customer_id.slice(-4)}`)
      if (txn.device_id) {
        const devId = `dev_${txn.device_id.slice(-6)}`
        addNode(devId, 'device', `Device\n${txn.device_id.slice(-4)}`)
        edges.push({ data: { id: `${userId}-${devId}`, source: userId, target: devId, type: 'USED_DEVICE' } })
      }
      if (txn.ip_address) {
        const ipId = `ip_${txn.ip_address.split('.').slice(0, 3).join('.')}`
        addNode(ipId, 'ip', `IP\n${txn.ip_address.split('.').slice(0, 2).join('.')}.*`)
        edges.push({ data: { id: `${userId}-${ipId}-${txn.id}`, source: userId, target: ipId, type: 'FROM_IP' } })
      }
    })

    setCyElements([...Array.from(nodes.values()), ...edges])
  }, [selected])

  const layout = { name: 'cose', animate: true, randomize: false, nodeRepulsion: 4500, idealEdgeLength: 80 }

  const stylesheet = [
    {
      selector: 'node',
      style: {
        'background-color': 'data(color)',
        'label': 'data(label)',
        'color': '#fff',
        'font-size': 9,
        'text-wrap': 'wrap',
        'text-valign': 'center',
        'text-halign': 'center',
        width: 36,
        height: 36,
        'border-width': 2,
        'border-color': '#1f2937',
      },
    },
    {
      selector: 'edge',
      style: {
        'line-color': '#374151',
        'target-arrow-color': '#374151',
        'target-arrow-shape': 'triangle',
        'curve-style': 'bezier',
        width: 1.5,
        opacity: 0.6,
      },
    },
    {
      selector: 'node[type="user"]',
      style: { shape: 'ellipse' },
    },
    {
      selector: 'node[type="device"]',
      style: { shape: 'rectangle' },
    },
    {
      selector: 'node[type="ip"]',
      style: { shape: 'diamond' },
    },
  ]

  return (
    <div className="p-6 space-y-4">
      <div>
        <h1 className="text-2xl font-bold text-white flex items-center gap-2">
          <Share2 className="text-blue-400" size={24} />
          Graph Ring Explorer
        </h1>
        <p className="text-gray-500 text-sm mt-1">
          Interactive visualization of detected fraud abuse rings
        </p>
      </div>

      {/* Legend */}
      <div className="flex flex-wrap gap-3 text-xs">
        {Object.entries(NODE_COLORS).map(([type, color]) => (
          <span key={type} className="flex items-center gap-1.5 text-gray-400">
            <span className="w-3 h-3 rounded-full inline-block" style={{ background: color }} />
            {type}
          </span>
        ))}
      </div>

      <div className="flex gap-4 h-[600px]">
        {/* Ring list */}
        <div className="w-72 shrink-0 overflow-y-auto space-y-3 pr-1">
          {rings.length === 0 ? (
            <div className="bg-gray-900 border border-gray-800 rounded-xl p-6 text-center text-gray-600">
              {ringsQ.isLoading ? 'Loading rings...' : 'No rings detected yet.\nScore transactions to populate ring data.'}
            </div>
          ) : rings.map(r => (
            <RingCard key={r.ring_id} ring={r} onSelect={setSelected} selected={selected} />
          ))}
        </div>

        {/* Graph canvas */}
        <div className="flex-1 bg-gray-900 border border-gray-800 rounded-xl overflow-hidden relative">
          {!selected ? (
            <div className="absolute inset-0 flex flex-col items-center justify-center text-center text-gray-600 p-8">
              <Share2 size={48} className="mb-4 opacity-30" />
              <p className="text-lg">Select a fraud ring from the left panel to explore its graph</p>
              <p className="text-sm mt-2">Nodes: users (●), devices (■), IPs (◆)</p>
            </div>
          ) : cyElements.length > 0 ? (
            <CytoscapeComponent
              cy={(cy) => { cyRef.current = cy }}
              elements={cyElements}
              style={{ width: '100%', height: '100%', background: '#111827' }}
              stylesheet={stylesheet}
              layout={layout}
            />
          ) : (
            <div className="absolute inset-0 flex items-center justify-center text-gray-600">
              Building graph...
            </div>
          )}

          {/* Selected ring info overlay */}
          {selected && (
            <div className="absolute top-3 right-3 bg-gray-900/90 border border-gray-700 rounded-lg p-3 text-xs max-w-[200px]">
              <div className="text-red-400 font-semibold mb-1">Active Ring</div>
              <div className="text-gray-300 font-mono">{selected.ring_id.slice(-12)}</div>
              <div className="mt-2 text-gray-500 space-y-1">
                <div>{selected.transaction_count} transactions</div>
                <div>{selected.unique_customers} customers</div>
                <div>{formatINR(selected.total_amount)} total</div>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Transaction detail for selected ring */}
      {selected && (
        <div className="bg-gray-900 border border-gray-800 rounded-xl overflow-hidden">
          <div className="px-4 py-3 border-b border-gray-800">
            <h3 className="text-sm font-semibold text-white flex items-center gap-2">
              <AlertTriangle size={14} className="text-red-400" />
              Ring Transactions ({selected.transaction_count})
            </h3>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-gray-800">
                  {['Tx ID', 'Amount', 'Method', 'Customer', 'Device', 'IP', 'Fraud Type', 'Time'].map(h => (
                    <th key={h} className="px-3 py-2 text-left text-xs text-gray-500">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {selected.transactions.slice(0, 20).map(t => (
                  <tr key={t.id} className="border-b border-gray-800/50 hover:bg-gray-800/20">
                    <td className="px-3 py-2 font-mono text-xs text-gray-400">{shortId(t.id)}</td>
                    <td className="px-3 py-2 text-white">{formatINR(t.amount)}</td>
                    <td className="px-3 py-2 text-gray-400">{t.payment_method}</td>
                    <td className="px-3 py-2 font-mono text-xs text-gray-500">{t.customer_id?.slice(-8)}</td>
                    <td className="px-3 py-2 font-mono text-xs text-gray-500">{t.device_id?.slice(-8) || '—'}</td>
                    <td className="px-3 py-2 font-mono text-xs text-gray-500">{t.ip_address || '—'}</td>
                    <td className="px-3 py-2">
                      <span className="text-xs px-2 py-0.5 rounded bg-red-900/40 text-red-300">
                        {t.fraud_type?.replace(/_/g, ' ') || '—'}
                      </span>
                    </td>
                    <td className="px-3 py-2 text-gray-500 text-xs">{t.created_at?.slice(0, 16) || '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  )
}
