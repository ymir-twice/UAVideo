import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import axios from 'axios'

const API_BASE = '/api'
const AUTH_TOKEN = 'sk-admin'

const apiClient = axios.create({
  baseURL: API_BASE,
  timeout: 300000,
  headers: {
    'Content-Type': 'application/json'
  }
})
apiClient.defaults.headers.common['Authorization'] = `Bearer ${AUTH_TOKEN}`

// ========== 类型定义 ==========

export interface Message {
  id: string
  role: 'user' | 'assistant'
  content: string
  timestamp: number
}

export interface VideoInfo {
  name: string
  url: string | null
  file: File | null
  duration: number
  framesCount: number
}

export interface AnalysisResult {
  summary: string
  duration: number
  framesExtracted: number
  audioTranscribed: string
  keyTags: string[]
  processingTime: number
}

export interface SessionSummary {
  sessionId: string
  videoName: string
  lastMessage: string
  timestamp: number
  messageCount: number
}

// ========== Store ==========

export const useSessionStore = defineStore('session', () => {
  // State
  const messages = ref<Message[]>([])
  const isProcessing = ref(false)
  const processingStage = ref('')
  const processingProgress = ref(0)
  const processingMessage = ref('')
  const error = ref<string | null>(null)

  const videoInfo = ref<VideoInfo | null>(null)
  const analysisResult = ref<AnalysisResult | null>(null)
  const historySessions = ref<SessionSummary[]>([])
  const isHistoryOpen = ref(false)
  const isStreaming = ref(false)
  const streamingContent = ref('')

  let eventSource: EventSource | null = null

  // Computed
  const hasVideo = computed(() => videoInfo.value !== null)
  const hasAnalysis = computed(() => analysisResult.value !== null)
  const canSend = computed(() => messages.value.length > 0 || hasVideo.value)

  // Actions
  function generateId(): string {
    return Date.now().toString(36) + Math.random().toString(36).substr(2)
  }

  async function sendMessage(content: string) {
    if (!content.trim()) return

    // Add user message
    const userMsg: Message = {
      id: generateId(),
      role: 'user',
      content: content.trim(),
      timestamp: Date.now()
    }
    messages.value.push(userMsg)

    // If no video, use chat-only API
    if (!hasVideo.value) {
      await sendChatOnlyMessage(content)
      return
    }

    // With video - use video understanding API
    await sendVideoQuestion(content)
  }

  async function sendChatOnlyMessage(content: string) {
    isProcessing.value = true
    error.value = null

    const assistantMsg: Message = {
      id: generateId(),
      role: 'assistant',
      content: '',
      timestamp: Date.now()
    }
    messages.value.push(assistantMsg)

    try {
      const response = await apiClient.post('/v1/chat/completions', {
        model: 'tool-agent',
        messages: messages.value.map(m => ({ role: m.role, content: m.content }))
      })

      assistantMsg.content = response.data.choices[0].message.content
    } catch (e: any) {
      assistantMsg.content = `抱歉，发生了错误：${e.response?.data?.detail || e.message}`
    } finally {
      isProcessing.value = false
    }
  }

  async function sendVideoQuestion(content: string) {
    if (!videoInfo.value?.file) return

    isProcessing.value = true
    isStreaming.value = true
    streamingContent.value = ''
    error.value = null

    const assistantMsg: Message = {
      id: generateId(),
      role: 'assistant',
      content: '',
      timestamp: Date.now()
    }
    messages.value.push(assistantMsg)

    try {
      // First check if session exists, if not create one
      let sessionId = sessionStorage.getItem('currentSessionId')

      if (!sessionId) {
        const formData = new FormData()
        formData.append('video', videoInfo.value.file)
        const resp = await apiClient.post('/sessions', formData, {
          headers: { 'Content-Type': 'multipart/form-data' }
        })
        sessionId = resp.data.session_id
        sessionStorage.setItem('currentSessionId', sessionId)
      }

      // Start understanding if not done
      if (!hasAnalysis.value) {
        await startVideoUnderstanding(sessionId)
      }

      // Send question (non-streaming)
      const resp = await apiClient.post(`/sessions/${sessionId}/question`, {
        question: content
      })

      assistantMsg.content = resp.data.answer
      analysisResult.value = {
        summary: '视频分析完成',
        duration: videoInfo.value?.duration || 0,
        framesExtracted: 16,
        audioTranscribed: '',
        keyTags: [],
        processingTime: 0
      }
    } catch (e: any) {
      assistantMsg.content = `抱歉，发生了错误：${e.response?.data?.detail || e.message}`
    } finally {
      isProcessing.value = false
      isStreaming.value = false
    }
  }

  async function startVideoUnderstanding(sessionId: string) {
    processingStage.value = 'starting'
    processingProgress.value = 0
    processingMessage.value = '准备分析...'

    return new Promise<void>((resolve, reject) => {
      eventSource = new EventSource(`${API_BASE}/sessions/${sessionId}/stream`, {
        withCredentials: true
      })

      eventSource.onmessage = (event) => {
        const data = event.data.split('|')
        if (data.length >= 3) {
          processingStage.value = data[0]
          processingProgress.value = parseFloat(data[1]) || 0
          processingMessage.value = data[2] || ''

          if (data[0] === 'done') {
            isProcessing.value = false
            analysisResult.value = {
              summary: '视频分析完成',
              duration: videoInfo.value?.duration || 0,
              framesExtracted: parseInt(data[1]) || 16,
              audioTranscribed: '',
              keyTags: [],
              processingTime: 0
            }
            closeEventSource()
            resolve()
          }
        }
      }

      eventSource.onerror = () => {
        error.value = '连接中断'
        isProcessing.value = false
        closeEventSource()
        reject(new Error('SSE connection error'))
      }
    })
  }

  function closeEventSource() {
    if (eventSource) {
      eventSource.close()
      eventSource = null
    }
  }

  function setVideoFile(file: File) {
    videoInfo.value = {
      name: file.name,
      url: null,
      file: file,
      duration: 0,
      framesCount: 0
    }
    // Clear previous analysis
    analysisResult.value = null
    messages.value = []
    sessionStorage.removeItem('currentSessionId')
  }

  function setVideoUrl(url: string) {
    videoInfo.value = {
      name: url.split('/').pop() || '视频',
      url: url,
      file: null,
      duration: 0,
      framesCount: 0
    }
    analysisResult.value = null
    messages.value = []
    sessionStorage.removeItem('currentSessionId')
  }

  function clearVideo() {
    videoInfo.value = null
    analysisResult.value = null
    messages.value = []
    sessionStorage.removeItem('currentSessionId')
  }

  async function loadHistory() {
    try {
      const response = await apiClient.get('/sessions')
      historySessions.value = response.data.sessions.map((s: any) => ({
        sessionId: s.session_id,
        videoName: s.video_name,
        lastMessage: '',
        timestamp: s.created_at || Date.now(),
        messageCount: s.conversation_count || 0
      }))
    } catch (e) {
      console.error('Failed to load history:', e)
    }
  }

  function toggleHistory() {
    isHistoryOpen.value = !isHistoryOpen.value
    if (isHistoryOpen.value) {
      loadHistory()
    }
  }

  function clearError() {
    error.value = null
  }

  return {
    // State
    messages,
    isProcessing,
    processingStage,
    processingProgress,
    processingMessage,
    error,
    videoInfo,
    analysisResult,
    historySessions,
    isHistoryOpen,
    isStreaming,

    // Computed
    hasVideo,
    hasAnalysis,
    canSend,

    // Actions
    sendMessage,
    setVideoFile,
    setVideoUrl,
    clearVideo,
    loadHistory,
    toggleHistory,
    clearError
  }
})
