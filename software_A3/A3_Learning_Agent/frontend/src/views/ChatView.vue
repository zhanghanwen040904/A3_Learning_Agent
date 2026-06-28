<template>
  <div class="page chat-page">
    <el-card class="panel chat-card">
      <template #header>
        <div class="header-line">
          <div>
            <strong>智能答疑</strong>
            <p>切换模块不会中断当前问答，返回后仍会保留历史。</p>
          </div>
          <div class="header-actions">
            <el-tag v-if="loading" type="warning">生成中，切换模块不会中断</el-tag>
            <el-button size="small" :disabled="loading" @click="clearHistory">清空历史</el-button>
            <el-switch v-model="needVideo" active-text="生成短视频" />
          </div>
        </div>
      </template>

      <div class="chat-window">
        <div v-for="(item, index) in messages" :key="`${item.role}-${index}`" :class="['bubble', item.role]">
          <div class="markdown-body" v-html="renderAnswerMarkdown(item, 'before')"></div>

          <template v-if="item.diagram_image">
            <div class="section-label">图解说明</div>
            <figure class="diagram-card">
              <img :src="item.diagram_image" alt="图解知识图" />
            </figure>
            <div class="markdown-body" v-html="renderAnswerMarkdown(item, 'after')"></div>
          </template>

          <div v-if="item.sources?.length" class="source-list">
            <strong>参考来源</strong>
            <el-tag v-for="source in item.sources" :key="`${source.source}-${source.chunk_index}`" size="small">
              {{ source.source }} #{{ source.chunk_index }}
            </el-tag>
          </div>

          <video v-if="item.video && isPlayableVideo(item.video)" controls :src="item.video" class="video"></video>
        </div>
      </div>

      <div class="composer">
        <el-progress v-if="loading" :percentage="progress" striped striped-flow />
        <el-steps v-if="loading" :active="activeStep" finish-status="success" simple>
          <el-step title="检索知识库" />
          <el-step title="生成回答" />
          <el-step title="安全复核" />
        </el-steps>

        <div class="input-line">
          <el-input
            v-model="question"
            type="textarea"
            :rows="2"
            :autosize="{ minRows: 2, maxRows: 5 }"
            placeholder="请输入课程问题，例如：需求分析和总体设计有什么区别？"
            @keydown.enter.exact.prevent="ask"
          />
          <el-button type="primary" :loading="loading" @click="ask">提问</el-button>
        </div>
      </div>
    </el-card>
  </div>
</template>

<script setup>
import MarkdownIt from "markdown-it";
import { computed, nextTick, onMounted, reactive, watch } from "vue";
import { ElMessage } from "element-plus";
import { activeProfileSessionId, chatApi } from "../api";

const md = new MarkdownIt({ html: true, linkify: true, breaks: true });
const WELCOME_MESSAGE = {
  role: "assistant",
  content: "我是课程答疑助手，会先检索知识库，再结合当前画像生成答案。",
};
const STORAGE_PREFIX = "a3_tutor_chat_v2_";

const chatState = reactive({
  sessionId: "",
  question: "需求分析和总体设计有什么区别？",
  needVideo: false,
  loading: false,
  progress: 0,
  activeStep: 0,
  messages: [WELCOME_MESSAGE],
  pendingPromise: null,
  timer: null,
});

const question = computed({
  get: () => chatState.question,
  set: (value) => {
    chatState.question = value;
  },
});
const needVideo = computed({
  get: () => chatState.needVideo,
  set: (value) => {
    chatState.needVideo = value;
  },
});
const loading = computed(() => chatState.loading);
const progress = computed(() => chatState.progress);
const activeStep = computed(() => chatState.activeStep);
const messages = computed(() => chatState.messages);

function storageKey(sessionId = chatState.sessionId) {
  return `${STORAGE_PREFIX}${sessionId || "default"}`;
}

function saveLocal() {
  localStorage.setItem(
    storageKey(),
    JSON.stringify({
      messages: chatState.messages,
      question: chatState.question,
      needVideo: chatState.needVideo,
      loading: chatState.loading,
      progress: chatState.progress,
      activeStep: chatState.activeStep,
    })
  );
}

function loadLocal(sessionId) {
  try {
    const raw = localStorage.getItem(storageKey(sessionId));
    if (!raw) return false;
    const data = JSON.parse(raw);
    chatState.messages = cleanMessages(data.messages || []);
    chatState.question = data.question || chatState.question;
    chatState.needVideo = Boolean(data.needVideo);
    chatState.progress = Number(data.progress || 0);
    chatState.activeStep = Number(data.activeStep || 0);
    return true;
  } catch {
    return false;
  }
}

