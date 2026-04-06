<template>
  <n-config-provider :theme="darkTheme" :theme-overrides="themeOverrides">
    <n-message-provider>
      <n-notification-provider>
        <div class="app-container">
          <!-- Header -->
          <header class="app-header">
            <div class="header-left">
              <img :src="logoUrl" alt="VideoBuddy" class="logo-img" />
              <span class="logo-text">VideoBuddy</span>
            </div>
            <div class="header-right">
              <n-button quaternary circle @click="store.toggleHistory()" title="历史对话">
                <template #icon>
                  <n-icon :component="menuOutline" />
                </template>
              </n-button>
            </div>
          </header>

          <!-- Main Content -->
          <main class="app-main">
            <!-- Video Upload Section (Optional, Above Chat) -->
            <div v-if="!store.hasVideo" class="upload-section">
              <div class="upload-tabs">
                <button
                  :class="['tab', { active: uploadMode === 'file' }]"
                  @click="uploadMode = 'file'"
                >
                  上传视频
                </button>
                <button
                  :class="['tab', { active: uploadMode === 'url' }]"
                  @click="uploadMode = 'url'"
                >
                  视频链接
                </button>
              </div>

              <div v-if="uploadMode === 'file'" class="upload-zone" @click="triggerFileInput">
                <input
                  ref="fileInputRef"
                  type="file"
                  accept="video/*"
                  style="display: none"
                  @change="handleFileSelect"
                />
                <div class="upload-content">
                  <n-icon :size="32" :component="cloudUploadOutline" class="upload-icon" />
                  <span class="upload-text">点击选择视频文件</span>
                  <span class="upload-hint">支持 MP4, AVI, MOV, WebM</span>
                </div>
              </div>

              <div v-else class="url-input-section">
                <n-input
                  v-model:value="videoUrl"
                  placeholder="请输入视频链接..."
                  @keydown.enter="handleUrlSubmit"
                >
                  <template #append>
                    <n-button @click="handleUrlSubmit" :disabled="!videoUrl.trim()">
                      添加
                    </n-button>
                  </template>
                </n-input>
              </div>

              <div v-if="store.hasVideo" class="video-preview">
                <div class="preview-info">
                  <n-icon :component="filmOutline" />
                  <span>{{ store.videoInfo?.name }}</span>
                  <n-button quaternary circle size="small" @click="store.clearVideo()">
                    <template #icon>
                      <n-icon :component="closeOutline" />
                    </template>
                  </n-button>
                </div>
              </div>
            </div>

            <!-- Video Preview (When Video Uploaded) -->
            <div v-if="store.hasVideo" class="video-section">
              <video
                v-if="store.videoInfo?.url"
                :src="store.videoInfo.url"
                controls
                class="video-player"
              />
              <div v-else class="video-placeholder">
                <n-icon :size="48" :component="videocamOutline" />
                <span>{{ store.videoInfo?.name }}</span>
              </div>
            </div>

            <!-- Messages -->
            <div class="messages-container" ref="messagesContainer">
              <!-- Welcome Message -->
              <div v-if="store.messages.length === 0 && !store.isProcessing" class="welcome-message">
                <img :src="logoUrl" alt="VideoBuddy" class="welcome-logo" />
                <h2>我是 VideoBuddy</h2>
                <p v-if="store.hasVideo">视频已准备就绪，开始问我任何关于这个视频的问题吧！</p>
                <p v-else>我是视频理解智能体，可以分析视频内容并回答问题。</p>
              </div>

              <!-- Message List -->
              <div
                v-for="msg in store.messages"
                :key="msg.id"
                :class="['message-wrapper', msg.role]"
              >
                <div class="message-avatar">
                  <img v-if="msg.role === 'assistant'" :src="logoUrl" alt="AI" />
                  <div v-else class="user-avatar">U</div>
                </div>
                <div class="message-content">
                  <div v-if="msg.role === 'user'" class="message-bubble user">
                    {{ msg.content }}
                  </div>
                  <div v-else class="message-bubble assistant" v-html="renderMarkdown(msg.content)" />
                </div>
              </div>

              <!-- Processing Indicator -->
              <div v-if="store.isProcessing" class="message-wrapper assistant">
                <div class="message-avatar">
                  <img :src="logoUrl" alt="AI" />
                </div>
                <div class="message-content">
                  <div class="message-bubble assistant processing">
                    <div class="processing-dots">
                      <span></span><span></span><span></span>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </main>

          <!-- Status Bar -->
          <div class="status-bar">
            <div class="status-content">
              <n-icon v-if="store.isProcessing" :component="syncOutline" class="status-icon spinning" />
              <n-icon v-else :component="checkmarkCircleOutline" class="status-icon" />
              <span class="status-text">
                {{ store.isProcessing ? store.processingMessage : 'VideoBuddy 已就绪' }}
              </span>
              <n-progress
                v-if="store.isProcessing"
                type="line"
                :percentage="Math.round(store.processingProgress * 100)"
                :show-indicator="false"
                :height="4"
                class="status-progress"
              />
            </div>
          </div>

          <!-- Input Area -->
          <div class="input-area">
            <div class="input-container">
              <textarea
                ref="inputRef"
                v-model="inputMessage"
                class="input-field"
                placeholder="输入消息..."
                rows="1"
                @keydown="handleKeydown"
                @input="autoResize"
              />
              <n-button
                type="primary"
                circle
                :disabled="!inputMessage.trim() || store.isProcessing"
                @click="handleSend"
                class="send-btn"
              >
                <template #icon>
                  <n-icon :component="paperPlaneOutline" />
                </template>
              </n-button>
            </div>
            <p class="input-hint">VideoBuddy 可以分析视频内容并回答问题</p>
          </div>

          <!-- History Drawer -->
          <n-drawer v-model:show="store.isHistoryOpen" :width="320" placement="right">
            <n-drawer-content title="历史对话" closable>
              <div v-if="store.historySessions.length === 0" class="history-empty">
                <n-empty description="暂无历史对话" />
              </div>
              <div v-else class="history-list">
                <div
                  v-for="session in store.historySessions"
                  :key="session.sessionId"
                  class="history-item"
                  @click="loadSession(session.sessionId)"
                >
                  <div class="history-icon">
                    <n-icon :component="filmOutline" />
                  </div>
                  <div class="history-info">
                    <span class="history-name">{{ session.videoName }}</span>
                    <span class="history-meta">
                      {{ formatTime(session.timestamp) }} · {{ session.messageCount }} 条消息
                    </span>
                  </div>
                </div>
              </div>
            </n-drawer-content>
          </n-drawer>
        </div>
      </n-notification-provider>
    </n-message-provider>
  </n-config-provider>
