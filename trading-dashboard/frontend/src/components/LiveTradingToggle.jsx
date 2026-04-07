import { useState, useEffect, useCallback } from 'react'
import { useAuth } from '../store/AuthContext'
import { getLiveTradingStatus, setLiveTradingEnabled } from '../api/execution'

const ADMIN_ROLES = ['super_admin', 'admin']

export default function LiveTradingToggle() {
  const { user } = useAuth()
  const [enabled, setEnabled] = useState(false)
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState(false)

  const canManage = user && ADMIN_ROLES.includes(user.role)

  const load = useCallback(async () => {
    if (!canManage) return
    setLoading(true)
    try {
      const d = await getLiveTradingStatus()
      setEnabled(!!d.live_trading_enabled)
    } catch {
      setEnabled(false)
    } finally {
      setLoading(false)
    }
  }, [canManage])

  useEffect(() => {
    load()
  }, [load])

  async function toggle() {
    if (!canManage || busy) return
    setBusy(true)
    try {
      const d = await setLiveTradingEnabled(!enabled)
      setEnabled(!!d.live_trading_enabled)
    } catch {
      // keep prior state; optional toast could go here
    } finally {
      setBusy(false)
    }
  }

  if (!canManage) return null

  return (
    <button
      type="button"
      onClick={toggle}
      disabled={loading || busy}
      className={`px-4 py-2 rounded-lg text-sm font-medium border transition-colors shrink-0 ${
        enabled
          ? 'bg-emerald-600 text-white border-emerald-700 hover:bg-emerald-700'
          : 'bg-gray-100 text-gray-700 border-gray-300 hover:bg-gray-200'
      }`}
      title="When ON (green), MT5 EAs that use dashboard execution will send real orders. When OFF, they only raise terminal alerts."
    >
      {loading ? 'Live trading…' : busy ? 'Saving…' : enabled ? 'Live trading ON' : 'Live trading OFF'}
    </button>
  )
}
