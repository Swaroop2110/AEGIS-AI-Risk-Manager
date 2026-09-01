import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { generateData, getDataStats, trainModel, scoreBatch } from '../api'
import { Database, CheckCircle, AlertTriangle, RefreshCw, Cpu, Zap } from 'lucide-react'
import { formatINR } from '../utils'

function StatCard({ label, value, color = 'text-white' }) {
  return (
    <div className="bg-gray-900 border border-gray-800 rounded-xl p-4 text-center">
      <div className={`text-2xl font-bold ${color}`}>{(value || 0).toLocaleString()}</div>
      <div className="text-xs text-gray-500 mt-1">{label}</div>
    </div>
  )
}

export default function DataManager() {
  const [config, setConfig] = useState({
    num_customers: 1000,
    num_merchants: 100,
    num_transactions: 10000,
    fraud_rate: 0.02,
    seed: 42,
  })
  const [genResult, setGenResult] = useState(null)
  const [trainResult, setTrainResult] = useState(null)
  const [scoreResult, setScoreResult] = useState(null)

  const qc = useQueryClient()
  const statsQ = useQuery({ queryKey: ['data-stats'], queryFn: getDataStats, refetchInterval: 30000 })
  const stats = statsQ.data || {}

  const genMutation = useMutation({
    mutationFn: generateData,
    onSuccess: (data) => {
      setGenResult(data)
      qc.invalidateQueries(['data-stats'])
      qc.invalidateQueries(['stats'])
    },
  })

  const trainMutation = useMutation({
    mutationFn: trainModel,
    onSuccess: (data) => setTrainResult(data),
  })

  const scoreMutation = useMutation({
    mutationFn: () => scoreBatch(500),
    onSuccess: (data) => {
      setScoreResult(data)
      qc.invalidateQueries(['stats'])
      qc.invalidateQueries(['recent-txns'])
    },
  })

  const fraudCount = Math.round(config.num_transactions * config.fraud_rate)
  const legitCount = config.num_transactions - fraudCount

  return (
    <div className="p-6 space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-white flex items-center gap-2">
          <Database className="text-blue-400" size={24} />
          Data Manager
        </h1>
        <p className="text-gray-500 text-sm mt-1">
          Generate synthetic Indian payment data with realistic fraud patterns
        </p>
      </div>

      {/* Current DB stats */}
      <div>
        <h2 className="text-sm font-semibold text-gray-400 uppercase mb-3">Current Database</h2>
        <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
          <StatCard label="Customers" value={stats.customers} color="text-blue-400" />
          <StatCard label="Merchants" value={stats.merchants} color="text-indigo-400" />
          <StatCard label="Transactions" value={stats.transactions} color="text-white" />
          <StatCard label="Fraud Txns" value={stats.fraud_transactions} color="text-red-400" />
          <StatCard label="Disputes" value={stats.disputes} color="text-yellow-400" />
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Data Generation Config */}
        <div className="bg-gray-900 border border-gray-800 rounded-xl p-6 space-y-4">
          <h2 className="font-semibold text-white flex items-center gap-2">
            <Database size={16} className="text-blue-400" />
            Generate Synthetic Dataset
          </h2>

          <div className="space-y-3">
            {[
              { key: 'num_customers', label: 'Customers', min: 10, max: 50000, step: 100 },
              { key: 'num_merchants', label: 'Merchants', min: 5, max: 5000, step: 10 },
              { key: 'num_transactions', label: 'Transactions', min: 100, max: 500000, step: 1000 },
            ].map(({ key, label, min, max, step }) => (
              <div key={key}>
                <label className="flex justify-between text-sm text-gray-400 mb-1">
                  <span>{label}</span>
                  <span className="text-white font-medium">{config[key].toLocaleString()}</span>
                </label>
                <input
                  type="range"
                  min={min}
                  max={max}
                  step={step}
                  value={config[key]}
                  onChange={e => setConfig(prev => ({ ...prev, [key]: +e.target.value }))}
                  className="w-full accent-blue-500"
                />
              </div>
            ))}

            <div>
              <label className="flex justify-between text-sm text-gray-400 mb-1">
                <span>Fraud Rate</span>
                <span className="text-red-400 font-medium">{(config.fraud_rate * 100).toFixed(1)}%</span>
              </label>
              <input
                type="range"
                min={0.01}
                max={0.15}
                step={0.005}
                value={config.fraud_rate}
                onChange={e => setConfig(prev => ({ ...prev, fraud_rate: +e.target.value }))}
                className="w-full accent-red-500"
              />
            </div>

            {/* Preview breakdown */}
            <div className="bg-gray-800 rounded-lg p-3 text-sm space-y-1">
              <div className="flex justify-between text-gray-400">
                <span>Legitimate transactions</span>
                <span className="text-green-400 font-medium">{legitCount.toLocaleString()}</span>
              </div>
              <div className="flex justify-between text-gray-400">
                <span>Fraud transactions (5 vectors)</span>
                <span className="text-red-400 font-medium">{fraudCount.toLocaleString()}</span>
              </div>
              <div className="flex justify-between text-gray-400 border-t border-gray-700 pt-1 mt-1">
                <span>Total</span>
                <span className="text-white font-medium">{config.num_transactions.toLocaleString()}</span>
              </div>
            </div>
          </div>

          <div className="flex items-center gap-3 pt-1 text-sm text-gray-500">
            <span>Seed:</span>
            <input
              type="number"
              value={config.seed}
              onChange={e => setConfig(prev => ({ ...prev, seed: +e.target.value }))}
              className="w-20 bg-gray-800 border border-gray-700 rounded px-2 py-1 text-white text-sm"
            />
          </div>

          <button
            onClick={() => { setGenResult(null); genMutation.mutate(config) }}
            disabled={genMutation.isPending}
            className="w-full py-3 bg-blue-600 hover:bg-blue-700 disabled:bg-gray-700 text-white rounded-xl font-semibold transition-colors flex items-center justify-center gap-2"
          >
            {genMutation.isPending ? (
              <><RefreshCw size={16} className="animate-spin" /> Generating... (this may take 1-2 minutes)</>
            ) : (
              <><Database size={16} /> Generate Dataset</>
            )}
          </button>

          {genMutation.isError && (
            <div className="text-red-400 text-sm bg-red-900/20 border border-red-800 rounded-lg px-3 py-2">
              {genMutation.error?.response?.data?.detail || 'Generation failed'}
            </div>
          )}

          {genResult && (
            <div className="bg-green-900/20 border border-green-700/50 rounded-xl p-4 space-y-2">
              <div className="flex items-center gap-2 text-green-400 font-semibold">
                <CheckCircle size={16} />
                Dataset Generated!
              </div>
              <div className="grid grid-cols-2 gap-2 text-sm">
                {[
                  ['Customers', genResult.customers_generated],
                  ['Merchants', genResult.merchants_generated],
                  ['Transactions', genResult.transactions_generated],
                  ['Fraud txns', genResult.fraud_transactions],
                  ['Graph nodes', genResult.graph_nodes],
                  ['Graph edges', genResult.graph_edges],
                ].map(([k, v]) => (
                  <div key={k} className="flex justify-between text-gray-400">
                    <span>{k}:</span>
                    <span className="text-white font-medium">{(v || 0).toLocaleString()}</span>
                  </div>
                ))}
              </div>
              <p className="text-xs text-gray-500 mt-1">{genResult.message}</p>
              <div className="pt-2 border-t border-green-800/50">
                <p className="text-xs text-yellow-400 mb-2">Next step: Score the transactions to see them in the War Room</p>
                <button
                  onClick={() => { setScoreResult(null); scoreMutation.mutate() }}
                  disabled={scoreMutation.isPending}
                  className="w-full py-2 bg-yellow-700/50 hover:bg-yellow-700 border border-yellow-600/50 disabled:bg-gray-700 text-white rounded-lg text-sm font-semibold transition-colors flex items-center justify-center gap-2"
                >
                  {scoreMutation.isPending ? (
                    <><RefreshCw size={14} className="animate-spin" /> Scoring transactions...</>
                  ) : (
                    <><Zap size={14} /> Score Transactions (up to 500)</>
                  )}
                </button>
                {scoreResult && (
                  <div className="mt-2 text-xs text-green-400">
                    Scored {scoreResult.scored} transactions ({scoreResult.errors} errors). Check War Room!
                  </div>
                )}
              </div>
            </div>
          )}
        </div>

        {/* Model Training */}
        <div className="bg-gray-900 border border-gray-800 rounded-xl p-6 space-y-4">
          <h2 className="font-semibold text-white flex items-center gap-2">
            <Cpu size={16} className="text-purple-400" />
            Train L1 LightGBM Model
          </h2>
          <p className="text-sm text-gray-400">
            Train the LightGBM baseline on generated labelled data. Before training, a
            deterministic sigmoid fallback is used. Training improves fraud classification
            accuracy using the features: velocity, z-score, device, geo mismatch, IP reputation.
          </p>

          <div className="bg-gray-800 rounded-lg p-3 text-xs space-y-1 text-gray-400">
            <div className="font-semibold text-gray-300 mb-2">Features used:</div>
            {['amount_log', 'hour', 'account_age_days', 'txn_velocity_1h', 'txn_velocity_24h',
              'is_new_device', 'amount_zscore', 'ip_fraud_rate', 'geo_mismatch'].map(f => (
              <div key={f} className="flex items-center gap-2">
                <span className="w-1.5 h-1.5 rounded-full bg-blue-500" />
                <span className="font-mono">{f}</span>
              </div>
            ))}
          </div>

          <button
            onClick={() => { setTrainResult(null); trainMutation.mutate() }}
            disabled={trainMutation.isPending}
            className="w-full py-3 bg-purple-700 hover:bg-purple-600 disabled:bg-gray-700 text-white rounded-xl font-semibold transition-colors flex items-center justify-center gap-2"
          >
            {trainMutation.isPending ? (
              <><RefreshCw size={16} className="animate-spin" /> Training model...</>
            ) : (
              <><Cpu size={16} /> Train LightGBM Model</>
            )}
          </button>

          {trainMutation.isError && (
            <div className="text-red-400 text-sm bg-red-900/20 border border-red-800 rounded-lg px-3 py-2">
              {trainMutation.error?.response?.data?.detail || 'Training failed — generate data first'}
            </div>
          )}

          {trainResult && (
            <div className="bg-purple-900/20 border border-purple-700/50 rounded-xl p-4 space-y-3">
              <div className="flex items-center gap-2 text-purple-400 font-semibold">
                <CheckCircle size={16} />
                Model Trained!
              </div>
              <div className="grid grid-cols-2 gap-2 text-sm">
                {[
                  ['Training rows', trainResult.training_rows?.toLocaleString()],
                  ['Test rows', trainResult.test_rows?.toLocaleString()],
                  ['Precision', (trainResult.precision * 100).toFixed(1) + '%'],
                  ['Recall', (trainResult.recall * 100).toFixed(1) + '%'],
                  ['F1 Score', (trainResult.f1 * 100).toFixed(1) + '%'],
                  ['AUC-ROC', trainResult.auc_roc?.toFixed(4)],
                ].map(([k, v]) => (
                  <div key={k} className="flex justify-between text-gray-400">
                    <span>{k}:</span>
                    <span className="text-white font-medium">{v}</span>
                  </div>
                ))}
              </div>
              <p className="text-xs text-gray-500">Model saved to data/models/l1_lightgbm.txt</p>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
