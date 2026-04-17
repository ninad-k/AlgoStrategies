import axios from 'axios'

const BASE = import.meta.env.VITE_API_BASE || 'http://localhost:8000/api/v1'

export async function login(email, password) {
  const res = await axios.post(`${BASE}/auth/login`, { email, password }, { withCredentials: true })
  return res.data.access_token
}

export async function logout() {
  await axios.post(`${BASE}/auth/logout`, {}, { withCredentials: true })
}
