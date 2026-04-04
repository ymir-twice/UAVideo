<template>
  <n-config-provider :theme-overrides="themeOverrides">
    <n-message-provider>
      <n-dialog-provider>
        <n-notification-provider>
          <div class="app-container">
            <!-- 顶部导航 -->
            <header class="app-header">
              <div class="header-content">
                <div class="logo">
                  <n-icon :size="32" color="#18a058">
                    <video-camera-outline />
                  </n-icon>
                  <span class="logo-text">视频理解智能体</span>
                </div>
                <div class="header-actions">
                  <n-button quaternary @click="goHome">
                    <template #icon>
                      <n-icon><home-outline /></n-icon>
                    </template>
                    首页
                  </n-button>
                  <n-button quaternary @click="loadSessions">
                    <template #icon>
                      <n-icon><list-outline /></n-icon>
                    </template>
                    历史
                  </n-button>
                </div>
              </div>
            </header>

            <!-- 主内容 -->
            <main class="app-main">
              <!-- 首页：上传视频 -->
              <div v-if="!store.hasSession && view === 'home'" class="home-view">
                <div class="hero-section">
                  <h1 class="hero-title">视频理解智能体</h1>
                  <p class="hero-subtitle">基于长短期记忆管理的长视频理解与问答系统</p>
                </div>

                <div class="upload-section">
                  <n-card class="upload-card">
                    <div
                      class="upload-zone"
                      :class="{ 'upload-zone-active': isDragOver }"
                      @dragover.prevent="isDragOver = true"
                      @dragleave="isDragOver = false"
                      @drop.prevent="handleDrop"
                    >
                      <input
                        ref="fileInputRef"
                        type="file"
                        accept="video/*"
                        class="file-input"
                        @change="handleFileChange"
                      />
                      <div class="upload-content">
                        <n-icon :size="64" color="#18a058" class="upload-icon">
                          <cloud-upload-outline />
                        </n-icon>
                        <n-text class="upload-text">
                          拖拽视频文件到此处，或
                          <n-text type="primary" class="upload-link">点击选择</n-text>
                        </n-text>
                        <n-text depth="3" class="upload-hint">
                          支持 MP4, AVI, MOV 等格式
                        </n-text>
                      </div>
                    </div>

                    <div v-if="previewFile" class="preview-section">
                      <n-card embedded>
                        <div class="preview-info">
                          <n-icon :size="24" color="#18a058">
                            <film-outline />
                          </n-icon>
                          <n-text>{{ previewFile.name }}</n-text>
                          <n-text depth="3">({{ formatFileSize(previewFile.size) }})</n-text>
                        </div>
                        <n-button
                          type="primary"
                          size="large"
                          :loading="store.isUploading"
                          :disabled="!previewFile"
                          @click="handleUpload"
                          class="upload-btn"
                        >
                          <template #icon>
                            <n-icon><play-outline /></n-icon>
                          </template>
                          {{ store.isUploading ? '上传中...' : '开始分析' }}
                        </n-button>
                      </n-card>
                    </div>

                    <n-alert v-if="store.error" type="error" class="error-alert">
                      {{ store.error }}
                    </n-alert>
                  </n-card>
                </div>

                <!-- 功能介绍 -->
                <div class="features-section">
                  <n-grid :cols="3" :x-gap="24" :y-gap="24">
                    <n-gi>
                      <n-card class="feature-card">
                        <template #header>
                          <div class="feature-header">
                            <n-icon :size="28" color="#18a058">
                              <flash-outline />
                            </n-icon>
                            <span>自适应抽帧</span>
                          </div>
                        </template>
                        <n-text depth="2">
                          基于内容变化的智能抽帧技术，在保证语义完整性的同时大幅降低计算开销
                        </n-text>
                      </n-card>
                    </n-gi>
                    <n-gi>
                      <n-card class="feature-card">
                        <template #header>
                          <div class="feature-header">
                            <n-icon :size="28" color="#18a058">
                              <brain-outline />
                            </n-icon>
                            <span>长短期记忆</span>
                          </div>
                        </template>
                        <n-text depth="2">
                          模拟人类认知机制，短期记忆保留细节，长期记忆提炼语义，实现跨时间关联理解
                        </n-text>
                      </n-card>
                    </n-gi>
                    <n-gi>
                      <n-card class="feature-card">
                        <template #header>
                          <div class="feature-header">
                            <n-icon :size="28" color="#18a058">
                              <chatbox-outline />
                            </n-icon>
                            <span>智能问答</span>
                          </div>
                        </template>
                        <n-text depth="2">
                          基于记忆检索的精准问答，理解视频整体内容与细节，支持复杂推理与关联分析
                        </n-text>
                      </n-card>
                    </n-gi>
                  </n-grid>
                </div>
              </div>

              <!-- 处理中视图 -->
              <div v-else-if="store.isProcessing" class="processing-view">
                <n-card class="processing-card">
                  <div class="processing-header">
                    <n-icon :size="48" color="#18a058" class="processing-icon">
                      <sync-outline />
                    </n-icon>
                    <h2>视频分析中</h2>
                    <n-text depth="2">{{ store.processingMessage }}</n-text>
                  </div>

                  <n-progress
                    type="line"
                    :percentage="Math.round(store.processingProgress * 100)"
                    :indicator-placement="'inside'"
                    :processing="store.isProcessing"
                    status="success"
                  />

                  <n-list class="processing-steps">
                    <n-list-item
                      v-for="step in processingSteps"
                      :key="step.key"
                      :class="{ active: store.processingStage === step.key, completed: isStepCompleted(step.key) }"
                    >
                      <template #prefix>
                        <n-icon v-if="isStepCompleted(step.key)" color="#18a058">
                          <checkmark-circle-outline />
                        </n-icon>
                        <n-spin v-else-if="store.processingStage === step.key" :size="16" />
                        <n-icon v-else depth="4">
                          <ellipse-outline />
                        </n-icon>
                      </template>
                      {{ step.label }}
                    </n-list-item>
                  </n-list>
                </n-card>
              </div>

              <!-- 会话问答视图 -->
              <div v-else-if="store.hasSession" class="session-view">
                <div class="session-layout">
                  <!-- 左侧：视频和信息 -->
                  <div class="session-left">
                    <n-card class="video-card">
                      <template #header>
                        <div class="card-header">
                          <n-icon :size="20" color="#18a058">
                            <film-outline />
                          </n-icon>
                          <span>{{ store.currentSession?.video_name }}</span>
                        </div>
                      </template>
                      <div class="video-player">
                        <video
                          v-if="store.currentSession?.video_path"
                          :src="`file://${store.currentSession.video_path}`"
                          controls
                          class="video-element"
                        />
                        <div v-else class="video-placeholder">
                          <n-icon :size="64" depth="4">
                            <videocam-outline />
                          </n-icon>
                        </div>
                      </div>
                      <div class="video-info">
                        <n-statistic label="视频时长" :value="formatDuration(store.currentSession?.video_duration || 0)" />
                        <n-statistic label="处理帧数" :value="store.currentSession?.total_frames || 0" />
                        <n-statistic label="语义片段" :value="store.currentSession?.total_segments || 0" />
                      </div>
                    </n-card>

                    <!-- 记忆时间轴 -->
                    <n-card class="memory-card">
                      <template #header>
                        <div class="card-header">
                          <n-icon :size="20" color="#18a058">
                            <time-outline />
                          </n-icon>
                          <span>记忆时间轴</span>
                        </div>
                      </template>
                      <div class="timeline">
                        <div
                          v-for="segment in store.longTermSegments"
                          :key="segment.segment_id"
                          class="timeline-item"
                          :style="{ left: `${(segment.start_time / (store.currentSession?.video_duration || 1)) * 100}%` }"
                          @click="selectedSegment = segment"
                        >
                          <div class="timeline-marker"></div>
                          <div class="timeline-tooltip">
                            <n-text strong>{{ segment.start_time.toFixed(0) }}s - {{ segment.end_time.toFixed(0) }}s</n-text>
                            <n-text depth="2">{{ segment.summary }}</n-text>
                          </div>
                        </div>
                      </div>
                    </n-card>
                  </div>

                  <!-- 右侧：问答 -->
                  <div class="session-right">
                    <!-- 视频摘要 -->
                    <n-card v-if="videoSummary" class="summary-card">
                      <template #header>
                        <div class="card-header">
                          <n-icon :size="20" color="#18a058">
                            <document-text-outline />
                          </n-icon>
                          <span>视频摘要</span>
                        </div>
                      </template>
                      <n-text>{{ videoSummary }}</n-text>
                    </n-card>

                    <!-- 对话历史 -->
                    <n-card class="chat-card">
                      <template #header>
                        <div class="card-header">
                          <n-icon :size="20" color="#18a058">
                            <chatbubbles-outline />
                          </n-icon>
                          <span>智能问答</span>
                        </div>
                      </template>
                      <div class="chat-messages" ref="chatContainerRef">
                        <div
                          v-for="(conv, idx) in store.conversations"
                          :key="idx"
                          class="chat-message"
                        >
                          <div class="message-question">
                            <div class="message-label">
                              <n-icon :size="14"><chatbox-ellipses-outline /></n-icon>
                              问题
                            </div>
                            <div class="message-content">{{ conv.question }}</div>
                          </div>
                          <div class="message-answer">
                            <div class="message-label">
                              <n-icon :size="14"><checkmark-circle-outline /></n-icon>
                              回答
                            </div>
                            <div class="message-content">{{ conv.answer }}</div>
                          </div>
                        </div>
                        <div v-if="store.conversations.length === 0" class="chat-empty">
                          <n-empty description="开始提问吧" />
                        </div>
                      </div>

                      <!-- 输入区域 -->
                      <div class="chat-input">
                        <n-input
                          v-model:value="questionInput"
                          type="text"
                          placeholder="请输入您的问题..."
                          @keydown.enter="handleAsk"
                          :disabled="isAsking"
                        />
                        <n-button
                          type="primary"
                          :loading="isAsking"
                          @click="handleAsk"
                          :disabled="!questionInput.trim()"
                        >
                          <template #icon>
                            <n-icon><send-outline /></n-icon>
                          </template>
                          提问
                        </n-button>
                      </div>
                    </n-card>

                    <!-- 记忆片段 -->
                    <n-card class="segments-card">
                      <template #header>
                        <div class="card-header">
                          <n-icon :size="20" color="#18a058">
                            <layers-outline />
                          </n-icon>
                          <span>记忆片段 ({{ store.longTermSegments.length }})</span>
                        </div>
                      </template>
                      <div class="segments-list">
                        <div
                          v-for="segment in store.longTermSegments"
                          :key="segment.segment_id"
                          class="segment-item"
                          :class="{ active: selectedSegment?.segment_id === segment.segment_id }"
                          @click="selectedSegment = segment"
                        >
                          <div class="segment-time">{{ segment.start_time.toFixed(0) }}s - {{ segment.end_time.toFixed(0) }}s</div>
                          <n-text depth="2" class="segment-summary">{{ segment.summary }}</n-text>
                          <div v-if="segment.events.length" class="segment-events">
                            <n-tag v-for="event in segment.events.slice(0, 2)" :key="event" size="small">
                              {{ event }}
                            </n-tag>
                          </div>
                        </div>
                      </div>

                      <!-- 选中片段详情 -->
                      <div v-if="selectedSegment" class="segment-detail">
                        <n-divider />
                        <n-text strong>{{ selectedSegment.start_time.toFixed(0) }}s - {{ selectedSegment.end_time.toFixed(0) }}s</n-text>
                        <n-text>{{ selectedSegment.summary }}</n-text>
                        <div v-if="selectedSegment.entities.length" class="segment-entities">
                          <n-text depth="3">实体: </n-text>
                          <n-text>{{ selectedSegment.entities.join(', ') }}</n-text>
                        </div>
                        <div v-if="selectedSegment.events.length" class="segment-events-detail">
                          <n-text depth="3">事件: </n-text>
                          <n-text>{{ selectedSegment.events.join(', ') }}</n-text>
                        </div>
                      </div>
                    </n-card>
                  </div>
                </div>
              </div>

              <!-- 历史会话视图 -->
              <div v-else-if="view === 'history'" class="history-view">
                <n-card>
                  <template #header>
                    <div class="history-header">
                      <h2>历史会话</h2>
                      <n-button quaternary @click="goHome">
                        <n-icon><close-outline /></n-icon>
                      </n-button>
                    </div>
                  </template>
                  <n-list v-if="store.sessions.length > 0">
                    <n-list-item v-for="session in store.sessions" :key="session.session_id">
                      <div class="session-item">
                        <div class="session-info">
                          <n-text strong>{{ session.video_name }}</n-text>
                          <n-text depth="3">
                            {{ formatDate(session.created_at) }} |
                            {{ session.status.stage }}
                          </n-text>
                        </div>
                        <div class="session-actions">
                          <n-button
                            v-if="session.status.stage === 'done'"
                            type="primary"
                            size="small"
                            @click="openSession(session.session_id)"
                          >
                            打开
                          </n-button>
                          <n-button
                            type="error"
                            size="small"
                            ghost
                            @click="handleDeleteSession(session.session_id)"
                          >
                            删除
                          </n-button>
                        </div>
                      </div>
                    </n-list-item>
                  </n-list>
                  <n-empty v-else description="暂无历史会话" />
                </n-card>
              </div>
            </main>
          </div>
        </n-notification-provider>
      </n-dialog-provider>
    </n-message-provider>
  </n-config-provider>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, nextTick } from 'vue'
