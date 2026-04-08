import client from './client'

export async function uploadTrades(file, accountId) {
  const form = new FormData()
  form.append('file', file)
  form.append('account_id', accountId)
  const res = await client.post('/upload/trades', form, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
  return res.data
}
