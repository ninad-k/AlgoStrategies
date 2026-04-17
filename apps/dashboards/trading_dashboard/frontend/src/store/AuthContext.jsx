import { createContext, useContext, useState, useCallback } from 'react'
import { login as apiLogin, logout as apiLogout } from '../api/auth'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [user, setUser] = useState(() => {
    const stored = sessionStorage.getItem('td_user')
    return stored ? JSON.parse(stored) : null
  })

  const login = useCallback(async (email, password) => {
    const token = await apiLogin(email, password)
    window.__accessToken = token
    // Decode role from JWT payload (no verification needed client-side)
    const payload = JSON.parse(atob(token.split('.')[1]))
    const u = { email: payload.sub, role: payload.role }
    setUser(u)
    sessionStorage.setItem('td_user', JSON.stringify(u))
    return u
  }, [])

  const logout = useCallback(async () => {
    await apiLogout()
    window.__accessToken = null
    setUser(null)
    sessionStorage.removeItem('td_user')
  }, [])

  return (
    <AuthContext.Provider value={{ user, login, logout }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  return useContext(AuthContext)
}
