import client from './client'

export async function getLiveTradingStatus() {
  const { data } = await client.get('/execution/live-trading')
  return data
}

export async function setLiveTradingEnabled(enabled) {
  const { data } = await client.put('/execution/live-trading', { live_trading_enabled: enabled })
  return data
}
