<template>
  <div class="page resource-page">
    <el-card class="panel request-card">
      <template #header>
        <div class="header-line">
          <div>
            <strong>个性化学习资源生成</strong>
            <p>读取当前画像后，系统会实时生成六类资源，并按栏目分开展示。</p>
          </div>
          <el-button type="primary" size="large" :loading="loading" @click="generate">
            {{ resources.length ? "重新生成资源" : "开始生成资源" }}
          </el-button>
        </div>
      </template>

      <el-form :model="requestForm" label-position="top" class="request-form">
        <el-form-item label="专业">
          <el-input v-model="requestForm.major" />
        </el-form-item>
        <el-form-item label="课程">
          <el-input v-model="requestForm.course" />
        </el-form-item>
        <el-form-item label="本次学习需求" class="need-field">
          <el-input
            v-model="requestForm.learning_need"
            type="textarea"
            :rows="2"
            placeholder="例如：希望通过图文讲解、习题和案例掌握软件工程中的需求分析与总体设计。"
          />
        </el-form-item>
      </el-form>
    </el-card>

    <el-card v-if="loading || generationProgress > 0" class="panel progress-panel">
      <template #header>
        <div class="header-line">
          <span>实时生成进度</span>
          <el-tag type="primary" effect="dark">{{ generationProgress }}%</el-tag>
        </div>
      </template>

      <el-progress
        :percentage="generationProgress"
        :status="generationProgress === 100 && !loading ? 'success' : undefined"
        striped
        striped-flow
      />

      <div class="progress-copy">
        <strong>{{ currentProgressTitle }}</strong>
        <p>{{ currentProgressHint }}</p>
      </div>

      <div class="stage-grid">
        <div v-for="stage in progressStages" :key="stage.key" class="stage-card" :class="stageClass(stage)">
          <b>{{ stage.index }}</b>
          <strong>{{ stage.title }}</strong>
          <span>{{ stage.desc }}</span>
        </div>
      </div>
    </el-card>

    <el-card class="panel catalog-panel">
      <template #header>
        <div class="header-line">
          <div>
            <strong>六智能体协作栏目</strong>
            <p>点击不同栏目，查看该类资源的结果、配图和依据来源。</p>
          </div>
          <el-tag :type="displayMode === 'current' ? 'success' : displayMode === 'history' ? 'warning' : 'info'">
            {{ displayModeLabel }}
          </el-tag>
        </div>
      </template>

      <div class="catalog-tabs">
        <button
          v-for="tab in resourceTabs"
          :key="tab.key"
          class="catalog-tab"
          :class="{ active: activeTab === tab.key }"
          @click="activeTab = tab.key"
        >
          <span>{{ tab.label }}</span>
          <small>{{ tabCount(tab.key) }}</small>
        </button>
      </div>
    </el-card>

    <el-card v-if="plan.core_topic" class="panel plan-card">
      <template #header>资源规划摘要</template>
      <el-descriptions :column="3" border>
        <el-descriptions-item label="核心主题">{{ plan.core_topic }}</el-descriptions-item>
        <el-descriptions-item label="目标水平">{{ plan.target_level || "按画像自动推断" }}</el-descriptions-item>
        <el-descriptions-item label="偏好形式">{{ plan.preferred_style || "按画像自动推断" }}</el-descriptions-item>
      </el-descriptions>
    </el-card>

    <el-card v-if="trace.length" class="panel trace-card">
      <template #header>
        <div class="header-line">
          <span>协作轨迹</span>
          <el-tag>{{ traceId || "未生成" }}</el-tag>
        </div>
      </template>
      <el-timeline>
        <el-timeline-item
          v-for="(event, index) in trace"
          :key="`${event.agent}-${index}`"
          :type="eventType(event.status)"
          :timestamp="`${event.duration_ms || 0} ms${event.retry_count ? ` · 重试 ${event.retry_count} 次` : ''}`"
        >
          <strong>{{ event.agent }}</strong>
          <span class="trace-status">{{ event.status }}</span>
          <p>{{ event.message }}</p>
        </el-timeline-item>
      </el-timeline>
    </el-card>

    <el-empty
      v-if="!filteredResources.length && !loading"
      class="empty-panel panel"
      :description="resources.length ? '当前栏目还没有对应资源。' : '当前还没有学习资源，请先点击上方按钮开始生成。'"
    >
      <el-button type="primary" @click="generate">立即生成资源</el-button>
    </el-empty>

    <div v-else class="cards">
      <el-card v-for="item in filteredResources" :key="`${item.id || item.resource_type}-${item.title}`" shadow="hover" class="resource-card">
        <template #header>
          <div class="resource-header">
            <div class="resource-head-copy">
              <el-tag effect="dark">{{ typeLabel(item.resource_type) }}</el-tag>
              <strong>{{ item.title }}</strong>
            </div>
            <el-progress type="circle" :width="56" :stroke-width="6" :percentage="qualityScore(item)" />
          </div>
        </template>

        <el-alert class="personalization" type="success" :closable="false" show-icon>
          <template #title><strong>为什么这样生成</strong></template>
          {{ item.personalization || "系统根据当前学生画像、知识短板和课程上下文自动组织该类资源。" }}
        </el-alert>

        <div v-if="item.resource_type === 'mindmap'" class="mindmap-shell">
          <div class="mindmap-toolbar">
            <span>个性化知识导图</span>
            <el-tag type="info" size="small">Mermaid</el-tag>
          </div>
          <div class="mindmap" v-html="mindmapSvgs[item.id || item.resource_type]"></div>
        </div>

        <template v-else-if="item.resource_type === 'video'">
          <video v-if="playableVideo(item)" controls :src="videoUrl(item)" class="video"></video>
          <div class="markdown-body" v-html="renderMarkdown(item.content)"></div>
        </template>

        <div v-else class="markdown-body" v-html="renderMarkdown(item.content)"></div>

        <div v-if="resourceImages(item).length" class="image-gallery">
          <div class="image-title">相关图片</div>
          <a v-for="path in resourceImages(item)" :key="path" :href="imageUrl(path)" target="_blank" class="image-card">
            <img :src="imageUrl(path)" alt="知识库图片" loading="lazy" />
            <span>{{ shortImageName(path) }}</span>
          </a>
        </div>

        <el-divider />

        <div class="evidence">
          <div><strong>负责智能体：</strong>{{ item.agent_name || "历史资源" }}</div>
          <div><strong>关联知识点：</strong>{{ knowledgePoints(item).join("、") || "课程核心知识点" }}</div>
          <div class="source-row">
            <strong>参考来源：</strong>
            <el-tag v-for="source in uniqueSources(item.sources)" :key="source" size="small" type="info">{{ source }}</el-tag>
            <el-tag v-if="!uniqueSources(item.sources).length" size="small" type="danger">暂无来源</el-tag>
          </div>
        </div>
      </el-card>
    </div>
  </div>
