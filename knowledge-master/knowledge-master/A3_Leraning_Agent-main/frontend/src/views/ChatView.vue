<template>
  <div class="page chat-page">
    <el-card class="panel chat-card">
      <template #header>
        <div class="header-line">
          <div>
            <strong>多模态智能辅导</strong>
            <p>基于学生画像、本地知识库和大模型，提供文字答疑、图解说明、教材配图和短视频脚本。</p>
          </div>
          <div class="header-actions">
            <el-switch v-model="needVideo" active-text="生成短视频" />
            <el-button plain @click="clearMessages">清空记录</el-button>
          </div>
        </div>
      </template>

      <div class="chat-window">
        <div v-for="(item, index) in messages" :key="index" :class="['bubble', item.role]">
          <div class="bubble-title">{{ item.role === "user" ? "我" : "智能辅导教师" }}</div>
          <div class="markdown-body" v-html="renderMarkdown(item.content)"></div>

          <div v-if="item.diagram" class="diagram-card">
            <div class="section-title">图解说明</div>
            <div class="diagram" v-html="diagramSvgs[index]"></div>
          </div>

          <div v-if="item.images?.length" class="image-gallery">
            <div class="section-title">教材配图</div>
            <a v-for="image in item.images" :key="image.path" :href="imageUrl(image.path)" target="_blank" class="image-card">
              <img :src="imageUrl(image.path)" alt="教材配图" loading="lazy" />
              <span>{{ image.caption || shortImageName(image.path) }}</span>
            </a>
          </div>

          <div v-if="item.videoScript" class="script-card">
            <div class="section-title">短视频讲解脚本</div>
            <div class="markdown-body" v-html="renderMarkdown(item.videoScript)"></div>
          </div>

          <video v-if="item.video && isPlayableVideo(item.video)" controls :src="item.video" class="video"></video>

          <div v-if="item.selfCheck?.length" class="list-card">
            <div class="section-title">自测问题</div>
            <ol>
              <li v-for="entry in item.selfCheck" :key="entry">{{ entry }}</li>
            </ol>
          </div>

          <div v-if="item.nextActions?.length" class="list-card">
            <div class="section-title">下一步学习建议</div>
            <ul>
              <li v-for="entry in item.nextActions" :key="entry">{{ entry }}</li>
            </ul>
          </div>

          <div v-if="item.sources?.length" class="source-list">
            <strong>参考来源</strong>
            <el-tag v-for="source in item.sources" :key="`${source.source}-${source.chunk_index}`" size="small">
              {{ source.source }} #{{ source.chunk_index }}
            </el-tag>
          </div>
        </div>
      </div>

      <el-progress v-if="loading" :percentage="progress" striped striped-flow />
      <el-steps v-if="loading" :active="activeStep" finish-status="success" simple>
        <el-step title="检索知识库" />
        <el-step title="生成多模态解答" />
        <el-step title="安全复核" />
      </el-steps>

      <div class="input-line">
        <el-input
          v-model="question"
          type="textarea"
          :rows="3"
          placeholder="请输入软件工程学习问题，例如：瀑布模型为什么不适合需求频繁变化的项目？"
          @keydown.ctrl.enter.prevent="ask"
        />
        <el-button type="primary" :loading="loading" @click="ask">提问</el-button>
      </div>
    </el-card>
  </div>
</template>

<script setup>
import MarkdownIt from "markdown-it";
import mermaid from "mermaid";
import { nextTick, onMounted, ref, watch } from "vue";
import { ElMessage } from "element-plus";
import { chatApi } from "../api";

const STORAGE_KEY = "a3_tutor_messages";
const md = new MarkdownIt({ html: false, linkify: true, breaks: true });
const apiBase = import.meta.env.VITE_API_BASE_URL || "http://localhost:5000/api";

mermaid.initialize({
  startOnLoad: false,
  theme: "base",
  securityLevel: "strict",
  flowchart: {
    curve: "basis",
    htmlLabels: true,
    nodeSpacing: 38,
    rankSpacing: 58,
  },
  themeVariables: {
    background: "#ffffff",
    primaryColor: "#eff6ff",
    primaryTextColor: "#0f172a",
    primaryBorderColor: "#3b82f6",
    lineColor: "#60a5fa",
    secondaryColor: "#dbeafe",
    tertiaryColor: "#f8fafc",
    fontFamily: "Microsoft YaHei, PingFang SC, sans-serif",
  },
});

