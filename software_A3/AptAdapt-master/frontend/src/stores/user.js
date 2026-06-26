import { defineStore } from 'pinia'
import { ref } from 'vue'
import { login as loginApi } from '../api/auth'
import { getProfile } from '../api/chat'

export const useUserStore = defineStore('user', () => {
  const token = ref(localStorage.getItem('token') || '')
  const profile = ref(null)
  const isLoggedIn = ref(!!token.value)

  async function login(username, password) {
    const res = await loginApi(username, password)
    token.value = res.data.access_token
    localStorage.setItem('token', token.value)
    isLoggedIn.value = true
  }

  async function fetchProfile() {
    const res = await getProfile()
    profile.value = res.data
  }

  function logout() {
    token.value = ''
    profile.value = null
    isLoggedIn.value = false
    localStorage.removeItem('token')
  }

  return { token, profile, isLoggedIn, login, fetchProfile, logout }
})
