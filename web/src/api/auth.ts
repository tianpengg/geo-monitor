import { api } from './client'
import type { Session } from '../types'

export const authApi = {
  me: () => api<Session>('/auth/me'),
  login: (username: string, password: string) =>
    api<Session>('/auth/login', { method: 'POST', body: JSON.stringify({ username, password }) }),
  logout: () => api('/auth/logout', { method: 'POST' }),
}
