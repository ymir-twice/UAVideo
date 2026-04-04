import axios from 'axios'

const API_BASE = '/api'

const apiClient = axios.create({
  baseURL: API_BASE,
  timeout: 300000,
  headers: {
    'Content-Type': 'application/json'
  }
})

// 添加auth token
let authToken = 'sk-admin'
export const setAuthToken = (token: string) => {
  authToken = token
  apiClient.defaults.headers.common['Authorization'] = `Bearer ${token}`
}
setAuthToken(authToken)

// ========== API类型定义 ==========

export interface SessionStatus {
  stage: string
  progress: number
  message: string
  current_frame?: number
  total_frames?: number
  error?: string | null
}

export interface Session {
  session_id: string
  video_name: string
  video_path: string
  video_duration: number
  status: SessionStatus
  total_frames: number
  total_segments: number
  has_understanding: boolean
  conversation_count: number
  created_at?: number
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

export interface QuestionResponse {
  session_id: string
  question: string
  answer: string
  timestamp: number
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

// ========== API函数 ==========

export const api = {
  // 创建Session
  async createSession(videoFile: File): Promise<CreateSessionResponse> {
    const formData = new FormData()
    formData.append('video', videoFile)
    const response = await apiClient.post('/sessions', formData, {
      headers: { 'Content-Type': 'multipart/form-data' }
    })
    return response.data
  },

  // 获取Session
  async getSession(sessionId: string): Promise<Session> {
    const response = await apiClient.get(`/sessions/${sessionId}`)
    return response.data
  },

  // 列出所有Session
  async listSessions(): Promise<{ sessions: Session[]; count: number }> {
    const response = await apiClient.get('/sessions')
    return response.data
  },

  // 删除Session
  async deleteSession(sessionId: string): Promise<{ success: boolean }> {
    const response = await apiClient.delete(`/sessions/${sessionId}`)
    return response.data
  },

  // 开始视频理解
  async startUnderstand(sessionId: string): Promise<{ message: string; session_id: string }> {
    const response = await apiClient.post(`/sessions/${sessionId}/understand`)
    return response.data
  },

  // 获取记忆数据
  async getMemory(sessionId: string): Promise<MemoryData> {
    const response = await apiClient.get(`/sessions/${sessionId}/memory`)
    return response.data
  },

  // 获取摘要
  async getSummary(sessionId: string): Promise<SummaryResponse> {
    const response = await apiClient.get(`/sessions/${sessionId}/summary`)
    return response.data
  },

  // 问答
  async askQuestion(sessionId: string, question: string): Promise<QuestionResponse> {
    const response = await apiClient.post(`/sessions/${sessionId}/question`, { question })
    return response.data
  },

  // 获取对话历史
  async getConversations(sessionId: string): Promise<{
    conversations: { question: string; answer: string; timestamp: number }[]
  }> {
    const response = await apiClient.get(`/sessions/${sessionId}/conversations`)
    return response.data
  },

  // SSE进度流
  createProgressStream(sessionId: string): EventSource {
    const url = `${API_BASE}/sessions/${sessionId}/stream`
    return new EventSource(url, { withCredentials: true })
  }
}

export default api
