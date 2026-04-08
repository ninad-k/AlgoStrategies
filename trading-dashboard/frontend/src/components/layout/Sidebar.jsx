import { NavLink } from 'react-router-dom'
import { useAuth } from '../../store/AuthContext'

const NAV = [
  { to: '/dashboard', label: 'Dashboard', icon: '◆' },
  { to: '/symbols', label: 'P&L by Symbol', icon: '◎' },
  { to: '/upload', label: 'Upload', icon: '⬆' },
  { to: '/config', label: 'Config', icon: '⚙' },
]

export default function Sidebar() {
  const { user, logout } = useAuth()

  return (
    <aside className="w-56 min-h-screen bg-navy-800 flex flex-col">
      {/* Logo */}
      <div className="px-5 py-5 border-b border-navy-700">
        <div className="text-teal-400 font-bold text-base tracking-wide">◆ TRADING DASH</div>
        <div className="text-gray-400 text-xs mt-0.5">REY CAPITAL</div>
      </div>

      {/* Nav */}
      <nav className="flex-1 px-3 py-4 space-y-1">
        {NAV.map(({ to, label, icon }) => (
          <NavLink
            key={to}
            to={to}
            className={({ isActive }) =>
              `flex items-center gap-2.5 px-3 py-2 rounded text-sm transition-colors ${
                isActive
                  ? 'bg-teal-500 text-white font-medium'
                  : 'text-gray-300 hover:bg-navy-700 hover:text-white'
              }`
            }
          >
            <span className="text-xs">{icon}</span>
            {label}
          </NavLink>
        ))}
      </nav>

      {/* User */}
      <div className="px-5 py-4 border-t border-navy-700">
        <div className="text-gray-300 text-xs truncate">{user?.email}</div>
        <div className="text-gray-500 text-xs capitalize">{user?.role?.replace('_', ' ')}</div>
        <button
          onClick={logout}
          className="mt-2 text-xs text-gray-400 hover:text-red-400 transition-colors"
        >
          Sign out
        </button>
      </div>
    </aside>
  )
}