</template>

<script setup>
import MarkdownIt from "markdown-it";
import mermaid from "mermaid";
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref } from "vue";
import { ElMessage } from "element-plus";
import { activeProfileSessionId, profileApi, resourceApi } from "../api";

const md = new MarkdownIt({ html: false, linkify: true, breaks: true });
const apiBase = import.meta.env.VITE_API_BASE_URL || "http://localhost:5000/api";
const absoluteImagePattern = /([A-Za-z]:\\[^\n\r；;，,]+?\.(?:png|jpg|jpeg|webp|gif))/gi;
const relativeImagePattern = /(images[\\/][^\n\r；;，,]+?\.(?:png|jpg|jpeg|webp|gif))/gi;

mermaid.initialize({
  startOnLoad: false,
  theme: "base",
  securityLevel: "strict",
  themeVariables: {
    background: "#ffffff",
    primaryColor: "#eff6ff",
    primaryTextColor: "#0f172a",
    primaryBorderColor: "#2563eb",
    lineColor: "#60a5fa",
    secondaryColor: "#dbeafe",
    tertiaryColor: "#f8fafc",
    fontFamily: "Microsoft YaHei, PingFang SC, sans-serif",
  },
});

const loading = ref(false);
const displayMode = ref("empty");
const resources = ref([]);
const trace = ref([]);
const traceId = ref("");
const generationProgress = ref(0);
const currentStageIndex = ref(0);
const eventSource = ref(null);
const activeTab = ref("doc");
const plan = reactive({});
const mindmapSvgs = reactive({});
const requestForm = reactive({
  major: "软件工程",
  course: "软件工程",
  learning_need: "希望围绕课程核心知识点生成图文讲解、知识导图、分层习题、拓展阅读、代码案例和视频说明。",
});

