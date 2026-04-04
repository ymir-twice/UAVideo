import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { api, Session, MemoryData, Segment, setAuthToken } from '../api/client'

export const useSessionStore = defineStore('session', () => {
  // State
  const currentSession = ref<Session | null>(null)
  const memoryData = ref<MemoryData | null>(null)
  const conversations = ref<{ question: string; answer: string; timestamp: number }[]>([])
  const isUploading = ref(false)
  const isProcessing = ref(false)
  const processingStage = ref('')
  const processingProgress = ref(0)
  const processingMessage = ref('')
  const error = ref<string | null>(null)
  const sessions = ref<Session[]>([])

  // EventSource for SSE
  let progressEventSource: EventSource | null = null

  // Computed
  const hasSession = computed(() => currentSession.value !== null)
  const hasMemory = computed(() => memoryData.value !== null && memoryData.value.short_term.count > 0)
  const shortTermFrames = computed(() => memoryData.value?.short_term.frames || [])
  const longTermSegments = computed(() => memoryData.value?.long_term.segments || [])

  // Actions
  async function uploadVideo(file: File): Promise<string | null> {
    isUploading.value = true
    error.value = null

    try {
      const response = await api.createSession(file)
      currentSession.value = {
        session_id: response.session_id,
        video_name: response.video_name,
        video_path: response.video_path,
        video_duration: 0,
        status: response.status,
        total_frames: 0,
        total_segments: 0,
        has_understanding: false,
        conversation_count: 0
      }
      return response.session_id
    } catch (e: any) {
      error.value = e.response?.data?.detail || '上传失败'
      return null
    } finally {
      isUploading.value = false
    }
  }

  async function loadSession(sessionId: string) {
    try {
      const session = await api.getSession(sessionId)
      currentSession.value = session
      if (session.has_understanding) {
        await loadMemory()
        await loadConversations()
      }
    } catch (e: any) {
      error.value = e.response?.data?.detail || '加载失败'
    }
  }

  async function startUnderstanding() {
    if (!currentSession.value) return

    isProcessing.value = true
    processingStage.value = 'starting'
    processingProgress.value = 0
    processingMessage.value = '准备开始...'
    error.value = null

    try {
      await api.startUnderstand(currentSession.value.session_id)
      startProgressStream()
    } catch (e: any) {
      error.value = e.response?.data?.detail || '启动失败'
      isProcessing.value = false
    }
  }

  function startProgressStream() {
    if (!currentSession.value) return

    stopProgressStream()

    progressEventSource = api.createProgressStream(currentSession.value.session_id)

    progressEventSource.onmessage = (event) => {
      const [stage, progress, message] = (event.data as string).split('|')
      processingStage.value = stage
      processingProgress.value = parseFloat(progress) || 0
      processingMessage.value = message || ''

      if (stage === 'done') {
        isProcessing.value = false
        loadMemory()
        loadConversations()
        loadSession(currentSession.value!.session_id)
      } else if (stage === 'error') {
        isProcessing.value = false
        error.value = message || '处理出错'
      }
    }

    progressEventSource.onerror = () => {
      isProcessing.value = false
      error.value = '连接中断'
      stopProgressStream()
    }
  }

  function stopProgressStream() {
    if (progressEventSource) {
      progressEventSource.close()
      progressEventSource = null
    }
  }

  async function loadMemory() {
    if (!currentSession.value) return

    try {
      memoryData.value = await api.getMemory(currentSession.value.session_id)
    } catch (e: any) {
      console.error('Failed to load memory:', e)
    }
  }

  async function loadConversations() {
    if (!currentSession.value) return

    try {
      const response = await api.getConversations(currentSession.value.session_id)
      conversations.value = response.conversations
    } catch (e: any) {
      console.error('Failed to load conversations:', e)
    }
  }

  async function askQuestion(question: string): Promise<string | null> {
    if (!currentSession.value) return null

    try {
      const response = await api.askQuestion(currentSession.value.session_id, question)
      conversations.value.push({
        question: response.question,
        answer: response.answer,
        timestamp: response.timestamp
      })
      return response.answer
    } catch (e: any) {
      error.value = e.response?.data?.detail || '问答失败'
      return null
    }
  }

  async function fetchSessions() {
    try {
      const response = await api.listSessions()
      sessions.value = response.sessions
    } catch (e: any) {
      console.error('Failed to fetch sessions:', e)
    }
  }

  async function deleteSession(sessionId: string) {
    try {
      await api.deleteSession(sessionId)
      sessions.value = sessions.value.filter(s => s.session_id !== sessionId)
      if (currentSession.value?.session_id === sessionId) {
        currentSession.value = null
        memoryData.value = null
        conversations.value = []
      }
    } catch (e: any) {
      error.value = e.response?.data?.detail || '删除失败'
    }
  }

  function clearCurrentSession() {
    stopProgressStream()
    currentSession.value = null
    memoryData.value = null
    conversations.value = []
    isProcessing.value = false
    processingStage.value = ''
    processingProgress.value = 0
    processingMessage.value = ''
    error.value = null
  }

  return {
    // State
    currentSession,
    memoryData,
    conversations,
    isUploading,
    isProcessing,
    processingStage,
    processingProgress,
    processingMessage,
    error,
    sessions,

    // Computed
    hasSession,
    hasMemory,
    shortTermFrames,
    longTermSegments,

    // Actions
    uploadVideo,
    loadSession,
    startUnderstanding,
    loadMemory,
    loadConversations,
    askQuestion,
    fetchSessions,
    deleteSession,
    clearCurrentSession
  }
})
