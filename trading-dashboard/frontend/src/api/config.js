import client from './client'

// Traders
export const getTraders = () => client.get('/traders').then(r => r.data)
export const createTrader = (body) => client.post('/traders', body).then(r => r.data)
export const updateTrader = (id, body) => client.put(`/traders/${id}`, body).then(r => r.data)
export const deleteTrader = (id) => client.delete(`/traders/${id}`)

// Strategies
export const getStrategies = () => client.get('/strategies').then(r => r.data)
export const createStrategy = (body) => client.post('/strategies', body).then(r => r.data)
export const updateStrategy = (id, body) => client.put(`/strategies/${id}`, body).then(r => r.data)
export const deleteStrategy = (id) => client.delete(`/strategies/${id}`)

// Accounts
export const getAccounts = () => client.get('/accounts').then(r => r.data)
export const createAccount = (body) => client.post('/accounts', body).then(r => r.data)

// Attribution rules
export const getRules = () => client.get('/attribution-rules').then(r => r.data)
export const createRule = (body) => client.post('/attribution-rules', body).then(r => r.data)
export const updateRule = (id, body) => client.put(`/attribution-rules/${id}`, body).then(r => r.data)
export const deleteRule = (id) => client.delete(`/attribution-rules/${id}`)
