<template>
  <div class="page chat-page">
    <el-card class="panel chat-card">
      <template #header>
        <div class="header-line">
          <span>多模态智能答疑</span>
          <div class="header-actions">
            <el-tag v-if="loading" type="warning">生成中，切换模块不会中断</el-tag>
            <el-button size="small" :disabled="loading" @click="clearHistory">清空历史</el-button>
            <el-switch v-model="needVideo" active-text="生成短视频" />
          </div>
        </div>
      </template>
      <div class="chat-window">
        <div v-for="(item, index) in messages" :key="`${item.role}-${index}`" :class="['bubble', item.role]">
          <div class="markdown-body" v-html="renderAnswerMarkdown(item)"></div>
          <figure v-if="item.diagram_image" class="diagram-card">
            <img :src="item.diagram_image" alt="图解知识图" />
            <figcaption>图解知识图</figcaption>
          </figure>
          <div v-if="item.sources?.length" class="source-list">
            <strong>参考来源</strong>
            <el-tag v-for="source in item.sources" :key="`${source.source}-${source.chunk_index}`" size="small">
              {{ source.source }} #{{ source.chunk_index }}
            </el-tag>
          </div>
          <video v-if="item.video && isPlayableVideo(item.video)" controls :src="item.video" class="video"></video>
        </div>
      </div>
      <el-progress v-if="loading" :percentage="progress" striped striped-flow />
      <el-steps v-if="loading" :active="activeStep" finish-status="success" simple>
        <el-step title="检索知识库" />
        <el-step title="生成回答" />
        <el-step title="安全复核" />
      </el-steps>
      <div class="input-line">
        <el-input v-model="question" type="textarea" :rows="3" placeholder="请输入人工智能导论课程问题，例如：什么是监督学习？" />
        <el-button type="primary" :loading="loading" @click="ask">提问</el-button>
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
const WELCOME_MESSAGE = { role: "assistant", content: "我是软件工程课程多模态答疑助手，会先检索课程知识库，再基于大模型生成回答，并进行防幻觉复核。" };
const STORAGE_PREFIX = "a3_tutor_chat_";
const chatState = reactive({
  sessionId: "",
  question: "软件工程中需求分析和总体设计有什么区别？",
  needVideo: false,
  loading: false,
  progress: 0,
  activeStep: 0,
  messages: [WELCOME_MESSAGE],
  pendingPromise: null,
  timer: null,
  loaded: false,
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
    const cleaned = cleanMessages(data.messages || []);
    chatState.messages = cleaned.length ? cleaned : [WELCOME_MESSAGE];
    chatState.question = data.question || chatState.question;
    chatState.needVideo = Boolean(data.needVideo);
    chatState.loading = Boolean(data.loading && chatState.pendingPromise);
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
  const hasLocal = loadLocal(sessionId);
  try {
    const res = await chatApi.history();
    if (res.code === 200 && Array.isArray(res.data?.messages) && res.data.messages.length && !chatState.loading) {
      const cleaned = cleanMessages(res.data.messages);
      chatState.messages = cleaned.length ? cleaned : [WELCOME_MESSAGE];
      saveLocal();
    } else if (!hasLocal && !chatState.messages.length) {
      chatState.messages = [WELCOME_MESSAGE];
    }
  } catch {
    if (!hasLocal) chatState.messages = [WELCOME_MESSAGE];
  } finally {
    chatState.loaded = true;
  }
}

function renderMarkdown(text) {
  return md.render(normalizeMarkdown(text));
}

function removeDiagramText(text) {
  const source = normalizeMarkdown(text);
  return source
    .replace(/\n?##\s*二[、.．]\s*图解说明[\s\S]*?(?=\n##\s*三[、.．]\s*易错点|\n##\s*三|\n#\s*三|$)/, "\n\n")
    .trim();
}

function renderAnswerMarkdown(item) {
  if (item?.diagram_image) return md.render(removeDiagramText(item.content));
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
    if (role === "assistant" && !content) continue;
    if (cleaned.length && cleaned[cleaned.length - 1].role === role && cleaned[cleaned.length - 1].content === content) continue;
    cleaned.push({ ...item, role, content });
  }
  return cleaned.length ? cleaned : [WELCOME_MESSAGE];
}

function normalizeMarkdown(text) {
  let source = String(text || "").trim();
  const fenced = source.match(/^```(?:markdown|md|text)?\s*([\s\S]*?)\s*```$/i);
  if (fenced) source = fenced[1].trim();
  source = source
    .replace(/^\s*```(?:markdown|md|text|mermaid)?\s*$/gim, "")
    .replace(/^\s*```\s*$/gm, "");
  source = source
    .split("\n")
    .filter((line) => !/^[\s|+\-_=]{8,}$/.test(line))
    .map((line) => (line.startsWith("    ") && !line.startsWith("        ") ? line.slice(4) : line))
    .join("\n");
  return source.trim();
}

function typewriter(target, fullText) {
  return new Promise((resolve) => {
    target.content = "";
    let index = 0;
    const timer = setInterval(() => {
      target.content += fullText.slice(index, index + 6);
      index += 6;
      saveLocal();
      if (index >= fullText.length) {
        target.content = fullText;
        saveLocal();
        clearInterval(timer);
        resolve();
      }
    }, 18);
  });
}

async function ask() {
  if (!chatState.question.trim() || chatState.loading) return;
  const askedQuestion = chatState.question;
  const sessionId = activeProfileSessionId();
  const historyBeforeQuestion = cleanMessages(chatState.messages);
  chatState.sessionId = sessionId;
  chatState.loading = true;
  chatState.progress = 10;
  chatState.activeStep = 0;
  chatState.messages.push({ role: "user", content: askedQuestion });
  const assistantMsg = { role: "assistant", content: "正在检索课程知识库并生成可信回答...", sources: [] };
  chatState.messages.push(assistantMsg);
  chatState.question = "";
  saveLocal();
  if (chatState.timer) clearInterval(chatState.timer);
  chatState.timer = setInterval(() => {
    chatState.progress = Math.min(chatState.progress + 7, 94);
    chatState.activeStep = chatState.progress > 65 ? 2 : chatState.progress > 35 ? 1 : 0;
    saveLocal();
  }, 500);
  const requestBody = { question: askedQuestion, need_video: chatState.needVideo, messages: historyBeforeQuestion };
  chatState.pendingPromise = chatApi.answer(requestBody);
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
      ElMessage.error(res.msg);
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
    if (nextSession === previousSession) return;
    if (chatState.loading) {
      saveLocal();
      return;
    }
    await loadHistory();
  }
);
</script>

