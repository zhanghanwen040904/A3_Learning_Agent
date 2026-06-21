<template>
  <div class="page resource-page">
    <el-card class="panel request-card">
      <template #header>
        <div class="header-line">
          <div>
            <strong>多智能体个性化资源工坊</strong>
            <p>统一读取学生画像，由 PlannerAgent 规划并调度六个专业资源智能体。</p>
          </div>
          <el-button type="primary" size="large" :loading="loading" @click="generate">
            {{ resources.length ? "重新启动六智能体协作" : "启动六智能体协作" }}
          </el-button>
        </div>
      </template>
      <el-form :model="requestForm" label-position="top" class="request-form">
        <el-form-item label="专业"><el-input v-model="requestForm.major" /></el-form-item>
        <el-form-item label="课程"><el-input v-model="requestForm.course" /></el-form-item>
        <el-form-item label="本次学习需求" class="need-field">
          <el-input v-model="requestForm.learning_need" type="textarea" :rows="2" placeholder="例如：希望通过图解和案例掌握需求分析、总体设计或软件测试" />
        </el-form-item>
      </el-form>
      <el-alert v-if="loading" type="info" :closable="false" show-icon title="六个资源智能体正在并行生成，完成后将自动进行质量审核与必要返工。" />
    </el-card>

    <el-card class="panel status-card" :class="`status-${displayMode}`">
      <div class="status-content">
        <div>
          <el-tag :type="displayMode === 'current' ? 'success' : displayMode === 'history' ? 'warning' : 'info'" effect="dark">
            {{ displayModeLabel }}
          </el-tag>
          <h3>{{ statusTitle }}</h3>
          <p>{{ statusDescription }}</p>
        </div>
        <div class="status-metrics">
          <div>
            <strong>{{ resources.length }}</strong>
            <span>当前资源</span>
          </div>
          <div>
            <strong>{{ trace.length }}</strong>
            <span>协作事件</span>
          </div>
          <div>
            <strong>{{ traceId || "未生成" }}</strong>
            <span>本次追踪 ID</span>
          </div>
        </div>
      </div>
    </el-card>

    <el-card v-if="plan.core_topic" class="panel">
      <template #header>PlannerAgent 资源计划</template>
      <el-descriptions :column="3" border>
        <el-descriptions-item label="核心主题">{{ plan.core_topic }}</el-descriptions-item>
        <el-descriptions-item label="目标水平">{{ plan.target_level }}</el-descriptions-item>
        <el-descriptions-item label="学习偏好">{{ plan.preferred_style }}</el-descriptions-item>
      </el-descriptions>
    </el-card>

    <el-card v-if="trace.length" class="panel">
      <template #header>
        <div class="header-line"><span>可审计的智能体协作轨迹</span><el-tag>{{ traceId }}</el-tag></div>
      </template>
      <el-timeline>
        <el-timeline-item
          v-for="(event, index) in trace"
          :key="`${event.agent}-${index}`"
          :type="eventType(event.status)"
          :timestamp="`${event.duration_ms || 0} ms${event.retry_count ? ` · 返工${event.retry_count}次` : ''}`"
        >
          <strong>{{ event.agent }}</strong>
          <span class="trace-status">{{ event.status }}</span>
          <p>{{ event.message }}</p>
        </el-timeline-item>
      </el-timeline>
    </el-card>

    <el-empty
      v-if="!resources.length && !loading"
      class="empty-panel panel"
      description="当前还没有学习资源。请先完成对话式画像，再点击上方按钮启动六智能体协作生成。"
    >
      <el-button type="primary" @click="generate">立即启动六智能体协作</el-button>
    </el-empty>

    <div v-else class="cards">
      <el-card v-for="item in resources" :key="`${item.id || item.resource_type}-${item.title}`" shadow="hover" class="resource-card">
        <template #header>
          <div class="resource-header">
            <div>
              <el-tag effect="dark">{{ typeLabel(item.resource_type) }}</el-tag>
              <el-tag :type="displayMode === 'current' ? 'success' : 'warning'" plain>
                {{ displayMode === 'current' ? '本次生成' : '历史资源' }}
              </el-tag>
              <strong>{{ item.title }}</strong>
            </div>
            <el-progress type="circle" :width="58" :stroke-width="6" :percentage="qualityScore(item)" />
          </div>
        </template>

        <el-alert class="personalization" type="success" :closable="false" show-icon>
          <template #title><strong>为什么为我这样生成</strong></template>
          {{ item.personalization || "依据当前学生画像与知识短板生成" }}
        </el-alert>

        <div v-if="item.resource_type === 'mindmap'" class="mindmap-shell">
          <div class="mindmap-toolbar">
            <span>白蓝详细知识导图</span>
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
          <div class="image-title">知识库配图</div>
          <a v-for="path in resourceImages(item)" :key="path" :href="imageUrl(path)" target="_blank" class="image-card">
            <img :src="imageUrl(path)" alt="知识库图片" loading="lazy" />
            <span>{{ shortImageName(path) }}</span>
          </a>
        </div>

        <el-divider />
        <div class="evidence">
          <div><strong>生成智能体：</strong>{{ item.agent_name || "历史资源" }}</div>
          <div><strong>知识点：</strong>{{ knowledgePoints(item).join("、") || "课程核心知识" }}</div>
          <div class="source-row">
            <strong>课程依据：</strong>
            <el-tag v-for="source in uniqueSources(item.sources)" :key="source" size="small" type="info">{{ source }}</el-tag>
          </div>
        </div>
      </el-card>
    </div>
  </div>