const welcomeMessage = {
  role: "assistant",
  content: "我是多模态智能辅导教师。你可以问软件工程课程中的概念、流程、图示、案例或练习题，我会结合本地知识库给出文字解答、图解说明、教材配图和学习建议。",
};

const question = ref("瀑布模型为什么不适合需求频繁变化的项目？");
const needVideo = ref(false);
const loading = ref(false);
const progress = ref(0);
const activeStep = ref(0);
const diagramSvgs = ref({});
const messages = ref([welcomeMessage]);

onMounted(async () => {
  restoreMessages();
  await renderAllDiagrams();
});

watch(
  messages,
  () => {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(messages.value));
  },
  { deep: true }
);

function restoreMessages() {
  try {
    const saved = JSON.parse(localStorage.getItem(STORAGE_KEY) || "[]");
    if (Array.isArray(saved) && saved.length) {
      messages.value = saved;
    }
  } catch {
    messages.value = [welcomeMessage];
  }
}

function clearMessages() {
  messages.value = [welcomeMessage];
  diagramSvgs.value = {};
  localStorage.removeItem(STORAGE_KEY);
}

function imageUrl(path) {
  return `${apiBase}/knowledge/image?path=${encodeURIComponent(String(path || "").trim())}`;
}

function shortImageName(path) {
  return String(path || "").split(/\\|\//).slice(-2).join(" / ");
}

function renderMarkdown(text) {
  return md.render(String(text || ""));
}

function isPlayableVideo(text) {
  return /^https?:\/\//.test(String(text || "")) && !String(text).includes("example.com") && !String(text).trim().startsWith("{");
}

function normalizeDiagram(source, title = "智能辅导图解") {
  const text = String(source || "").replace(/^```(?:mermaid)?/i, "").replace(/```$/i, "").trim();
  if (/^(flowchart|graph|mindmap)\b/i.test(text)) return text;
  return [
    "flowchart LR",
    `  A((${title}))`,
    "  A --> B[问题定位]",
    "  B --> C[知识库依据]",
    "  C --> D[通俗解释]",
    "  D --> E[易错点提醒]",
    "  E --> F[练习建议]",
  ].join("\n");
}

async function renderDiagram(index, diagram) {
  await nextTick();
  try {
    const id = `tutor-diagram-${index}-${Date.now()}`.replace(/[^a-zA-Z0-9-]/g, "");
    const { svg } = await mermaid.render(id, normalizeDiagram(diagram));
    diagramSvgs.value[index] = svg;
  } catch {
    diagramSvgs.value[index] = `<pre>${String(diagram || "图解生成失败")}</pre>`;
  }
}

async function renderAllDiagrams() {
  await Promise.all(messages.value.map((item, index) => (item.diagram ? renderDiagram(index, item.diagram) : null)));
}

function typewriter(target, fullText) {
  target.content = "";
  let index = 0;
  const timer = setInterval(() => {
    target.content += fullText.slice(index, index + 8);
    index += 8;
    if (index >= fullText.length) clearInterval(timer);
  }, 16);
}

async function ask() {
  if (!question.value.trim()) return;
  loading.value = true;
  progress.value = 10;
  activeStep.value = 0;
  messages.value.push({ role: "user", content: question.value });
  const assistantMsg = {
    role: "assistant",
    content: "正在检索本地知识库，并生成文字解答、图解说明和学习建议...",
    sources: [],
    images: [],
  };
  messages.value.push(assistantMsg);
  const assistantIndex = messages.value.length - 1;
  const timer = setInterval(() => {
    progress.value = Math.min(progress.value + 7, 94);
    activeStep.value = progress.value > 65 ? 2 : progress.value > 35 ? 1 : 0;
  }, 500);
  try {
    const res = await chatApi.answer({ question: question.value, need_video: needVideo.value });
    if (res.code === 200) {
      assistantMsg.sources = res.data.sources || [];
      assistantMsg.images = res.data.images || [];
      assistantMsg.diagram = res.data.diagram || "";
      assistantMsg.video = res.data.video_url;
      assistantMsg.videoScript = res.data.video_script;
      assistantMsg.selfCheck = res.data.self_check || [];
      assistantMsg.nextActions = res.data.next_actions || [];
      typewriter(assistantMsg, res.data.answer);
      await renderDiagram(assistantIndex, assistantMsg.diagram);
      question.value = "";
    } else {
      assistantMsg.content = res.msg || "智能辅导失败";
      ElMessage.error(res.msg);
    }
  } finally {
    clearInterval(timer);
    activeStep.value = 3;
    progress.value = 100;
    loading.value = false;
  }
}
</script>

<style scoped>
.chat-page { display: grid; }
.chat-card :deep(.el-card__body) { display: flex; height: calc(100vh - 190px); flex-direction: column; gap: 14px; }
.header-line, .input-line { display: flex; align-items: center; gap: 14px; justify-content: space-between; }
.header-actions { display: flex; align-items: center; gap: 12px; }
.header-line p { margin: 6px 0 0; color: #64748b; font-weight: 400; }
.chat-window { flex: 1; overflow: auto; padding: 18px; border-radius: 18px; background: #f8fafc; }
.bubble { max-width: 88%; margin-bottom: 14px; padding: 14px 16px; border-radius: 16px; }
.bubble-title { margin-bottom: 8px; font-size: 12px; color: #64748b; font-weight: 700; }
.bubble.assistant { background: #fff; border: 1px solid #dbeafe; }
.bubble.user { margin-left: auto; background: #dbeafe; }
.markdown-body { line-height: 1.75; }
.diagram-card, .script-card, .list-card { margin-top: 14px; padding: 14px; border: 1px solid #bfdbfe; border-radius: 8px; background: #ffffff; }
.section-title { margin-bottom: 10px; color: #1d4ed8; font-weight: 700; }
.diagram { min-width: 720px; min-height: 260px; overflow: auto; padding: 16px; background-image: linear-gradient(#eff6ff 1px, transparent 1px), linear-gradient(90deg, #eff6ff 1px, transparent 1px); background-size: 28px 28px; border-radius: 8px; }
.diagram :deep(svg) { max-width: none; height: auto; filter: drop-shadow(0 8px 18px rgba(37, 99, 235, 0.12)); }
.diagram :deep(.node rect), .diagram :deep(.node circle), .diagram :deep(.node polygon), .diagram :deep(.node path) { fill: #eff6ff !important; stroke: #60a5fa !important; stroke-width: 1.5px !important; }
.diagram :deep(.cluster rect) { fill: rgba(239, 246, 255, 0.64) !important; stroke: #bfdbfe !important; }
.diagram :deep(text) { fill: #0f172a !important; font-family: "Microsoft YaHei", "PingFang SC", sans-serif !important; font-weight: 600; }
.diagram :deep(path), .diagram :deep(line), .diagram :deep(.edgePath path) { stroke: #60a5fa !important; stroke-width: 1.5px !important; }
.diagram :deep(.arrowheadPath) { fill: #60a5fa !important; stroke: #60a5fa !important; }
.image-gallery { margin-top: 14px; display: grid; grid-template-columns: repeat(auto-fill, minmax(160px, 1fr)); gap: 12px; }
.image-card { display: grid; gap: 8px; padding: 8px; border: 1px solid #bfdbfe; border-radius: 8px; color: #475569; text-decoration: none; }
.image-card img { width: 100%; aspect-ratio: 4 / 3; object-fit: contain; background: #f8fafc; border-radius: 6px; }
.image-card span { font-size: 12px; word-break: break-all; }
.source-list { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 12px; padding-top: 10px; border-top: 1px dashed #cbd5e1; }
.video { width: 100%; margin-top: 12px; border-radius: 8px; background: #0f172a; }
ol, ul { margin: 0; padding-left: 20px; line-height: 1.8; }
@media (max-width: 900px) { .header-line, .input-line, .header-actions { align-items: stretch; flex-direction: column; } .bubble { max-width: 100%; } }
</style>