import { useStore } from 'naive-ui'
import {
  NConfigProvider, NMessageProvider, NDialogProvider, NNotificationProvider,
  NButton, NCard, NInput, NIcon, NProgress, NGrid, NGi, NText,
  NList, NListItem, NStatistic, NTag, NDivider, NEmpty, NAlert
} from 'naive-ui'
import {
  VideoCameraOutline, HomeOutline, ListOutline, CloudUploadOutline,
  FilmOutline, PlayOutline, FlashOutline, BrainOutline, ChatboxOutline,
  SyncOutline, CheckmarkCircleOutline, EllipseOutline, TimeOutline,
  DocumentTextOutline, ChatbubblesOutline, SendOutline, LayersOutline,
  ChatboxEllipsesOutline, VideocamOutline, CloseOutline
} from '@vicons/ionicons5'

const store = useStore()

// Theme
const themeOverrides = {
  common: {
    primaryColor: '#18a058',
    primaryColorHover: '#36ad6a',
    primaryColorPressed: '#0c7a43'
  }
}

// View state
const view = ref<'home' | 'history' | 'session'>('home')
const isDragOver = ref(false)
const fileInputRef = ref<HTMLInputElement | null>(null)
const previewFile = ref<File | null>(null)
const questionInput = ref('')
const isAsking = ref(false)
const selectedSegment = ref<any>(null)
const chatContainerRef = ref<HTMLElement | null>(null)
const videoSummary = ref('')