</template>

<script setup>
import MarkdownIt from "markdown-it";
import mermaid from "mermaid";
import { computed, nextTick, onMounted, reactive, ref } from "vue";
import { ElMessage } from "element-plus";
import { profileApi, resourceApi } from "../api";

const md = new MarkdownIt({ html: false, linkify: true, breaks: true });
const apiBase = import.meta.env.VITE_API_BASE_URL || "http://localhost:5000/api";
const absoluteImagePattern = /([A-Za-z]:\\[^\n\r，,；;）)]+?\.(?:png|jpg|jpeg|webp|gif))/gi;
const relativeImagePattern = /(images[\\/][^\n\r，,；;）)]+?\.(?:png|jpg|jpeg|webp|gif))/gi;
mermaid.initialize({ startOnLoad: false, theme: "base", securityLevel: "strict", themeVariables: { background: "#ffffff", primaryColor: "#eff6ff", primaryTextColor: "#0f172a", primaryBorderColor: "#3b82f6", lineColor: "#60a5fa", secondaryColor: "#dbeafe", tertiaryColor: "#f8fafc" } });

const loading = ref(false);
const displayMode = ref("empty");
const resources = ref([]);
const trace = ref([]);
const traceId = ref("");
const plan = reactive({});
const mindmapSvgs = reactive({});
const requestForm = reactive({ major: "软件工程", course: "软件工程", learning_need: "希望围绕软件工程中的需求分析、总体设计、详细设计、编码测试和维护等知识短板，通过图解、分层练习和案例形成完整学习资料。" });

const displayModeLabel = computed(() => ({ current: "本次生成结果", history: "历史资源回显", empty: "等待生成" }[displayMode.value] || "等待生成"));
const statusTitle = computed(() => {
  if (loading.value) return "正在生成本次个性化学习资源";
  if (displayMode.value === "current") return "当前展示的是本次六智能体协作生成结果";
  if (displayMode.value === "history") return "当前展示的是上次保存的历史学习资源";
  return "尚未生成学习资源";
});
const statusDescription = computed(() => {
  if (loading.value) return "系统正在读取画像、检索课程知识库，并并行调度六个资源智能体。完成后会展示 PlannerAgent 计划和可审计协作轨迹。";
  if (displayMode.value === "current") return "这些资源由本次点击按钮后实时生成，包含本次追踪 ID、协作轨迹、质量评分和课程依据，适合演示多智能体协作过程。";
  if (displayMode.value === "history") return "为了避免学生返回页面后资料丢失，系统会自动加载数据库中每类最新资源。点击上方按钮可基于最新画像重新生成。";
  return "请先在对话式画像页面完成画像采集，或直接填写本次学习需求后启动资源生成。";
});

