import client from './client'

const qs = (params) => {
  const p = Object.fromEntries(Object.entries(params).filter(([, v]) => v != null))
  return new URLSearchParams(p).toString()
}

export const getPnlSummary = (params = {}) => client.get(`/pnl/summary?${qs(params)}`).then(r => r.data)
export const getPnlByTrader = (params = {}) => client.get(`/pnl/by-trader?${qs(params)}`).then(r => r.data)
export const getPnlByStrategy = (params = {}) => client.get(`/pnl/by-strategy?${qs(params)}`).then(r => r.data)
export const getPnlBySymbol = (params = {}) => client.get(`/pnl/by-symbol?${qs(params)}`).then(r => r.data)
export const getPnlByAccount = (params = {}) => client.get(`/pnl/by-account?${qs(params)}`).then(r => r.data)
export const getTraderTrades = (id, params = {}) => client.get(`/pnl/traders/${id}/trades?${qs(params)}`).then(r => r.data)
export const getStrategyTrades = (id, params = {}) => client.get(`/pnl/strategies/${id}/trades?${qs(params)}`).then(r => r.data)
export const getTraderRisk = (id, params = {}) => client.get(`/pnl/traders/${id}/risk?${qs(params)}`).then(r => r.data)
export const getStrategyRisk = (id, params = {}) => client.get(`/pnl/strategies/${id}/risk?${qs(params)}`).then(r => r.data)