</template>

<script setup lang="ts">
import { ref, nextTick, onMounted, watch } from 'vue'
import { darkTheme, NIcon } from 'naive-ui'
import {
  NConfigProvider, NMessageProvider, NNotificationProvider,
  NButton, NInput, NDrawer, NDrawerContent, NEmpty, NProgress
} from 'naive-ui'
import {
  MenuOutline,
  CloudUploadOutline,
  FilmOutline,
  CloseOutline,
  VideocamOutline,
  SyncOutline,
  CheckmarkCircleOutline,
  PaperPlaneOutline
} from '@vicons/ionicons5'
import { useSessionStore } from './stores/session'
import { marked } from 'marked'
import hljs from 'highlight.js'

const store = useSessionStore()

// Logo
const logoUrl = '/videobuddy.png'

// Icons
const menuOutline = MenuOutline
const cloudUploadOutline = CloudUploadOutline
const filmOutline = FilmOutline
const closeOutline = CloseOutline
const videocamOutline = VideocamOutline
const syncOutline = SyncOutline
const checkmarkCircleOutline = CheckmarkCircleOutline
const paperPlaneOutline = PaperPlaneOutline

// Upload
const uploadMode = ref<'file' | 'url'>('file')
const fileInputRef = ref<HTMLInputElement | null>(null)
const videoUrl = ref('')

// Input
const inputMessage = ref('')
const inputRef = ref<HTMLTextAreaElement | null>(null)
const messagesContainer = ref<HTMLElement | null>(null)

// Theme
const themeOverrides = {
  common: {
    primaryColor: '#f59e0b',
    primaryColorHover: '#fbbf24',
    primaryColorPressed: '#d97706',
    primaryColorSuppl: '#f59e0b',
    borderRadius: '8px',
    borderRadiusSmall: '6px'
  },
  Button: {
    colorPrimary: '#f59e0b',
    colorHoverPrimary: '#fbbf24',
    colorPressedPrimary: '#d97706',
    textColor: '#1a1614'
  },
  Input: {
    color: '#292524',
    colorFocus: '#292524',
    border: '1px solid #44403c',
    borderHover: '1px solid #f59e0b',
    borderFocus: '1px solid #f59e0b'
  },
  Drawer: {
    color: '#1f1d1c',
    headerColor: '#1f1d1c',
    titleTextColor: '#fef3c7'
  },
  Card: {
    color: '#292524'
  }
}