// Processing steps
const processingSteps = [
  { key: 'extracting', label: '提取视频帧' },
  { key: 'captioning', label: '生成帧描述' },
  { key: 'asr', label: '音频转写' },
  { key: 'consolidating', label: '构建记忆' }
]

function isStepCompleted(key: string) {
  const order = ['extracting', 'captioning', 'asr', 'consolidating', 'done']
  const currentIndex = order.indexOf(store.processingStage)
  const stepIndex = order.indexOf(key)
  return currentIndex > stepIndex
}

// File handling
function handleDrop(e: DragEvent) {
  isDragOver.value = false
  const files = e.dataTransfer?.files
  if (files && files.length > 0) {
    selectFile(files[0])
  }
}

function handleFileChange(e: Event) {
  const input = e.target as HTMLInputElement
  if (input.files && input.files.length > 0) {
    selectFile(input.files[0])
  }
}

function selectFile(file: File) {
  if (!file.type.startsWith('video/')) {
    alert('请选择视频文件')
    return
  }
  previewFile.value = file
}

async function handleUpload() {
  if (!previewFile.value) return

  const sessionId = await store.uploadVideo(previewFile.value)
  if (sessionId) {
    view.value = 'session'
    // 自动开始理解
    await store.startUnderstanding()
  }
}