const progressStages = [
  { key: "profile", index: "01", title: "读取画像", desc: "合并学生画像和本次学习需求", progress: 12 },
  { key: "retrieve", index: "02", title: "知识检索", desc: "从课程知识库召回可信依据", progress: 28 },
  { key: "plan", index: "03", title: "任务规划", desc: "拆解为六类资源生成任务", progress: 42 },
  { key: "generate", index: "04", title: "并行生成", desc: "六类资源同时产出", progress: 72 },
  { key: "review", index: "05", title: "质量复核", desc: "检查完整性、来源与安全性", progress: 88 },
  { key: "package", index: "06", title: "结果整理", desc: "汇总资源、配图和协作轨迹", progress: 100 },
];

const resourceTabs = [
  { key: "doc", label: "课程讲解文档" },
  { key: "mindmap", label: "个性化思维导图" },
  { key: "quiz", label: "分层练习题" },
  { key: "reading", label: "拓展阅读材料" },
  { key: "code", label: "代码实操案例" },
  { key: "video", label: "多模态视频说明" },
];

const displayModeLabel = computed(() => ({
  current: "当前生成结果",
  history: "历史资源回显",
  empty: "等待生成",
}[displayMode.value] || "等待生成"));

const currentProgressTitle = computed(() => progressStages[currentStageIndex.value]?.title || "等待开始");
const currentProgressHint = computed(() => progressStages[currentStageIndex.value]?.desc || "系统尚未开始生成资源。");
const filteredResources = computed(() => resources.value.filter((item) => item.resource_type === activeTab.value));

function tabCount(type) {
  return resources.value.filter((item) => item.resource_type === type).length;
}

function stageClass(stage) {
  const index = progressStages.findIndex((item) => item.key === stage.key);
  if (generationProgress.value >= stage.progress) return "done";
  if (index === currentStageIndex.value && loading.value) return "running";
  return "pending";
}

function imageUrl(path) {
  return `${apiBase}/knowledge/image?path=${encodeURIComponent(String(path || "").trim())}`;
}

function extractImagePaths(text) {
  const source = String(text || "");
  const matches = [...(source.match(absoluteImagePattern) || []), ...(source.match(relativeImagePattern) || [])];
  return [...new Set(matches.map((item) => item.trim()))];
}

function renderMarkdown(text) {
  let source = String(text || "");
  source = source.replace(absoluteImagePattern, (path) => `\n\n![知识库图片](${imageUrl(path)})\n\n`);
  source = source.replace(relativeImagePattern, (path) => `\n\n![知识库图片](${imageUrl(path)})\n\n`);
  return md.render(source);
}

function stripFences(text) {
  return String(text || "")
    .trim()
    .replace(/^```(?:mermaid|markdown|md|json|text)?\s*/i, "")
    .replace(/```\s*$/i, "")
    .trim();
}

function cleanMindmapLabel(value) {
  const cleaned = String(value || "")
    .replace(/[`"'{}[\]|<>()[\]]/g, "")
    .replace(/[:：]/g, " ")
    .replace(/-->|---|==>|-/g, " ")
    .replace(/[#*_~\\/]/g, " ")
    .replace(/\s+/g, " ")
    .trim()
    .slice(0, 34);
  return cleaned || "知识点";
}

function normalizeMindmapSource(text) {
  const lines = stripFences(text)
    .replace(/::icon\([^)]+\)/g, "")
    .split("\n")
    .map((line) => line.replace(/\t/g, "  ").trimEnd())
    .filter((line) => line.trim() && !line.trim().startsWith("%%"));
  const startIndex = lines.findIndex((line) => /^mindmap\b/i.test(line.trim()));
  if (startIndex < 0) return "";
  const normalized = ["mindmap"];
  for (const line of lines.slice(startIndex + 1)) {
    const raw = line.trim();
    if (!raw || /^```/.test(raw)) continue;
    const leading = line.match(/^\s*/)?.[0].length || 0;
    const depth = Math.max(1, Math.min(5, Math.floor(leading / 2) + 1));
    const label = cleanMindmapLabel(raw.replace(/^[-*+]\s*/, "").replace(/^root\s*/i, ""));
    normalized.push(`${"  ".repeat(depth)}${label}`);
  }
  if (normalized.length < 3) return "";
  return normalized.join("\n");
}

