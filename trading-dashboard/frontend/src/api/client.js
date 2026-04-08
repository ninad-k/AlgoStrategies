import axios from 'axios'

const client = axios.create({
  baseURL: import.meta.env.VITE_API_BASE || 'http://localhost:8000/api/v1',
  withCredentials: true, // send HttpOnly refresh cookie
})

// Attach access token from memory on every request
client.interceptors.request.use((config) => {
  const token = window.__accessToken
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

// On 401, try silent refresh once then redirect to login
let isRefreshing = false
let failedQueue = []

const processQueue = (error) => {
  failedQueue.forEach((prom) => (error ? prom.reject(error) : prom.resolve()))
  failedQueue = []
}

client.interceptors.response.use(
  (res) => res,
  async (error) => {
    const original = error.config
    if (error.response?.status === 401 && !original._retry) {
      if (isRefreshing) {
        return new Promise((resolve, reject) => {
          failedQueue.push({ resolve, reject })
        }).then(() => client(original))
      }
      original._retry = true
      isRefreshing = true
      try {
        const res = await axios.post(
          `${import.meta.env.VITE_API_BASE || 'http://localhost:8000/api/v1'}/auth/refresh`,
          {},
          { withCredentials: true }
        )
        window.__accessToken = res.data.access_token
        processQueue(null)
        return client(original)
      } catch (refreshError) {
        window.__accessToken = null
        processQueue(refreshError)
        window.location.href = '/login'
        return Promise.reject(refreshError)
      } finally {
        isRefreshing = false
      }
    }
    return Promise.reject(error)
  }
)

export default client