async function handleAsk() {
  if (!questionInput.value.trim() || isAsking.value) return

  isAsking.value = true
  const question = questionInput.value
  questionInput.value = ''

  await store.askQuestion(question)

  isAsking.value = false

  // 滚动到底部
  await nextTick()
  if (chatContainerRef.value) {
    chatContainerRef.value.scrollTop = chatContainerRef.value.scrollHeight
  }
}

// Navigation
function goHome() {
  view.value = 'home'
  store.clearCurrentSession()
  previewFile.value = null
  selectedSegment.value = null
  videoSummary.value = ''
}

async function openSession(sessionId: string) {
  await store.loadSession(sessionId)
  if (store.currentSession?.has_understanding) {
    await loadSummary()
  }
  view.value = 'session'
}

async function loadSessions() {
  await store.fetchSessions()
  view.value = 'history'
}

async function handleDeleteSession(sessionId: string) {
  await store.deleteSession(sessionId)
}

// Load summary
async function loadSummary() {
  if (!store.currentSession) return
  try {
    const { api } = await import('./api/client')
    const response = await api.getSummary(store.currentSession.session_id)
    videoSummary.value = response.summary || ''
  } catch (e) {
    console.error('Failed to load summary:', e)
  }
}

// Utils
function formatFileSize(bytes: number): string {
  if (bytes < 1024) return bytes + ' B'
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB'
  if (bytes < 1024 * 1024 * 1024) return (bytes / (1024 * 1024)).toFixed(1) + ' MB'
  return (bytes / (1024 * 1024 * 1024)).toFixed(2) + ' GB'
}