async function loadHistory() {
  const sessionId = activeProfileSessionId();
  if (chatState.loading && chatState.sessionId === sessionId) return;
  chatState.sessionId = sessionId;
  loadLocal(sessionId);
  try {
    const res = await chatApi.history();
    if (res.code === 200 && Array.isArray(res.data?.messages) && res.data.messages.length && !chatState.loading) {
      chatState.messages = cleanMessages(res.data.messages);
      saveLocal();
    }
  } catch {}
}

function normalizeMarkdown(text) {
  let source = String(text || "").trim();
  const fenced = source.match(/^```(?:markdown|md|text)?\s*([\s\S]*?)\s*```$/i);
  if (fenced) source = fenced[1].trim();
  return source.replace(/^\s*```(?:markdown|md|text)?\s*$/gim, "").replace(/^\s*```\s*$/gm, "").trim();
}

function renderMarkdown(text) {
  return md.render(normalizeMarkdown(text));
}

function splitAnswerAroundDiagram(text) {
  const source = normalizeMarkdown(text);
  const heading = source.match(/(?:^|\n)#{1,6}\s*二[、.．]\s*图解说明\s*/);
  if (!heading) return { before: source, after: "" };
  const before = source.slice(0, heading.index).trim();
  const diagramStart = heading.index + heading[0].length;
  const rest = source.slice(diagramStart);
  const next = rest.match(/(?:^|\n)#{1,6}\s*(三|四)[、.．]\s*/);
  return { before, after: next ? rest.slice(next.index).trim() : "" };
}

function renderAnswerMarkdown(item, part = "all") {
  if (item?.diagram_image) {
    const split = splitAnswerAroundDiagram(item.content);
    if (part === "before") return md.render(split.before || "");
    if (part === "after") return md.render(split.after || "");
  }
  return renderMarkdown(item?.content || "");
}

function isPlayableVideo(text) {
  return /^https?:\/\//.test(String(text || "")) && !String(text).includes("example.com");
}

function cleanMessages(list) {
  const cleaned = [];
  for (const item of Array.isArray(list) ? list : []) {
    const role = item?.role || "assistant";
    const content = normalizeMarkdown(item?.content || "");
    if (!content && role === "assistant") continue;
    const next = { ...item, role, content };
    if (cleaned.length && cleaned[cleaned.length - 1].role === role && cleaned[cleaned.length - 1].content === content) continue;
    cleaned.push(next);
  }
  return cleaned.length ? cleaned : [WELCOME_MESSAGE];
}

function typewriter(target, fullText) {
  return new Promise((resolve) => {
    target.content = "";
    let index = 0;
    const timer = setInterval(() => {
      target.content += fullText.slice(index, index + 8);
      index += 8;
      saveLocal();
      if (index >= fullText.length) {
        target.content = fullText;
        clearInterval(timer);
        saveLocal();
        resolve();
      }
    }, 16);
  });
}

async function ask() {
  if (!chatState.question.trim() || chatState.loading) return;
  const askedQuestion = chatState.question;
  const historyBeforeQuestion = cleanMessages(chatState.messages);

  chatState.loading = true;
  chatState.progress = 10;
  chatState.activeStep = 0;
  chatState.messages.push({ role: "user", content: askedQuestion });
  const assistantMsg = { role: "assistant", content: "正在检索知识库并生成答案...", sources: [] };
  chatState.messages.push(assistantMsg);
  chatState.question = "";
  saveLocal();

  if (chatState.timer) clearInterval(chatState.timer);
  chatState.timer = setInterval(() => {
    chatState.progress = Math.min(chatState.progress + 7, 94);
    chatState.activeStep = chatState.progress > 65 ? 2 : chatState.progress > 35 ? 1 : 0;
    saveLocal();
  }, 500);

  chatState.pendingPromise = chatApi.answer({
    question: askedQuestion,
    need_video: chatState.needVideo,
    messages: historyBeforeQuestion,
  });

  try {
    const res = await chatState.pendingPromise;
    if (res.code === 200) {
      assistantMsg.sources = res.data.sources || [];
      assistantMsg.video = res.data.video_url;
      assistantMsg.diagram_image = res.data.diagram_image;
      await typewriter(assistantMsg, res.data.answer);
      chatState.messages = cleanMessages(chatState.messages);
      await chatApi.saveHistory({ messages: chatState.messages });
    } else {
      assistantMsg.content = res.msg || "答疑失败";
      ElMessage.error(res.msg || "答疑失败");
    }
  } catch (error) {
    assistantMsg.content = error?.message || "答疑异常，请稍后重试";
  } finally {
    if (chatState.timer) clearInterval(chatState.timer);
    chatState.timer = null;
    chatState.activeStep = 3;
    chatState.progress = 100;
    chatState.loading = false;
    chatState.pendingPromise = null;
    saveLocal();
  }
}

async function clearHistory() {
  if (chatState.loading) return;
  chatState.messages = [WELCOME_MESSAGE];
  chatState.progress = 0;
  chatState.activeStep = 0;
  saveLocal();
  const res = await chatApi.clearHistory();
  if (res.code === 200) ElMessage.success("答疑历史已清空");
}

onMounted(async () => {
  await loadHistory();
  await nextTick();
});

watch(
  () => activeProfileSessionId(),
  async (nextSession, previousSession) => {
    if (nextSession === previousSession || chatState.loading) return;
    await loadHistory();
  }
);
</script>

<style scoped>
.chat-page {
  display: grid;
  height: calc(100vh - 56px);
  min-height: 0;
}

.chat-card {
  height: 100%;
  min-height: 0;
}

.chat-card :deep(.el-card__body) {
  display: grid;
  grid-template-rows: minmax(0, 1fr) auto;
  height: calc(100vh - 145px);
  min-height: 0;
  gap: 16px;
}

.header-line,
.input-line {
  display: flex;
  align-items: center;
  gap: 14px;
  justify-content: space-between;
}

.header-line strong {
  color: #37352f;
  font-size: 20px;
  line-height: 1.2;
}

.header-line p {
  margin: 6px 0 0;
  color: #6e6e73;
  font-size: 14px;
  line-height: 1.5;
}

.header-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

.chat-window {
  min-height: 0;
  overflow: auto;
  padding: 8px 0 18px;
  background: #ffffff;
}

.bubble {
  max-width: 100%;
  margin-bottom: 16px;
  padding: 14px 16px;
  border: 0;
  border-radius: 8px;
  color: #37352f;
  transition: background-color 0.2s ease;
}

.bubble.assistant {
  background: #f7f7f8;
}

.bubble.user {
  margin-left: 48px;
  background: #ffffff;
}

.bubble.assistant:last-child::after {
  display: inline-flex;
  gap: 5px;
  width: 34px;
  height: 12px;
  margin-left: 8px;
  vertical-align: middle;
  content: "";
  background:
    radial-gradient(circle, #6e6e73 45%, transparent 47%) 0 50% / 8px 8px no-repeat,
    radial-gradient(circle, #6e6e73 45%, transparent 47%) 13px 50% / 8px 8px no-repeat,
    radial-gradient(circle, #6e6e73 45%, transparent 47%) 26px 50% / 8px 8px no-repeat;
  animation: dot-breathe 1.2s ease-in-out infinite;
}

.section-label {
  margin: 14px 0 10px;
  color: #37352f;
  font-size: 16px;
  font-weight: 700;
}

.diagram-card {
  margin: 8px 0 12px;
  padding: 14px;
  border: 1px solid #ececec;
  border-radius: 8px;
  background: #f7f7f8;
}

.diagram-card img {
  display: block;
  width: 100%;
  max-width: 100%;
  border-radius: 8px;
}

.source-list {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 12px;
  padding-top: 10px;
  border-top: 1px dashed #d9d9de;
}

.video {
  width: 100%;
  margin-top: 12px;
  border-radius: 8px;
}

.composer {
  position: sticky;
  bottom: 0;
  display: grid;
  gap: 10px;
  padding-top: 8px;
  background: #ffffff;
}

.input-line {
  align-items: center;
}

.input-line .el-input {
  flex: 1;
}

.input-line :deep(.el-textarea__inner) {
  min-height: 48px !important;
  padding: 13px 16px;
  border-radius: 24px;
  line-height: 1.5;
  resize: none;
}

.input-line .el-button {
  min-width: 72px;
  height: 48px;
  border-radius: 24px;
}

@keyframes dot-breathe {
  0%,
  80%,
  100% {
    opacity: 0.35;
  }
  40% {
    opacity: 1;
  }
}
</style>
