import axios from 'axios'
import type {
  NormalReviewSubmit,
  NormalReviewResponse,
  FeynmanVerifyResponse,
  SessionSnapshot,
  BatchCompletePayload,
} from '../types'

const api = axios.create({
  baseURL: '/api',
  headers: { 'Content-Type': 'application/json' },
})

api.interceptors.request.use((config) => {
  const token = localStorage.getItem('token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  if (config.data instanceof FormData) {
    delete config.headers['Content-Type']
  }
  return config
})

api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('token')
      window.location.href = '/login'
    }
    return Promise.reject(error)
  }
)

export const reviewApi = {
  getPending: (limit = 20, sourceType?: string) =>
    api.get('/review/pending', { params: { limit, source_type: sourceType } }),

  submitNormal: (data: NormalReviewSubmit) =>
    api.post<NormalReviewResponse>('/review/normal', data),

  submitVerificationFailed: (data: { chunk_id: string | null; schedule_id: string; response_time_ms: number }) =>
    api.post('/review/verification-failed', data),

  markMastered: (scheduleId: string) =>
    api.post(`/review/${scheduleId}/master`),

  feynmanVerify: (data: { schedule_id: string; explanation: string }) =>
    api.post<FeynmanVerifyResponse>('/review/feynman-verify', data),

  saveSession: (data: SessionSnapshot) =>
    api.post('/review/session', data),

  loadSession: () =>
    api.get<SessionSnapshot>('/review/session'),

  clearSession: () =>
    api.delete('/review/session'),

  batchComplete: (data: BatchCompletePayload) =>
    api.post('/review/batch-complete', data),

  getStats: () => api.get('/review/stats'),
}

export default api
