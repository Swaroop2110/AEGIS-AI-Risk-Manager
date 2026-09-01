import { BrowserRouter, Routes, Route, NavLink } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import {
  Shield, Activity, Share2, Zap, FileText, BarChart2, Database
} from 'lucide-react'
import WarRoom from './pages/WarRoom'
import GraphExplorer from './pages/GraphExplorer'
import AttackSimulator from './pages/AttackSimulator'
import DisputeCenter from './pages/DisputeCenter'
import MetricsDashboard from './pages/MetricsDashboard'
import DataManager from './pages/DataManager'

const qc = new QueryClient({ defaultOptions: { queries: { refetchInterval: 15000 } } })

const NAV = [
  { to: '/', icon: Activity, label: 'War Room' },
  { to: '/graph', icon: Share2, label: 'Graph Explorer' },
  { to: '/attack', icon: Zap, label: 'Attack Simulator' },
  { to: '/disputes', icon: FileText, label: 'Dispute Defense' },
  { to: '/metrics', icon: BarChart2, label: 'Metrics & ROI' },
  { to: '/data', icon: Database, label: 'Data Manager' },
]

function Sidebar() {
  return (
    <aside className="w-56 shrink-0 flex flex-col bg-[#111827] border-r border-gray-800 min-h-screen">
      {/* Logo */}
      <div className="px-4 py-5 border-b border-gray-800">
        <div className="flex items-center gap-2">
          <Shield className="text-blue-400" size={22} />
          <div>
            <div className="font-bold text-white text-sm leading-tight">AEGIS</div>
            <div className="text-gray-500 text-xs leading-tight">AI Risk Manager</div>
          </div>
        </div>
        <div className="mt-2 text-xs text-blue-400/70">Razorpay Buildathon 2026</div>
      </div>
      {/* Nav links */}
      <nav className="flex-1 px-2 py-3 space-y-1">
        {NAV.map(({ to, icon: Icon, label }) => (
          <NavLink
            key={to}
            to={to}
            end={to === '/'}
            className={({ isActive }) =>
              `flex items-center gap-3 px-3 py-2 rounded-lg text-sm transition-colors ${
                isActive
                  ? 'bg-blue-600/20 text-blue-400 border border-blue-600/30'
                  : 'text-gray-400 hover:bg-gray-800 hover:text-gray-200'
              }`
            }
          >
            <Icon size={16} />
            {label}
          </NavLink>
        ))}
      </nav>
      {/* Footer */}
      <div className="px-4 py-3 border-t border-gray-800 text-xs text-gray-600">
        Track 02 · AI Risk Manager
      </div>
    </aside>
  )
}

function Layout({ children }) {
  return (
    <div className="flex min-h-screen bg-[#0a0e1a]">
      <Sidebar />
      <main className="flex-1 overflow-auto">{children}</main>
    </div>
  )
}

export default function App() {
  return (
    <QueryClientProvider client={qc}>
      <BrowserRouter>
        <Layout>
          <Routes>
            <Route path="/" element={<WarRoom />} />
            <Route path="/graph" element={<GraphExplorer />} />
            <Route path="/attack" element={<AttackSimulator />} />
            <Route path="/disputes" element={<DisputeCenter />} />
            <Route path="/metrics" element={<MetricsDashboard />} />
            <Route path="/data" element={<DataManager />} />
          </Routes>
        </Layout>
      </BrowserRouter>
    </QueryClientProvider>
  )
}