function parseJsonLike(text) {
  const source = stripFences(text);
  try {
    return JSON.parse(source);
  } catch {
    const match = source.match(/\{[\s\S]*\}/);
    if (!match) return null;
    try {
      return JSON.parse(match[0]);
    } catch {
      return null;
    }
  }
}

function extractMindmapSource(text) {
  const source = stripFences(text);
  const mermaidFence = String(text || "").match(/```mermaid\s*([\s\S]*?)```/i);
  if (mermaidFence) return normalizeMindmapSource(mermaidFence[1]);
  const mindmapIndex = source.search(/^mindmap\b/im);
  if (mindmapIndex >= 0) return normalizeMindmapSource(source.slice(mindmapIndex));
  return "";
}

function buildFallbackMindmap(item) {
  const title = cleanMindmapLabel(item.title || "课程知识导图");
  const points = knowledgePoints(item).map(cleanMindmapLabel).filter(Boolean);
  const headings = String(item.content || "")
    .split("\n")
    .map((line) => line.replace(/^#+\s*/, "").replace(/^[-*]\s*/, ""))
    .map(cleanMindmapLabel)
    .filter(Boolean)
    .slice(0, 18);
  const branches = [...new Set([...points, ...headings])].slice(0, 24);
  const primary = branches.length ? branches : ["核心概念", "流程步骤", "方法工具", "易错点", "案例应用"];
  const lines = ["mindmap", `  ${title}`];
  primary.slice(0, 6).forEach((branch, index) => {
    lines.push(`    ${branch}`);
    const details = primary.slice(index * 3 + 6, index * 3 + 9);
    const fallbackDetails = ["定义与作用", "关键输入输出", "常见误区"];
    (details.length ? details : fallbackDetails).slice(0, 3).forEach((detail) => {
      lines.push(`      ${cleanMindmapLabel(detail)}`);
    });
  });
  return lines.join("\n");
}

function buildMindmapSource(item) {
  const direct = extractMindmapSource(item.content);
  if (direct) return direct;
  const parsed = parseJsonLike(item.content);
  if (parsed) {
    const content = parsed.content || parsed.mindmap || parsed.markdown || "";
    const fromJson = extractMindmapSource(content);
    if (fromJson) return fromJson;
    return buildFallbackMindmap({
      ...item,
      title: parsed.title || item.title,
      content: content || item.content,
      knowledge_points: parsed.knowledge_points || item.knowledge_points,
    });
  }
  return buildFallbackMindmap(item);
}

function resourceImages(item) {
  return extractImagePaths([item.content, item.personalization, JSON.stringify(item.metadata || {})].join("\n"));
}

function shortImageName(path) {
  return String(path || "").split(/\\|\//).slice(-2).join(" / ");
}

function typeLabel(type) {
  return ({
    doc: "课程讲解文档",
    quiz: "分层练习题",
    reading: "拓展阅读材料",
    mindmap: "知识思维导图",
    code: "代码实操案例",
    video: "视频说明",
  }[type] || type);
}

function eventType(status) {
  return ({ completed: "success", warning: "warning", failed: "danger" }[status] || "primary");
}

function qualityObject(item) {
  return item.quality || item.metadata?.quality || {};
}

function qualityScore(item) {
  return Number(item.quality_score || qualityObject(item).total || 0);
}

function knowledgePoints(item) {
  if (Array.isArray(item.knowledge_points)) return item.knowledge_points;
  try {
    return JSON.parse(item.knowledge_points || "[]");
  } catch {
    return [];
  }
}

function uniqueSources(sources = []) {
  return [...new Set((sources || []).map((item) => item.source || item.source_name).filter(Boolean))];
}

function videoUrl(item) {
  return item.video_url || item.metadata?.video_url || "";
}

function playableVideo(item) {
  const url = videoUrl(item);
  return /^https?:\/\//.test(url) && !url.includes("example.com");
}

function closeEventSource() {
  if (eventSource.value) {
    eventSource.value.close();
    eventSource.value = null;
  }
}

function progressForAgent(agentName, status) {
  const stageMap = {
    ProfileAgent: 12,
    RetrieveAgent: 28,
    PlannerAgent: 42,
    DocumentAgent: 72,
    QuizAgent: 72,
    ReadingAgent: 72,
    MindMapAgent: 72,
    CodeAgent: 72,
    VideoAgent: 72,
    QualityAgent: 88,
    SafetyAgent: 94,
    PackagerAgent: 100,
  };
  const target = stageMap[agentName] || generationProgress.value;
  return status === "running" ? Math.max(generationProgress.value, Math.max(5, target - 8)) : Math.max(generationProgress.value, target);
}

function applyAgentEvent(event) {
  if (!event?.agent) return;
  traceId.value = event.trace_id || traceId.value;
  if (event.status !== "running") trace.value = [...trace.value, event];
  generationProgress.value = progressForAgent(event.agent, event.status);
  const index = progressStages.findIndex((stage) => generationProgress.value <= stage.progress);
  currentStageIndex.value = index === -1 ? progressStages.length - 1 : index;
}

function finishProgress(finalProgress = 100) {
  closeEventSource();
  generationProgress.value = finalProgress;
  currentStageIndex.value = progressStages.length - 1;
}

async function safeRenderMindmap(key, source) {
  try {
    await mermaid.parse(source);
    const id = `mindmap-${key}-${Date.now()}`.replace(/[^a-zA-Z0-9-]/g, "");
    const { svg } = await mermaid.render(id, source);
    mindmapSvgs[key] = svg;
    return true;
  } catch {
    return false;
  }
}

async function renderMindmaps() {
  await nextTick();
  for (const item of resources.value.filter((entry) => entry.resource_type === "mindmap")) {
    const key = item.id || item.resource_type;
    const source = buildMindmapSource(item);
    if (source && await safeRenderMindmap(key, source)) continue;

    const safeSource = buildFallbackMindmap({ ...item, content: "", knowledge_points: knowledgePoints(item) });
    if (await safeRenderMindmap(`fallback-${key}`, safeSource)) {
      mindmapSvgs[key] = mindmapSvgs[`fallback-${key}`];
      delete mindmapSvgs[`fallback-${key}`];
    } else {
      mindmapSvgs[key] = `<div class="mindmap-error">思维导图渲染失败，请重新生成当前资源。</div>`;
    }
  }
}

function resetRunArtifacts() {
  trace.value = [];
  traceId.value = "";
  generationProgress.value = 0;
  currentStageIndex.value = 0;
  Object.keys(plan).forEach((key) => delete plan[key]);
}

async function loadResources() {
  resetRunArtifacts();
  const [resourceRes, profileRes] = await Promise.all([resourceApi.list(), profileApi.get()]);
  if (resourceRes.code === 200) {
    resources.value = resourceRes.data || [];
    displayMode.value = resources.value.length ? "history" : "empty";
  } else {
    resources.value = [];
    displayMode.value = "empty";
    ElMessage.warning(resourceRes.msg || "历史资源加载失败，可以直接重新生成。");
  }

  if (profileRes.code === 200) {
    if (profileRes.data?.major) requestForm.major = profileRes.data.major;
    if (profileRes.data?.target_course) requestForm.course = profileRes.data.target_course;
    if (profileRes.data?.study_goal) requestForm.learning_need = profileRes.data.study_goal;
  }

  if (!resources.value.find((item) => item.resource_type === activeTab.value) && resources.value.length) {
    activeTab.value = resources.value[0].resource_type;
  }
  await renderMindmaps();
}

function streamUrl() {
  const params = new URLSearchParams();
  const token = localStorage.getItem("token") || "";
  if (token) params.set("token", token);
  const sessionId = activeProfileSessionId();
  if (sessionId) params.set("profile_session_id", sessionId);
  Object.entries(requestForm).forEach(([key, value]) => {
    if (value !== undefined && value !== null && String(value).trim()) params.set(key, String(value));
  });
  return `${apiBase}/resource/generate/stream?${params.toString()}`;
}

function handleStreamResult(payload) {
  const result = payload.result || {};
  resources.value = result.resource_list || [];
  trace.value = result.trace || trace.value;
  traceId.value = result.trace_id || traceId.value;
  Object.keys(plan).forEach((key) => delete plan[key]);
  Object.assign(plan, result.plan || {});
  displayMode.value = "current";
  if (!resources.value.find((item) => item.resource_type === activeTab.value) && resources.value.length) {
    activeTab.value = resources.value[0].resource_type;
  }
  finishProgress(100);
  loading.value = false;
  renderMindmaps();
  ElMessage.success("六类资源生成完成。");
}

function handleStreamError(payload) {
  finishProgress(Math.max(generationProgress.value, 60));
  loading.value = false;
  displayMode.value = resources.value.length ? "history" : "empty";
  const detail = payload?.error ? `：${payload.error}` : "";
  ElMessage.error(`${payload?.message || "资源生成失败"}${detail}`);
}

async function generate() {
  loading.value = true;
  displayMode.value = "current";
  resetRunArtifacts();
  finishProgress(0);
  generationProgress.value = 5;
  currentStageIndex.value = 0;

  const source = new EventSource(streamUrl());
  eventSource.value = source;
  source.addEventListener("agent", (event) => applyAgentEvent(JSON.parse(event.data || "{}")));
  source.addEventListener("start", (event) => {
    const payload = JSON.parse(event.data || "{}");
    traceId.value = payload.trace_id || traceId.value;
    generationProgress.value = Math.max(generationProgress.value, 5);
  });
  source.addEventListener("result", (event) => handleStreamResult(JSON.parse(event.data || "{}")));
  source.addEventListener("error", (event) => {
    if (event.data) {
      handleStreamError(JSON.parse(event.data || "{}"));
    } else if (loading.value) {
      handleStreamError({ message: "SSE 连接中断，请确认后端服务正常运行" });
    }
  });
  source.onerror = () => {
    if (loading.value) handleStreamError({ message: "SSE 连接中断，请确认后端服务正常运行" });
  };
}

onMounted(loadResources);
onBeforeUnmount(() => closeEventSource());
</script>

<style scoped>
.resource-page {
  display: grid;
  gap: 18px;
}

.header-line,
.resource-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 18px;
}

.header-line p {
  margin: 6px 0 0;
  color: #64748b;
}

.request-form {
  display: grid;
  grid-template-columns: 1fr 1fr 2fr;
  gap: 16px;
}

.progress-panel {
  border-color: rgba(37, 99, 235, 0.22);
  background: linear-gradient(135deg, #ffffff, #f8fbff);
}

.progress-copy {
  margin-top: 14px;
}

.progress-copy strong {
  display: block;
  color: #0f172a;
}

.progress-copy p {
  margin: 6px 0 0;
  color: #64748b;
  line-height: 1.7;
}

.stage-grid {
  display: grid;
  grid-template-columns: repeat(6, minmax(0, 1fr));
  gap: 12px;
  margin-top: 18px;
}

.stage-card {
  min-height: 112px;
  padding: 14px;
  border: 1px solid #e2e8f0;
  border-radius: 16px;
  background: #fff;
  color: #64748b;
}

.stage-card b {
  display: block;
  color: #94a3b8;
  font-size: 18px;
}

.stage-card strong {
  display: block;
  margin: 8px 0 6px;
  color: #0f172a;
}

.stage-card span {
  font-size: 12px;
  line-height: 1.6;
}

.stage-card.running {
  border-color: #60a5fa;
  background: #eff6ff;
  box-shadow: 0 12px 32px rgba(37, 99, 235, 0.12);
}

.stage-card.done {
  border-color: #86efac;
  background: #f0fdf4;
}

.catalog-tabs {
  display: grid;
  grid-template-columns: repeat(6, minmax(0, 1fr));
  gap: 10px;
}

.catalog-tab {
  display: grid;
  gap: 6px;
  padding: 14px 12px;
  border: 1px solid #dbeafe;
  border-radius: 16px;
  background: #f8fbff;
  color: #1e40af;
  cursor: pointer;
  transition: 0.18s ease;
}

.catalog-tab span {
  font-weight: 700;
}

.catalog-tab small {
  color: #64748b;
}

.catalog-tab.active {
  border-color: #60a5fa;
  background: linear-gradient(180deg, #ffffff 0%, #eaf4ff 100%);
  box-shadow: 0 10px 22px rgba(37, 99, 235, 0.1);
}

.empty-panel {
  padding: 26px;
  background: rgba(255, 255, 255, 0.9);
}

.cards {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 18px;
}

.resource-card {
  min-width: 0;
}

.resource-head-copy {
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 0;
}

.resource-head-copy strong {
  color: #0f172a;
  word-break: break-word;
}

.personalization {
  margin-bottom: 14px;
}

.markdown-body {
  max-height: 650px;
  overflow: auto;
  line-height: 1.8;
}

.markdown-body :deep(pre) {
  overflow: auto;
  padding: 16px;
  border-radius: 12px;
  background: #0f172a;
  color: #e2e8f0;
}

.markdown-body :deep(img) {
  display: block;
  max-width: 100%;
  max-height: 360px;
  object-fit: contain;
  margin: 14px auto;
  border-radius: 8px;
  border: 1px solid #dbeafe;
  background: #fff;
}

.mindmap-shell {
  min-height: 620px;
  overflow: auto;
  border: 1px solid #bfdbfe;
  border-radius: 8px;
  background: #ffffff;
  box-shadow: inset 0 0 0 1px rgba(59, 130, 246, 0.06), 0 14px 36px rgba(30, 64, 175, 0.08);
}

.mindmap-toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 14px;
  border-bottom: 1px solid #dbeafe;
  color: #1d4ed8;
  font-weight: 700;
  background: linear-gradient(90deg, #eff6ff 0%, #ffffff 100%);
}

.mindmap {
  min-width: 1280px;
  min-height: 560px;
  overflow: auto;
  padding: 42px;
  display: grid;
  place-items: center;
  background-color: #fbfdff;
  background-image: linear-gradient(#e6f0ff 1px, transparent 1px), linear-gradient(90deg, #e6f0ff 1px, transparent 1px);
  background-size: 28px 28px;
}

.mindmap :deep(svg) {
  max-width: none;
  min-width: 980px;
  height: auto;
  filter: drop-shadow(0 10px 22px rgba(37, 99, 235, 0.14));
}

.mindmap :deep(.mindmap-node rect),
.mindmap :deep(.node rect),
.mindmap :deep(.node circle),
.mindmap :deep(.node ellipse),
.mindmap :deep(.node polygon) {
  fill: #eff6ff !important;
  stroke: #60a5fa !important;
  stroke-width: 1.4px !important;
}

.mindmap :deep(text) {
  fill: #0f172a !important;
  font-size: 15px !important;
  font-weight: 600 !important;
}

.mindmap :deep(path) {
  stroke: #60a5fa !important;
}

.mindmap-error {
  padding: 24px;
  color: #1d4ed8;
  font-weight: 700;
  background: #eff6ff;
  border: 1px dashed #93c5fd;
  border-radius: 8px;
}

.image-gallery {
  margin-top: 16px;
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(160px, 1fr));
  gap: 12px;
}

.image-title {
  grid-column: 1 / -1;
  font-weight: 700;
  color: #1d4ed8;
}

.image-card {
  display: grid;
  gap: 8px;
  padding: 8px;
  border: 1px solid #bfdbfe;
  border-radius: 8px;
  background: #fff;
  color: #475569;
  text-decoration: none;
}

.image-card img {
  width: 100%;
  aspect-ratio: 4 / 3;
  object-fit: contain;
  background: #f8fafc;
  border-radius: 6px;
}

.image-card span {
  font-size: 12px;
  word-break: break-all;
}

.video {
  width: 100%;
  max-height: 420px;
  border-radius: 14px;
  background: #0f172a;
}

.trace-status {
  margin-left: 10px;
  color: #64748b;
  font-size: 12px;
  text-transform: uppercase;
}

.el-timeline-item p {
  margin: 6px 0 0;
  color: #475569;
}

.evidence {
  display: grid;
  gap: 8px;
  color: #475569;
  font-size: 13px;
}

.source-row {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px;
}

@media (max-width: 1200px) {
  .stage-grid,
  .catalog-tabs {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 1000px) {
  .cards,
  .request-form {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 700px) {
  .stage-grid,
  .catalog-tabs {
    grid-template-columns: 1fr;
  }
}
</style>