// Configure marked
marked.setOptions({
  highlight: (code: string, lang: string) => {
    if (lang && hljs.getLanguage(lang)) {
      return hljs.highlight(code, { language: lang }).value
    }
    return code
  }
})

function renderMarkdown(content: string): string {
  return marked.parse(content) as string
}

function triggerFileInput() {
  fileInputRef.value?.click()
}

function handleFileSelect(e: Event) {
  const input = e.target as HTMLInputElement
  if (input.files && input.files[0]) {
    store.setVideoFile(input.files[0])
  }
}

function handleUrlSubmit() {
  if (videoUrl.value.trim()) {
    store.setVideoUrl(videoUrl.value.trim())
    videoUrl.value = ''
  }
}

function handleKeydown(e: KeyboardEvent) {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault()
    handleSend()
  }
}

async function handleSend() {
  if (!inputMessage.value.trim()) return

  await store.sendMessage(inputMessage.value)
  inputMessage.value = ''

  await nextTick()
  scrollToBottom()
}

function autoResize() {
  if (inputRef.value) {
    inputRef.value.style.height = 'auto'
    inputRef.value.style.height = Math.min(inputRef.value.scrollHeight, 200) + 'px'
  }
}

function scrollToBottom() {
  if (messagesContainer.value) {
    messagesContainer.value.scrollTop = messagesContainer.value.scrollHeight
  }
}

function formatTime(timestamp: number): string {
  const date = new Date(timestamp)
  const now = new Date()
  const diff = now.getTime() - date.getTime()

  if (diff < 60000) return '刚刚'
  if (diff < 3600000) return Math.floor(diff / 60000) + ' 分钟前'
  if (diff < 86400000) return Math.floor(diff / 3600000) + ' 小时前'
  return date.toLocaleDateString('zh-CN')
}

async function loadSession(sessionId: string) {
  store.isHistoryOpen = false
}

watch(() => store.messages.length, () => {
  nextTick(() => scrollToBottom())
})

onMounted(() => {
  inputRef.value?.focus()
})
</script>

<style scoped>
.app-container {
  display: flex;
  flex-direction: column;
  height: 100vh;
  background-color: #1a1614;
  color: #fef3c7;
}

/* Header */
.app-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 24px;
  background-color: #1f1d1c;
  border-bottom: 1px solid #44403c;
  height: 56px;
  flex-shrink: 0;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 12px;
}

.logo-img {
  height: 32px;
  width: auto;
}

.logo-text {
  font-size: 18px;
  font-weight: 600;
  color: #fef3c7;
}

.header-right {
  display: flex;
  gap: 8px;
}

/* Main */
.app-main {
  flex: 1;
  overflow-y: auto;
  padding: 0 24px;
  display: flex;
  flex-direction: column;
}

/* Upload Section */
.upload-section {
  padding: 16px 0;
  border-bottom: 1px solid #292524;
}

.upload-tabs {
  display: flex;
  gap: 8px;
  margin-bottom: 12px;
}

.tab {
  padding: 6px 16px;
  background: transparent;
  border: 1px solid #44403c;
  border-radius: 8px;
  color: #a8a29e;
  cursor: pointer;
  transition: all 0.2s;
  font-size: 14px;
}

.tab:hover {
  border-color: #f59e0b;
  color: #fef3c7;
}

.tab.active {
  background: #f59e0b;
  border-color: #f59e0b;
  color: #1a1614;
  font-weight: 500;
}

.upload-zone {
  border: 2px dashed #44403c;
  border-radius: 12px;
  padding: 32px;
  text-align: center;
  cursor: pointer;
  transition: all 0.2s;
}

.upload-zone:hover {
  border-color: #f59e0b;
  background: rgba(245, 158, 11, 0.05);
}

.upload-content {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
}

.upload-icon {
  color: #f59e0b;
}

.upload-text {
  color: #fef3c7;
  font-size: 14px;
}

.upload-hint {
  color: #a8a29e;
  font-size: 12px;
}

.url-input-section {
  max-width: 500px;
}

.video-preview {
  margin-top: 12px;
  padding: 12px;
  background: #292524;
  border-radius: 8px;
  display: flex;
  align-items: center;
  gap: 8px;
}

.preview-info {
  display: flex;
  align-items: center;
  gap: 8px;
  flex: 1;
}

/* Video Section */
.video-section {
  padding: 16px 0;
  border-bottom: 1px solid #292524;
}

.video-player {
  width: 100%;
  max-height: 300px;
  border-radius: 12px;
  background: #000;
}

.video-placeholder {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 48px;
  background: #292524;
  border-radius: 12px;
  color: #a8a29e;
}