<style scoped>
.chat-page {
  display: grid;
}

.chat-card :deep(.el-card__body) {
  display: flex;
  height: calc(100vh - 190px);
  flex-direction: column;
  gap: 14px;
}

.header-line,
.input-line {
  display: flex;
  align-items: center;
  gap: 14px;
  justify-content: space-between;
}

.header-actions {
  display: flex;
  align-items: center;
  gap: 12px;
}

.chat-window {
  flex: 1;
  overflow: auto;
  padding: 18px;
  border-radius: 18px;
  background: #f8fafc;
}

.bubble {
  max-width: 78%;
  margin-bottom: 14px;
  padding: 14px 16px;
  border-radius: 16px;
}

.bubble.assistant {
  background: #fff;
  border: 1px solid #dbeafe;
}

.bubble.user {
  margin-left: auto;
  background: #dbeafe;
}

.markdown-body :deep(h1),
.markdown-body :deep(h2),
.markdown-body :deep(h3) {
  margin: 14px 0 10px;
  color: #0f3a78;
  line-height: 1.35;
}

.markdown-body :deep(h2) {
  padding-left: 12px;
  border-left: 4px solid #3b82f6;
  font-size: 20px;
}

.markdown-body :deep(p) {
  margin: 8px 0;
  line-height: 1.85;
}

.markdown-body :deep(ul),
.markdown-body :deep(ol) {
  margin: 8px 0 12px;
  padding-left: 22px;
}

.markdown-body :deep(li) {
  margin: 6px 0;
  line-height: 1.75;
}

.markdown-body :deep(pre) {
  overflow: auto;
  padding: 14px 16px;
  border: 1px solid #bfdbfe;
  border-radius: 8px;
  background: #f8fbff;
  color: #0f172a;
  white-space: pre-wrap;
}

.markdown-body :deep(code) {
  padding: 2px 6px;
  border-radius: 6px;
  background: #eff6ff;
  color: #1d4ed8;
}

.diagram-card {
  margin: 14px 0 4px;
  padding: 12px;
  border: 1px solid #bfdbfe;
  border-radius: 8px;
  background: linear-gradient(135deg, #f8fbff 0%, #ffffff 100%);
}

.diagram-card img {
  display: block;
  width: 100%;
  max-height: 460px;
  object-fit: contain;
  border-radius: 6px;
  background: #fff;
}

.diagram-card figcaption {
  margin-top: 8px;
  color: #1d4ed8;
  font-size: 13px;
  font-weight: 700;
  text-align: center;
}

.source-list {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 12px;
  padding-top: 10px;
  border-top: 1px dashed #cbd5e1;
}

.video {
  width: 100%;
  margin-top: 12px;
  border-radius: 12px;
}
</style>
