import { ref } from 'vue'
import { ApiError, setCsrf } from '../api/client'
import { authApi } from '../api/auth'

type Callbacks = {
  loadSite: () => Promise<void>
  resetWorkspace: () => void
  failure: (error: unknown) => void
  attempt: (action: () => Promise<void>, expiredOnUnauthorized?: boolean) => Promise<void>
  beforeLogout: () => void
  missingFields: () => void
  clearError: () => void
}

export function useSession(callbacks: Callbacks) {
  const ready = ref(false),
    loggedIn = ref(false),
    sessionChecked = ref(false)
  const username = ref('admin'),
    currentUser = ref(''),
    password = ref('')
  function clear() {
    loggedIn.value = false
    sessionChecked.value = true
    setCsrf('')
    password.value = ''
    currentUser.value = ''
    callbacks.resetWorkspace()
  }
  function accept(session: { csrf_token: string; username: string }) {
    setCsrf(session.csrf_token)
    currentUser.value = session.username
    loggedIn.value = true
    sessionChecked.value = true
  }
  async function bootstrap() {
    ready.value = false
    callbacks.clearError()
    try {
      accept(await authApi.me())
      await callbacks.loadSite()
    } catch (error) {
      if (error instanceof ApiError && error.status === 401) clear()
      else {
        loggedIn.value = false
        sessionChecked.value = false
        callbacks.failure(error)
      }
    } finally {
      ready.value = true
    }
  }
  async function login() {
    if (!username.value.trim() || !password.value) {
      callbacks.missingFields()
      return
    }
    await callbacks.attempt(async () => {
      accept(await authApi.login(username.value, password.value))
      password.value = ''
      await callbacks.loadSite()
    }, false)
  }
  async function logout() {
    callbacks.beforeLogout()
    await callbacks.attempt(async () => {
      await authApi.logout()
      clear()
    })
  }
  return {
    ready,
    loggedIn,
    sessionChecked,
    username,
    currentUser,
    password,
    clear,
    bootstrap,
    login,
    logout,
  }
}