/* Messages */
.messages-container {
  flex: 1;
  overflow-y: auto;
  padding: 24px 0;
}

.welcome-message {
  text-align: center;
  padding: 48px 24px;
}

.welcome-logo {
  height: 64px;
  width: auto;
  margin-bottom: 16px;
}

.welcome-message h2 {
  font-size: 24px;
  font-weight: 600;
  margin-bottom: 8px;
  color: #fef3c7;
}

.welcome-message p {
  color: #a8a29e;
  font-size: 14px;
}

.message-wrapper {
  display: flex;
  gap: 12px;
  margin-bottom: 24px;
  animation: fadeIn 0.2s ease-out;
}

@keyframes fadeIn {
  from {
    opacity: 0;
    transform: translateY(8px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.message-wrapper.user {
  flex-direction: row-reverse;
}

.message-avatar {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  overflow: hidden;
  flex-shrink: 0;
}

.message-avatar img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.user-avatar {
  width: 100%;
  height: 100%;
  background: #44403c;
  color: #a8a29e;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 14px;
  font-weight: 600;
}

.message-content {
  max-width: 70%;
}

.message-bubble {
  padding: 12px 16px;
  border-radius: 12px;
  line-height: 1.6;
  font-size: 14px;
}

.message-bubble.user {
  background: #3f3f46;
  color: #fef3c7;
  border-bottom-right-radius: 4px;
}

.message-bubble.assistant {
  background: #292524;
  color: #fef3c7;
  border-bottom-left-radius: 4px;
}

.message-bubble.processing {
  display: flex;
  align-items: center;
  padding: 16px 20px;
}

.processing-dots {
  display: flex;
  gap: 4px;
}

.processing-dots span {
  width: 8px;
  height: 8px;
  background: #f59e0b;
  border-radius: 50%;
  animation: bounce 1.4s infinite ease-in-out both;
}

.processing-dots span:nth-child(1) { animation-delay: -0.32s; }
.processing-dots span:nth-child(2) { animation-delay: -0.16s; }

@keyframes bounce {
  0%, 80%, 100% {
    transform: scale(0);
  }
  40% {
    transform: scale(1);
  }
}

/* Status Bar */
.status-bar {
  height: 32px;
  background: #1f1d1c;
  border-top: 1px solid #292524;
  display: flex;
  align-items: center;
  padding: 0 24px;
  flex-shrink: 0;
}

.status-content {
  display: flex;
  align-items: center;
  gap: 8px;
  flex: 1;
}

.status-icon {
  color: #22c55e;
  font-size: 14px;
}

.status-icon.spinning {
  color: #f59e0b;
  animation: spin 1s linear infinite;
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

.status-text {
  font-size: 12px;
  color: #a8a29e;
}

.status-progress {
  width: 120px;
}

/* Input Area */
.input-area {
  padding: 16px 24px;
  background: #1a1614;
  border-top: 1px solid #292524;
  flex-shrink: 0;
}

.input-container {
  display: flex;
  gap: 12px;
  align-items: flex-end;
  max-width: 800px;
  margin: 0 auto;
}

.input-field {
  flex: 1;
  background: #292524;
  border: 1px solid #44403c;
  border-radius: 12px;
  padding: 12px 16px;
  color: #fef3c7;
  font-size: 14px;
  font-family: inherit;
  resize: none;
  outline: none;
  transition: border-color 0.2s;
  max-height: 200px;
  min-height: 48px;
}

.input-field:focus {
  border-color: #f59e0b;
}

.input-field::placeholder {
  color: #a8a29e;
}

.send-btn {
  width: 48px;
  height: 48px;
  flex-shrink: 0;
}

.input-hint {
  text-align: center;
  font-size: 12px;
  color: #57534e;
  margin-top: 8px;
}

/* History Drawer */
.history-empty {
  padding: 48px 24px;
}

.history-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.history-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px;
  background: #292524;
  border-radius: 8px;
  cursor: pointer;
  transition: background 0.2s;
}

.history-item:hover {
  background: #44403c;
}

.history-icon {
  width: 40px;
  height: 40px;
  background: #1a1614;
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #f59e0b;
}

.history-info {
  display: flex;
  flex-direction: column;
  gap: 4px;
  overflow: hidden;
}

.history-name {
  font-size: 14px;
  color: #fef3c7;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.history-meta {
  font-size: 12px;
  color: #a8a29e;
}

/* Highlight.js Theme Override */
:deep(.hljs) {
  background: #1a1614 !important;
  color: #fef3c7 !important;
  padding: 12px !important;
  border-radius: 8px !important;
  overflow-x: auto !important;
}
</style>