function formatDuration(seconds: number): string {
  const mins = Math.floor(seconds / 60)
  const secs = Math.floor(seconds % 60)
  return `${mins}:${secs.toString().padStart(2, '0')}`
}

function formatDate(timestamp: number | undefined): string {
  if (!timestamp) return ''
  return new Date(timestamp * 1000).toLocaleString('zh-CN')
}

// Load sessions on mount
onMounted(() => {
  store.fetchSessions()
})
</script>

<style scoped>
.app-container {
  min-height: 100vh;
  background: linear-gradient(135deg, #f5f7fa 0%, #e4e8eb 100%);
}

.app-header {
  background: white;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
  position: sticky;
  top: 0;
  z-index: 100;
}

.header-content {
  max-width: 1400px;
  margin: 0 auto;
  padding: 16px 24px;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.logo {
  display: flex;
  align-items: center;
  gap: 12px;
}

.logo-text {
  font-size: 20px;
  font-weight: 600;
  color: #18a058;
}

.header-actions {
  display: flex;
  gap: 8px;
}

.app-main {
  max-width: 1400px;
  margin: 0 auto;
  padding: 24px;
}

/* Home View */
.home-view {
  display: flex;
  flex-direction: column;
  gap: 48px;
}

.hero-section {
  text-align: center;
  padding: 48px 0;
}

.hero-title {
  font-size: 48px;
  font-weight: 700;
  color: #18a058;
  margin-bottom: 16px;
}

.hero-subtitle {
  font-size: 20px;
  color: #666;
}

.upload-section {
  max-width: 800px;
  margin: 0 auto;
  width: 100%;
}

.upload-card {
  padding: 24px;
}

.upload-zone {
  border: 2px dashed #d9d9d9;
  border-radius: 12px;
  padding: 64px;
  text-align: center;
  cursor: pointer;
  transition: all 0.3s;
}

.upload-zone:hover,
.upload-zone-active {
  border-color: #18a058;
  background: rgba(24, 160, 88, 0.05);
}

.file-input {
  display: none;
}

.upload-icon {
  margin-bottom: 16px;
}

.upload-text {
  font-size: 16px;
  margin-bottom: 8px;
}

.upload-link {
  cursor: pointer;
}

.upload-hint {
  font-size: 14px;
}

.preview-section {
  margin-top: 24px;
}

.preview-info {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 16px;
}

.upload-btn {
  width: 100%;
}

.error-alert {
  margin-top: 16px;
}

.features-section {
  margin-top: 48px;
}

.feature-card {
  height: 100%;
  transition: transform 0.3s, box-shadow 0.3s;
}

.feature-card:hover {
  transform: translateY(-4px);
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.12);
}

.feature-header {
  display: flex;
  align-items: center;
  gap: 8px;
  color: #18a058;
}

/* Processing View */
.processing-view {
  display: flex;
  justify-content: center;
  align-items: center;
  min-height: 60vh;
}

.processing-card {
  max-width: 500px;
  width: 100%;
  text-align: center;
}

.processing-header {
  margin-bottom: 32px;
}

.processing-header h2 {
  margin: 16px 0 8px;
}

.processing-icon {
  animation: rotate 2s linear infinite;
}

@keyframes rotate {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

.processing-steps {
  margin-top: 32px;
  text-align: left;
}

.processing-steps .n-list-item {
  padding: 12px 0;
}

.processing-steps .n-list-item.active {
  color: #18a058;
  font-weight: 500;
}

.processing-steps .n-list-item.completed {
  color: #18a058;
}

/* Session View */
.session-view {
  width: 100%;
}

.session-layout {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 24px;
}

.session-left,
.session-right {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.card-header {
  display: flex;
  align-items: center;
  gap: 8px;
}

.video-card .video-player {
  background: #000;
  border-radius: 8px;
  overflow: hidden;
  margin-bottom: 16px;
}

.video-element {
  width: 100%;
  max-height: 400px;
  display: block;
}

.video-placeholder {
  height: 200px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #f5f5f5;
}

.video-info {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 16px;
}

/* Memory Timeline */
.timeline {
  position: relative;
  height: 60px;
  background: linear-gradient(90deg, #e8f5e9 0%, #c8e6c9 100%);
  border-radius: 8px;
  margin-top: 8px;
}

.timeline-item {
  position: absolute;
  top: 50%;
  transform: translate(-50%, -50%);
  cursor: pointer;
}

.timeline-marker {
  width: 16px;
  height: 16px;
  background: #18a058;
  border-radius: 50%;
  border: 2px solid white;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.2);
}

.timeline-tooltip {
  position: absolute;
  bottom: 24px;
  left: 50%;
  transform: translateX(-50%);
  background: white;
  padding: 8px 12px;
  border-radius: 8px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
  min-width: 150px;
  display: none;
  z-index: 10;
}

.timeline-item:hover .timeline-tooltip {
  display: block;
}

/* Chat */
.chat-card {
  flex: 1;
  display: flex;
  flex-direction: column;
}

.chat-messages {
  flex: 1;
  max-height: 400px;
  overflow-y: auto;
  padding: 16px 0;
}

.chat-message {
  margin-bottom: 16px;
}

.message-question,
.message-answer {
  margin-bottom: 12px;
}

.message-label {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 12px;
  margin-bottom: 4px;
  color: #18a058;
}

.message-question .message-label {
  color: #18a058;
}

.message-answer .message-label {
  color: #2080f0;
}

.message-content {
  background: #f5f5f5;
  padding: 12px;
  border-radius: 8px;
  line-height: 1.6;
}

.message-answer .message-content {
  background: #e6f4ff;
}

.chat-empty {
  padding: 48px;
}

.chat-input {
  display: flex;
  gap: 12px;
  padding-top: 16px;
  border-top: 1px solid #f0f0f0;
}

.chat-input .n-input {
  flex: 1;
}

/* Segments */
.segments-card {
  max-height: 400px;
  overflow-y: auto;
}

.segments-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.segment-item {
  padding: 12px;
  border: 1px solid #e8e8e8;
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.2s;
}

.segment-item:hover,
.segment-item.active {
  border-color: #18a058;
  background: #fafffe;
}

.segment-time {
  font-size: 12px;
  color: #18a058;
  margin-bottom: 4px;
}

.segment-summary {
  font-size: 14px;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.segment-events {
  display: flex;
  gap: 4px;
  margin-top: 8px;
  flex-wrap: wrap;
}

.segment-detail {
  padding-top: 12px;
}

.segment-entities,
.segment-events-detail {
  margin-top: 8px;
}

/* History View */
.history-view {
  max-width: 800px;
  margin: 0 auto;
}

.history-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.history-header h2 {
  margin: 0;
}

.session-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  width: 100%;
}

.session-info {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.session-actions {
  display: flex;
  gap: 8px;
}

.summary-card {
  background: linear-gradient(135deg, #e8f5e9 0%, #c8e6c9 100%);
}

.summary-card .n-card__content {
  line-height: 1.8;
}

/* Responsive */
@media (max-width: 1024px) {
  .session-layout {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 768px) {
  .hero-title {
    font-size: 32px;
  }

  .hero-subtitle {
    font-size: 16px;
  }

  .upload-zone {
    padding: 32px;
  }

  .video-info {
    grid-template-columns: 1fr;
  }
}
</style>
