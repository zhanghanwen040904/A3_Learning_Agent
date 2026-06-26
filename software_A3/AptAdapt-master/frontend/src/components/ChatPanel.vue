<template>
  <div class="chat-panel">
    <div class="chat-header">
      <div>
        <p class="aa-kicker">Conversation</p>
        <h2 class="aa-title">对话式学习画像</h2>
      </div>
      <span class="stream-badge">SSE 流式输出</span>
    </div>

    <div class="chat-messages" ref="msgContainer">
      <div v-for="(msg, index) in messages" :key="index" :class="['message', msg.role]">
        <div class="avatar">{{ msg.role === 'user' ? '我' : 'AI' }}</div>
        <div class="content" v-html="renderMarkdown(msg.content)"></div>
      </div>
      <div v-if="streaming" class="message assistant">
        <div class="avatar">AI</div>
        <div class="content" v-html="renderMarkdown(streamContent)"></div>
        <span class="cursor">|</span>
      </div>
    </div>

    <div class="quick-prompts">
      <button @click="fillPrompt('我 Cache 映射方式总是分不清，希望用图解和例题学习。')">
        Cache 映射
      </button>
      <button @click="fillPrompt('帮我梳理流水线冲突，并生成一组选择题。')">
        流水线冲突
      </button>
      <button @click="fillPrompt('我想用汇编和图示理解中断处理流程。')">
        中断机制
      </button>
    </div>

    <div class="chat-input">
      <el-input
        v-model="input"
        placeholder="输入你的学习问题，如：我 Cache 映射方式分不清..."
        @keyup.enter="send"
        :disabled="streaming"
        size="large"
      />
      <el-button type="primary" size="large" @click="send" :disabled="streaming" :loading="streaming">
        发送
      </el-button>
    </div>
  </div>
</template>

<script setup>
import { ref, nextTick, onMounted } from 'vue'
import { useCourseStore } from '../stores/course'
import markdownit from 'markdown-it'

const md = markdownit()
const courseStore = useCourseStore()
const messages = ref([])
const input = ref('帮我生成 Cache 直接映射、全相联、组相联的学习资源')
const streamContent = ref('')
const streaming = ref(false)
const msgContainer = ref(null)

function renderMarkdown(text) {
  return text ? md.render(text) : ''
}

function scrollToBottom() {
  nextTick(() => {
    const el = msgContainer.value
    if (el) el.scrollTop = el.scrollHeight
  })
}

function fillPrompt(text) {
  input.value = text
}

function mockReply(userMsg) {
  return `已识别你的学习需求：**${userMsg}**

系统将优先调用 Profile Agent、RAG Agent、Doc Agent、MindMap Agent、Quiz Agent 和 Reviewer Agent。

- 学习画像：偏好图解、例题和代码示例
- 当前薄弱点：Cache 映射方式、流水线冲突
- 推荐资源：讲解文档、思维导图、练习题、代码案例、视频脚本
- 下一步：进入右侧资源区查看生成结果`
}

async function send() {
  if (!input.value.trim() || streaming.value) return
  const userMsg = input.value.trim()
  messages.value.push({ role: 'user', content: userMsg })
  input.value = ''
  scrollToBottom()

  streaming.value = true
  streamContent.value = ''

  try {
    const { sendMessage } = await import('../api/chat')
    const res = await sendMessage(userMsg, courseStore.currentId)
    streamContent.value = res.data.data?.reply || res.data.reply || mockReply(userMsg)
  } catch {
    streamContent.value = mockReply(userMsg)
  } finally {
    messages.value.push({ role: 'assistant', content: streamContent.value })
    streaming.value = false
    streamContent.value = ''
    scrollToBottom()
  }
}

onMounted(() => {
  messages.value.push({
    role: 'assistant',
    content: '你好，我是 AptAdapt 学习助手。你可以描述自己的专业、薄弱点和学习目标，我会为你生成个性化学习资源。'
  })
})
</script>

<style scoped>
.chat-panel {
  display: grid;
  grid-template-rows: auto minmax(0, 1fr) auto auto;
  height: 100%;
  min-height: 0;
}

.chat-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  padding: 18px 18px 0;
}

.stream-badge {
  padding: 6px 10px;
  border-radius: 8px;
  color: #1b6c89;
  background: rgba(229, 249, 255, 0.78);
  border: 1px solid rgba(64, 184, 230, 0.18);
  font-size: 12px;
  white-space: nowrap;
}

.chat-messages {
  min-height: 150px;
  overflow-y: auto;
  padding: 18px;
}

.message {
  display: flex;
  gap: 12px;
  margin-bottom: 18px;
}

.message.user {
  flex-direction: row-reverse;
}

.avatar {
  width: 38px;
  height: 38px;
  border-radius: 50%;
  display: grid;
  place-items: center;
  flex-shrink: 0;
  color: #0f4e72;
  font-size: 13px;
  font-weight: 900;
  background: linear-gradient(135deg, rgba(122, 225, 255, 0.55), rgba(220, 232, 255, 0.8));
  border: 1px solid rgba(64, 184, 230, 0.2);
}

.message.assistant .avatar {
  color: #14664d;
  background: rgba(226, 255, 245, 0.9);
  border-color: rgba(39, 201, 148, 0.2);
}

.content {
  max-width: min(78%, 720px);
  padding: 13px 15px;
  border-radius: 8px;
  color: var(--aa-text);
  line-height: 1.75;
  font-size: 14px;
  background: rgba(255, 255, 255, 0.82);
  border: 1px solid rgba(89, 128, 176, 0.12);
}

.content :deep(p) {
  margin: 0;
}

.content :deep(p + p),
.content :deep(ul),
.content :deep(ol) {
  margin-top: 8px;
}

.message.user .content {
  color: #0f4e72;
  background: linear-gradient(135deg, rgba(208, 247, 255, 0.95), rgba(224, 233, 255, 0.92));
  border-color: rgba(64, 184, 230, 0.22);
}

.cursor {
  align-self: center;
  color: var(--aa-cyan);
  animation: blink 1s infinite;
}

.quick-prompts {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  padding: 0 18px 10px;
}

.quick-prompts button {
  min-height: 32px;
  padding: 0 12px;
  border: 1px solid rgba(64, 184, 230, 0.16);
  border-radius: 8px;
  color: #1b6c89;
  background: rgba(229, 249, 255, 0.72);
  cursor: pointer;
}

.chat-input {
  display: grid;
  grid-template-columns: 1fr auto;
  gap: 10px;
  padding: 12px 18px 18px;
  border-top: 1px solid rgba(89, 128, 176, 0.12);
}

@keyframes blink {
  0%, 50% { opacity: 1; }
  51%, 100% { opacity: 0; }
}
</style>
