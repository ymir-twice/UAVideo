import axios from 'axios'

const API_BASE = '/api'
const AUTH_TOKEN = 'sk-admin'

export const apiClient = axios.create({
  baseURL: API_BASE,
  timeout: 300000,
  headers: {
    'Content-Type': 'application/json'
  }
})
apiClient.defaults.headers.common['Authorization'] = `Bearer ${AUTH_TOKEN}`

// Types
export interface Session {
  session_id: string
  video_name: string
  video_path: string
  video_duration: number
  status: string
  total_frames: number
  total_segments: number
  has_understanding: boolean
  conversation_count: number
  created_at?: number
}

export interface SessionStatus {
  stage: string
  progress: number
  message: string
}

export interface CreateSessionResponse {
  session_id: string
  video_name: string
  video_path: string
  status: SessionStatus
  message: string
}

export interface MemoryData {
  short_term: {
    frames: any[]
    count: number
    window_size: number
  }
  long_term: {
    segments: Segment[]
    count: number
  }
  video_duration: number
  frames_summary: string
}

export interface Segment {
  segment_id: string
  start_time: number
  end_time: number
  summary: string
  key_frames: string[]
  entities: string[]
  events: string[]
  importance_score: number
}

export interface SummaryResponse {
  session_id: string
  summary: string | null
  key_events: string[]
  duration: number
  frames_extracted: number
  segments_created: number
  processing_time: number
  message?: string
}

// API Functions
export const api = {
  async createSession(videoFile: File): Promise<CreateSessionResponse> {
    const formData = new FormData()
    formData.append('video', videoFile)
    const response = await apiClient.post('/sessions', formData, {
      headers: { 'Content-Type': 'multipart/form-data' }
    })
    return response.data
  },

  async getSession(sessionId: string): Promise<Session> {
    const response = await apiClient.get(`/sessions/${sessionId}`)
    return response.data
  },

  async listSessions(): Promise<{ sessions: Session[]; count: number }> {
    const response = await apiClient.get('/sessions')
    return response.data
  },

  async deleteSession(sessionId: string): Promise<{ success: boolean }> {
    const response = await apiClient.delete(`/sessions/${sessionId}`)
    return response.data
  },

  async startUnderstand(sessionId: string): Promise<{ message: string; session_id: string }> {
    const response = await apiClient.post(`/sessions/${sessionId}/understand`)
    return response.data
  },

  async getMemory(sessionId: string): Promise<MemoryData> {
    const response = await apiClient.get(`/sessions/${sessionId}/memory`)
    return response.data
  },

  async getSummary(sessionId: string): Promise<SummaryResponse> {
    const response = await apiClient.get(`/sessions/${sessionId}/summary`)
    return response.data
  },

  async askQuestion(sessionId: string, question: string): Promise<{
    question: string
    answer: string
    timestamp: number
  }> {
    const response = await apiClient.post(`/sessions/${sessionId}/question`, { question })
    return response.data
  },

  async getConversations(sessionId: string): Promise<{
    conversations: { question: string; answer: string; timestamp: number }[]
  }> {
    const response = await apiClient.get(`/sessions/${sessionId}/conversations`)
    return response.data
  },

  createProgressStream(sessionId: string): EventSource {
    const url = `${API_BASE}/sessions/${sessionId}/stream`
    return new EventSource(url, { withCredentials: true })
  }
}

export default api