function imageUrl(path) { return `${apiBase}/knowledge/image?path=${encodeURIComponent(String(path || "").trim())}`; }
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
function resourceImages(item) { return extractImagePaths([item.content, item.personalization, JSON.stringify(item.metadata || {})].join("\n")); }
function shortImageName(path) { return String(path || "").split(/\\|\//).slice(-2).join(" / "); }
function typeLabel(type) { return ({ doc: "讲解文档", quiz: "分层练习", reading: "拓展阅读", mindmap: "思维导图", code: "代码实操", video: "教学视频" }[type] || type); }
function eventType(status) { return ({ completed: "success", warning: "warning", failed: "danger" }[status] || "primary"); }
function qualityScore(item) { return Number(item.quality_score || item.quality?.total || item.metadata?.quality?.total || 0); }
function knowledgePoints(item) {
  if (Array.isArray(item.knowledge_points)) return item.knowledge_points;
  try { return JSON.parse(item.knowledge_points || "[]"); } catch { return []; }
}
function uniqueSources(sources = []) { return [...new Set((sources || []).map((item) => item.source || item.source_name).filter(Boolean))]; }
function videoUrl(item) { return item.video_url || item.metadata?.video_url || ""; }
function playableVideo(item) { const url = videoUrl(item); return /^https?:\/\//.test(url) && !url.includes("example.com"); }

async function renderMindmaps() {
  await nextTick();
  for (const item of resources.value.filter((entry) => entry.resource_type === "mindmap")) {
    const key = item.id || item.resource_type;
    try {
      const id = `mindmap-${key}-${Date.now()}`.replace(/[^a-zA-Z0-9-]/g, "");
      const { svg } = await mermaid.render(id, String(item.content || ""));
      mindmapSvgs[key] = svg;
    } catch (error) {
      mindmapSvgs[key] = `<pre>${String(item.content || "思维导图生成失败")}</pre>`;
    }
  }
}

function resetRunArtifacts() {
  trace.value = [];
  traceId.value = "";
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
    ElMessage.warning(resourceRes.msg || "历史资源加载失败，可直接重新生成");
  }
  if (profileRes.code === 200 && profileRes.data?.study_goal) requestForm.learning_need = profileRes.data.study_goal;
  await renderMindmaps();
}

async function generate() {
  loading.value = true;
  displayMode.value = "current";
  resetRunArtifacts();
  try {
    const res = await resourceApi.generate({ ...requestForm });
    if (res.code !== 200) {
      displayMode.value = resources.value.length ? "history" : "empty";
      const detail = res.data?.error ? `：${res.data.error}` : "";
      return ElMessage.error(`${res.msg || "资源生成失败"}${detail}`);
    }
    resources.value = res.data.resource_list || [];
    trace.value = res.data.trace || [];
    traceId.value = res.data.trace_id || "";
    Object.assign(plan, res.data.plan || {});
    displayMode.value = "current";
    await renderMindmaps();
    ElMessage.success(`六类资源生成完成，共记录${trace.value.length}个协作事件`);
  } catch (error) {
    displayMode.value = resources.value.length ? "history" : "empty";
    ElMessage.error(error?.message || "资源生成异常，请确认后端服务正常运行");
  } finally {
    loading.value = false;
  }
}

onMounted(loadResources);
</script>

<style scoped>
.resource-page { display: grid; gap: 18px; }
.header-line, .resource-header { display: flex; align-items: center; justify-content: space-between; gap: 20px; }
.header-line p { margin: 6px 0 0; color: #64748b; font-weight: normal; }
.status-card { overflow: hidden; }
.status-current { border-color: rgba(34, 197, 94, 0.35); background: linear-gradient(135deg, rgba(240, 253, 244, 0.96), rgba(255, 255, 255, 0.94)); }
.status-history { border-color: rgba(245, 158, 11, 0.35); background: linear-gradient(135deg, rgba(255, 251, 235, 0.96), rgba(255, 255, 255, 0.94)); }
.status-empty { border-color: rgba(59, 130, 246, 0.25); background: linear-gradient(135deg, rgba(239, 246, 255, 0.96), rgba(255, 255, 255, 0.94)); }
.status-content { display: flex; align-items: stretch; justify-content: space-between; gap: 24px; }
.status-content h3 { margin: 12px 0 8px; font-size: 20px; }
.status-content p { max-width: 860px; margin: 0; color: #475569; line-height: 1.8; }
.status-metrics { display: grid; grid-template-columns: repeat(3, minmax(110px, 1fr)); gap: 12px; min-width: 420px; }
.status-metrics div { padding: 14px; border-radius: 16px; background: rgba(255, 255, 255, 0.75); border: 1px solid rgba(148, 163, 184, 0.18); }
.status-metrics strong { display: block; max-width: 180px; overflow: hidden; color: #0f172a; font-size: 18px; text-overflow: ellipsis; white-space: nowrap; }
.status-metrics span { display: block; margin-top: 6px; color: #64748b; font-size: 12px; }
.empty-panel { padding: 26px; background: rgba(255, 255, 255, 0.9); }
.request-form { display: grid; grid-template-columns: 1fr 1fr 2fr; gap: 16px; }
.need-field { grid-column: span 1; }
.cards { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 18px; }
.resource-card { min-width: 0; }
.resource-header > div:first-child { display: flex; align-items: center; gap: 10px; }
.personalization { margin-bottom: 18px; }
.markdown-body { max-height: 650px; overflow: auto; line-height: 1.75; }
.markdown-body :deep(pre) { overflow: auto; padding: 16px; border-radius: 12px; background: #0f172a; color: #e2e8f0; }
.mindmap-shell { min-height: 560px; overflow: auto; border: 1px solid #bfdbfe; border-radius: 12px; background: #ffffff; box-shadow: inset 0 0 0 1px rgba(59, 130, 246, 0.06), 0 14px 36px rgba(30, 64, 175, 0.08); }
.mindmap-toolbar { display: flex; justify-content: space-between; align-items: center; padding: 12px 14px; border-bottom: 1px solid #dbeafe; color: #1d4ed8; font-weight: 700; background: linear-gradient(90deg, #eff6ff 0%, #ffffff 100%); }
.mindmap { min-width: 1180px; min-height: 500px; overflow: auto; padding: 36px; display: grid; place-items: center; background-image: linear-gradient(#eff6ff 1px, transparent 1px), linear-gradient(90deg, #eff6ff 1px, transparent 1px); background-size: 28px 28px; }
.mindmap :deep(svg) { max-width: none; height: auto; filter: drop-shadow(0 10px 22px rgba(37, 99, 235, 0.14)); }
.markdown-body :deep(img) { display: block; max-width: 100%; max-height: 360px; object-fit: contain; margin: 14px auto; border-radius: 8px; border: 1px solid #dbeafe; background: #fff; }
.image-gallery { margin-top: 16px; display: grid; grid-template-columns: repeat(auto-fill, minmax(160px, 1fr)); gap: 12px; }
.image-title { grid-column: 1 / -1; font-weight: 700; color: #1d4ed8; }
.image-card { display: grid; gap: 8px; padding: 8px; border: 1px solid #bfdbfe; border-radius: 8px; background: #fff; color: #475569; text-decoration: none; }
.image-card img { width: 100%; aspect-ratio: 4 / 3; object-fit: contain; background: #f8fafc; border-radius: 6px; }
.image-card span { font-size: 12px; word-break: break-all; }
.video { width: 100%; max-height: 420px; border-radius: 14px; background: #0f172a; }
.trace-status { margin-left: 10px; color: #64748b; font-size: 12px; text-transform: uppercase; }
.el-timeline-item p { margin: 6px 0 0; color: #475569; }
.evidence { display: grid; gap: 8px; color: #475569; font-size: 13px; }
.source-row { display: flex; flex-wrap: wrap; align-items: center; gap: 6px; }
@media (max-width: 1000px) {
  .cards, .request-form { grid-template-columns: 1fr; }
  .status-content { flex-direction: column; }
  .status-metrics { grid-template-columns: 1fr; min-width: 0; }
}
</style>
