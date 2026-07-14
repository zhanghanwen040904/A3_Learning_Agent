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
      <el-alert v-if="loading" type="info" :closable="false" show-icon :title="currentProgressHint" />
    </el-card>

    <el-card v-if="loading || generationProgress > 0" class="panel progress-panel">
      <template #header>
        <div class="header-line">
          <span>生成进度追踪</span>
          <el-tag type="primary" effect="dark">{{ generationProgress }}%</el-tag>
        </div>
      </template>
      <el-progress :percentage="generationProgress" :status="generationProgress === 100 && !loading ? 'success' : undefined" striped striped-flow />
      <div class="stage-grid">
        <div v-for="stage in progressStages" :key="stage.key" class="stage-card" :class="stageClass(stage)">
          <b>{{ stage.index }}</b>
          <strong>{{ stage.title }}</strong>
          <span>{{ stage.desc }}</span>
        </div>
      </div>
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

    <el-card class="panel agent-dashboard">
      <template #header>
        <div class="header-line">
          <div>
            <strong>智能体协作驾驶舱</strong>
            <p>展示各角色的实时/最终状态、耗时、返工次数与执行说明。</p>
          </div>
          <el-tag :type="loading ? 'primary' : trace.length ? 'success' : 'info'">{{ loading ? "协作中" : trace.length ? "已完成" : "待启动" }}</el-tag>
        </div>
      </template>
      <div class="agent-grid">
        <div v-for="agent in agentDashboard" :key="agent.name" class="agent-card" :class="`agent-${agent.status}`">
          <div class="agent-head">
            <div class="agent-avatar">{{ agent.short }}</div>
            <div>
              <strong>{{ agent.name }}</strong>
              <span>{{ agent.role }}</span>
            </div>
            <el-tag :type="agentTagType(agent.status)" size="small">{{ agentStatusLabel(agent.status) }}</el-tag>
          </div>
          <p>{{ agent.message }}</p>
          <div class="agent-meta">
            <span>{{ agent.duration_ms || 0 }} ms</span>
            <span>{{ agent.retry_count ? `返工 ${agent.retry_count} 次` : "无返工" }}</span>
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

        <el-collapse class="audit-collapse">
          <el-collapse-item title="质量审核与防幻觉报告" name="audit">
            <div class="audit-grid">
              <div class="audit-score">
                <el-progress type="dashboard" :percentage="qualityScore(item)" :color="scoreColors" />
                <strong>{{ qualityPassed(item) ? "审核通过" : "需要关注" }}</strong>
                <span>{{ qualityProblems(item).length ? qualityProblems(item).join("；") : "未发现明显问题" }}</span>
              </div>
              <div class="audit-bars">
                <div v-for="metric in qualityMetrics(item)" :key="metric.key" class="metric-row">
                  <span>{{ metric.label }}</span>
                  <el-progress :percentage="metric.value" />
                </div>
              </div>
              <div class="guard-card">
                <strong>防幻觉依据</strong>
                <p>{{ hallucinationSummary(item) }}</p>
                <div class="guard-tags">
                  <el-tag :type="uniqueSources(item.sources).length ? 'success' : 'danger'" size="small">来源 {{ uniqueSources(item.sources).length }} 个</el-tag>
                  <el-tag :type="qualityPassed(item) ? 'success' : 'warning'" size="small">质量 {{ qualityScore(item) }} 分</el-tag>
                  <el-tag :type="qualityChecks(item).content_audit === false ? 'danger' : 'success'" size="small">内容安全</el-tag>
                </div>
              </div>
            </div>
          </el-collapse-item>
        </el-collapse>

        <div v-if="item.resource_type === 'mindmap'" class="mindmap-shell">
          <div class="mindmap-toolbar">
            <div>
              <span>标准 Mermaid 思维导图</span>
              <el-tag type="info" size="small">mindmap</el-tag>
            </div>
            <div class="mindmap-actions">
              <el-tag size="small" effect="plain">{{ mindmapScaleLabel(item) }}</el-tag>
              <el-button size="small" @click="zoomMindmap(item, 0.15)">放大</el-button>
              <el-button size="small" @click="zoomMindmap(item, -0.15)">缩小</el-button>
              <el-button size="small" @click="resetMindmapView(item)">重置</el-button>
            </div>
          </div>
          <div
            class="mindmap-viewport"
            :data-mindmap-key="mindmapKey(item)"
            :class="{ dragging: mindmapDrag.key === mindmapKey(item) }"
            @pointerdown="startMindmapDrag($event, item)"
            @pointermove="moveMindmapDrag"
            @pointerup="stopMindmapDrag"
            @pointercancel="stopMindmapDrag"
            @pointerleave="stopMindmapDrag"
            @wheel.prevent="wheelMindmap($event, item)"
          >
            <div class="mindmap-canvas" :style="mindmapCanvasStyle(item)">
              <div class="mindmap" v-html="mindmapSvgs[mindmapKey(item)]"></div>
            </div>
          </div>
        </div>

        <template v-else-if="item.resource_type === 'doc'">
          <div class="doc-view">
            <div class="doc-section">
              <h4>当前学习位置</h4>
              <div v-if="docLocation(item).pathText" class="doc-location">
                <span>{{ docLocation(item).unit || "未识别单元" }}</span>
                <span>{{ docLocation(item).chapter || "未识别章节" }}</span>
                <span>{{ docLocation(item).section || "未识别小节" }}</span>
                <span v-if="docLocation(item).pagesText">第 {{ docLocation(item).pagesText }} 页</span>
              </div>
              <div v-else class="doc-empty">未检索到对应知识库片段。</div>
            </div>

            <div class="doc-section">
              <h4>核心概念讲解</h4>
              <div v-if="docConcepts(item).length" class="doc-grid">
                <div v-for="concept in docConcepts(item)" :key="concept.name" class="doc-card">
                  <strong>{{ concept.name }}</strong>
                  <p>{{ concept.definition }}</p>
                  <small v-if="concept.why_it_matters">{{ concept.why_it_matters }}</small>
                </div>
              </div>
              <div v-else class="doc-empty">未检索到对应知识库片段。</div>
            </div>

                        <div class="doc-section">
              <h4>知识点详细讲解</h4>
              <div v-if="docMainExplanation(item)" class="doc-stack">
                <div class="doc-card doc-card-main">
                  <strong>{{ docMainExplanation(item).title }}</strong>
                  <p>{{ docMainExplanation(item).explanation }}</p>
                </div>
              </div>
              <div v-else class="doc-empty">未检索到对应知识库片段。</div>
            </div>

            <div class="doc-section">
              <h4>补充知识点</h4>
              <div v-if="docExplanations(item).length" class="doc-stack">
                <div v-for="entry in docExplanations(item)" :key="entry.title" class="doc-card">
                  <strong>{{ entry.title }}</strong>
                  <p>{{ entry.explanation }}</p>
                </div>
              </div>
              <div v-else class="doc-empty">本资源围绕单一核心知识点展开，无需额外补充知识点。</div>
            </div>
<div class="doc-section">
              <h4>常见误区与纠正</h4>
              <div v-if="docMistakes(item).length" class="doc-stack">
                <div v-for="mistake in docMistakes(item)" :key="mistake.mistake_title" class="doc-card">
                  <strong>{{ mistake.mistake_title }}</strong>
                  <p>{{ mistake.reason }}</p>
                  <small v-if="mistake.correction">纠正：{{ mistake.correction }}</small>
                </div>
              </div>
              <div v-else class="doc-empty">未检索到对应知识库片段。</div>
            </div>

            <div class="doc-section">
              <h4>课程知识库依据</h4>
              <div v-if="docEvidence(item).length" class="doc-stack">
                <div v-for="evidence in docEvidence(item)" :key="docEvidenceKey(evidence)" class="doc-card">
                  <strong>{{ evidence.title }}</strong>
                                                                        <p>{{ evidence.content_preview }}</p>
                </div>
              </div>
              <div v-else class="doc-empty">未检索到对应知识库片段。</div>
            </div>
          </div>
        </template>

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
            <el-tag v-if="!uniqueSources(item.sources).length" size="small" type="danger">缺少来源依据</el-tag>
          </div>
        </div>
        <div class="resource-feedback-box">
          <div class="resource-feedback-head">
            <strong>学习反馈</strong>
            <span>{{ feedbackStatus(item) }}</span>
          </div>
          <div class="resource-feedback-actions">
            <el-button size="small" @click="markResourceHelpful(item, 5)">很有帮助</el-button>
            <el-button size="small" @click="markResourceHelpful(item, 3)">一般</el-button>
            <el-button size="small" @click="markResourceHelpful(item, 1)">需加强</el-button>
            <el-button size="small" type="success" plain @click="markResourceCompleted(item)">标记已学习</el-button>
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
const absoluteImagePattern = /([A-Za-z]:\\[^\n\r，,；;）)]+?\.(?:png|jpg|jpeg|webp|gif))/gi;
const relativeImagePattern = /(images[\\/][^\n\r，,；;）)]+?\.(?:png|jpg|jpeg|webp|gif))/gi;
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
const streamCompleted = ref(false);
const resourceStartTimes = reactive({});
const resourceFeedbackState = reactive({});
const plan = reactive({});
const mindmapSvgs = reactive({});
const mindmapViews = reactive({});
const mindmapDrag = reactive({ key: "", pointerId: null, startX: 0, startY: 0, originX: 0, originY: 0 });
const requestForm = reactive({ major: "软件工程", course: "软件工程", learning_need: "希望围绕软件工程中的需求分析、总体设计、详细设计、编码测试和维护等知识短板，通过图解、分层练习和案例形成完整学习资料。" });

const progressStages = [
  { key: "profile", index: "01", title: "画像读取", desc: "合并学生画像与本次学习需求", progress: 12 },
  { key: "retrieve", index: "02", title: "可信检索", desc: "从软件工程知识库召回依据", progress: 28 },
  { key: "plan", index: "03", title: "任务规划", desc: "PlannerAgent 拆解六类资源", progress: 42 },
  { key: "generate", index: "04", title: "并行生成", desc: "六个资源智能体同步生产", progress: 70 },
  { key: "review", index: "05", title: "审核返工", desc: "质量评分、防幻觉与安全复核", progress: 88 },
  { key: "package", index: "06", title: "保存打包", desc: "汇总资源包和协作证据", progress: 100 },
];
const agentSpecs = [
  { name: "ProfileAgent", short: "PA", role: "画像分析" },
  { name: "RetrieveAgent", short: "RA", role: "知识检索" },
  { name: "PlannerAgent", short: "PL", role: "任务规划" },
  { name: "DocumentAgent", short: "DA", role: "讲解文档" },
  { name: "QuizAgent", short: "QA", role: "分层练习" },
  { name: "ReadingAgent", short: "RD", role: "拓展阅读" },
  { name: "MindMapAgent", short: "MM", role: "思维导图" },
  { name: "CodeAgent", short: "CA", role: "代码实操" },
  { name: "VideoAgent", short: "VA", role: "视频脚本" },
  { name: "QualityAgent", short: "QG", role: "质量评估" },
  { name: "SafetyAgent", short: "SA", role: "安全复核" },
  { name: "PackagerAgent", short: "PK", role: "结果编排" },
];
const scoreColors = [
  { color: "#ef4444", percentage: 59 },
  { color: "#f59e0b", percentage: 74 },
  { color: "#10b981", percentage: 100 },
];

const displayModeLabel = computed(() => ({ current: "本次生成结果", history: "历史资源回显", empty: "等待生成" }[displayMode.value] || "等待生成"));
const currentProgressHint = computed(() => progressStages[currentStageIndex.value]?.desc || "多智能体正在协同生成资源");
const agentDashboard = computed(() => agentSpecs.map((spec) => {
  const event = [...trace.value].reverse().find((item) => item.agent === spec.name);
  if (event) return { ...spec, ...event, status: event.status || "completed", message: event.message || "执行完成" };
  if (!loading.value) return { ...spec, status: "idle", message: "等待本次任务启动", duration_ms: 0, retry_count: 0 };
  const runningNames = agentNamesForStage(currentStageIndex.value);
  const status = runningNames.includes(spec.name) ? "running" : "pending";
  return { ...spec, status, message: status === "running" ? "正在处理当前阶段任务" : "等待上游智能体完成", duration_ms: 0, retry_count: 0 };
}));
const statusTitle = computed(() => {
  if (loading.value) return "正在生成本次个性化学习资源";
  if (displayMode.value === "current") return "当前展示的是本次六智能体协作生成结果";
  if (displayMode.value === "history") return "当前展示的是上次保存的历史学习资源";
  return "尚未生成学习资源";
});
const statusDescription = computed(() => {
  if (loading.value) return "系统正在读取画像、检索课程知识库，并并行调度六个资源智能体。页面会持续展示生成阶段，完成后用真实协作轨迹覆盖。";
  if (displayMode.value === "current") return "这些资源由本次点击按钮后实时生成，包含本次追踪 ID、协作轨迹、质量评分、防幻觉审核和课程依据，适合演示多智能体协作过程。";
  if (displayMode.value === "history") return "为了避免学生返回页面后资料丢失，系统会自动加载数据库中每类最新资源。点击上方按钮可基于最新画像重新生成。";
  return "请先在对话式画像页面完成画像采集，或直接填写本次学习需求后启动资源生成。";
});

function agentNamesForStage(index) {
  return [
    ["ProfileAgent"],
    ["RetrieveAgent"],
    ["PlannerAgent"],
    ["DocumentAgent", "QuizAgent", "ReadingAgent", "MindMapAgent", "CodeAgent", "VideoAgent"],
    ["QualityAgent", "SafetyAgent"],
    ["PackagerAgent"],
  ][index] || [];
}
function stageClass(stage) {
  const index = progressStages.findIndex((item) => item.key === stage.key);
  if (generationProgress.value >= stage.progress) return "done";
  if (index === currentStageIndex.value && loading.value) return "running";
  return "pending";
}
function agentTagType(status) { return ({ completed: "success", warning: "warning", failed: "danger", running: "primary", pending: "info", idle: "info" }[status] || "info"); }
function agentStatusLabel(status) { return ({ completed: "完成", warning: "警告", failed: "失败", running: "运行中", pending: "排队", idle: "待启动" }[status] || status); }
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
function stripFences(text) {
  return String(text || "")
    .trim()
    .replace(/^```(?:mermaid|markdown|md|json|text)?\s*/i, "")
    .replace(/```\s*$/i, "")
    .trim();
}
function mindmapKey(item) {
  return String(item?.id || item?.resource_type || item?.title || "mindmap").replace(/[^\w-]/g, "-");
}
function ensureMindmapView(key) {
  if (!mindmapViews[key]) {
    mindmapViews[key] = { x: 0, y: 0, scale: 1, fitted: false };
  }
  return mindmapViews[key];
}
function mindmapCanvasStyle(item) {
  const view = ensureMindmapView(mindmapKey(item));
  return { transform: `translate(${view.x}px, ${view.y}px) scale(${view.scale})` };
}
function clampMindmapScale(value) {
  return Math.min(2.8, Math.max(0.35, Number(value) || 1));
}
function mindmapScaleLabel(item) {
  const view = ensureMindmapView(mindmapKey(item));
  return `${Math.round(view.scale * 100)}%`;
}
function zoomMindmap(item, delta) {
  const view = ensureMindmapView(mindmapKey(item));
  view.scale = clampMindmapScale(view.scale + delta);
  view.fitted = true;
}
function wheelMindmap(event, item) {
  const view = ensureMindmapView(mindmapKey(item));
  const previousScale = view.scale;
  const nextScale = clampMindmapScale(previousScale + (event.deltaY > 0 ? -0.1 : 0.1));
  const rect = event.currentTarget.getBoundingClientRect();
  const offsetX = event.clientX - rect.left - view.x;
  const offsetY = event.clientY - rect.top - view.y;
  const ratio = nextScale / previousScale;
  view.x -= offsetX * (ratio - 1);
  view.y -= offsetY * (ratio - 1);
  view.scale = nextScale;
  view.fitted = true;
}
function resetMindmapView(item) {
  fitMindmapView(item, true);
}
function startMindmapDrag(event, item) {
  if (event.button !== 0) return;
  event.currentTarget.setPointerCapture?.(event.pointerId);
  const key = mindmapKey(item);
  const view = ensureMindmapView(key);
  mindmapDrag.key = key;
  mindmapDrag.pointerId = event.pointerId;
  mindmapDrag.startX = event.clientX;
  mindmapDrag.startY = event.clientY;
  mindmapDrag.originX = view.x;
  mindmapDrag.originY = view.y;
  view.fitted = true;
}
function moveMindmapDrag(event) {
  if (!mindmapDrag.key || event.pointerId !== mindmapDrag.pointerId) return;
  const view = ensureMindmapView(mindmapDrag.key);
  view.x = mindmapDrag.originX + event.clientX - mindmapDrag.startX;
  view.y = mindmapDrag.originY + event.clientY - mindmapDrag.startY;
}
function stopMindmapDrag(event) {
  if (event?.pointerId && mindmapDrag.pointerId && event.pointerId !== mindmapDrag.pointerId) return;
  event?.currentTarget?.releasePointerCapture?.(mindmapDrag.pointerId);
  mindmapDrag.key = "";
  mindmapDrag.pointerId = null;
}
function cleanMindmapLabel(value) {
  const cleaned = String(value || "")
    .replace(/<[^>]+>/g, " ")
    .replace(/[`"'{}[\]|<>()[\]]/g, "")
    .replace(/[:：;]/g, " ")
    .replace(/-->|---|==>|-/g, " ")
    .replace(/[#*_~\\/]/g, " ")
    .replace(/\s+/g, " ")
    .trim()
    .slice(0, 42);
  return cleaned || "知识点";
}
function markdownLineToMindmapNode(line) {
  const raw = String(line || "").replace(/\t/g, "  ").trimEnd();
  if (!raw.trim() || raw.trim().startsWith("%%")) return null;
  const heading = raw.match(/^\s*(#{1,6})\s+(.+)$/);
  if (heading) return { depth: heading[1].length, label: cleanMindmapLabel(heading[2]) };
  const list = raw.match(/^(\s*)([-*+] |\d+[.)]\s+)(.+)$/);
  if (list) return { depth: Math.min(6, Math.floor(list[1].length / 2) + 2), label: cleanMindmapLabel(list[3]) };
  const node = raw.match(/^(\s*)(.+)$/);
  if (!node) return null;
  return {
    depth: Math.min(6, Math.floor(node[1].length / 2) + 1),
    label: cleanMindmapLabel(node[2].replace(/^root\s*/i, "")),
  };
}
function escapeMindmapText(value) {
  return String(value || "")
    .replace(/"/g, "")
    .replace(/\s+/g, " ")
    .trim();
}
function buildMindmapTree(nodes, fallbackTitle) {
  if (!nodes.length) return null;
  const minDepth = Math.min(...nodes.map((node) => node.depth));
  const rootNode = nodes.find((node) => node.depth === minDepth) || { label: cleanMindmapLabel(fallbackTitle), depth: minDepth };
  const root = { label: rootNode.label || cleanMindmapLabel(fallbackTitle), children: [] };
  const stack = [{ depth: minDepth, node: root }];

  for (const current of nodes) {
    if (current === rootNode) continue;
    const normalizedDepth = Math.max(minDepth + 1, current.depth);
    while (stack.length > 1 && normalizedDepth <= stack[stack.length - 1].depth) {
      stack.pop();
    }
    const parent = stack[stack.length - 1]?.node || root;
    const next = { label: current.label, children: [] };
    parent.children.push(next);
    stack.push({ depth: normalizedDepth, node: next });
  }

  return root;
}
function treeToMermaidMindmap(tree) {
  if (!tree?.label) return "";
  const lines = ["mindmap", `  root((${escapeMindmapText(tree.label)}))`];
  function walk(node, depth) {
    for (const child of node.children || []) {
      lines.push(`${"  ".repeat(depth)}${escapeMindmapText(child.label)}`);
      walk(child, depth + 1);
    }
  }
  walk(tree, 2);
  return lines.join("\n");
}
function normalizeMindmapSource(text, fallbackTitle = "软件工程知识导图") {
  const source = stripFences(text).replace(/::icon\([^)]+\)/g, "");
  const lines = source.split("\n").map((line) => line.replace(/\r/g, ""));
  const startIndex = lines.findIndex((line) => /^\s*mindmap\b/i.test(line));
  const contentLines = startIndex >= 0 ? lines.slice(startIndex + 1) : lines;
  const nodes = contentLines.map(markdownLineToMindmapNode).filter(Boolean);
  if (!nodes.length) return "";
  const tree = buildMindmapTree(nodes.slice(0, 80), fallbackTitle);
  return treeToMermaidMindmap(tree);
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
function normalizeCompareText(value) {
  return String(value || "")
    .trim()
    .toLowerCase()
    .replace(/[\s\-_—–·•，。！？；：、,.!?;:()[\]{}<>《》“”"'`~]+/g, "");
}
function dedupeBy(items, keyFn) {
  const seen = new Set();
  return (items || []).filter((item) => {
    const key = keyFn(item);
    if (!key || seen.has(key)) return false;
    seen.add(key);
    return true;
  });
}
function sanitizeKnowledgeText(value) {
  return String(value || "")
    .replace(/(标题|章节路径|页码|内容|教材依据|教材片段重点说明|结合课程知识库内容可知)\s*[：:]\s*/g, "")
    .replace(/\n{2,}/g, "\n")
    .replace(/\s{2,}/g, " ")
    .trim();
}

function docPayload(item) {
  const parsed = parseJsonLike(item.content);
  return parsed && typeof parsed === "object" && !Array.isArray(parsed) ? parsed : null;
}
function docLocation(item) {
  const payload = docPayload(item) || {};
  const context = payload.studentcontext || {};
  const path = Array.isArray(context.path) ? context.path : [];
  const unit = context.currentunit || path[0] || "";
  const chapter = context.currentchapter || path[1] || "";
  const section = context.currentsection || path[2] || "";
  const currentPage = Array.isArray(context.currentpage) ? context.currentpage : context.currentpage ? [context.currentpage] : [];
  return {
    unit,
    chapter,
    section,
    pages: currentPage,
    pagesText: currentPage.join("、"),
    pathText: [unit, chapter, section].filter(Boolean).join(" > "),
  };
}
function docConcepts(item) {
  const payload = docPayload(item) || {};
  return dedupeBy(
    (payload.core_concepts || []).map((entry) => ({
      name: entry?.name || entry?.title || "",
      definition: entry?.definition || entry?.content || "",
      why_it_matters: entry?.why_it_matters || "",
    })),
    (entry) => normalizeCompareText(entry.name),
  ).filter((entry) => entry.name);
}
function docMainExplanation(item) {
  const payload = docPayload(item) || {};
  const main = payload.main_explanation || {};
  const firstExtra = (payload.knowledge_explanation || [])[0] || {};
  const title = sanitizeKnowledgeText(main?.title || firstExtra?.title || "核心知识讲解");
  const explanation = sanitizeKnowledgeText(main?.content || main?.explanation || firstExtra?.explanation || "");
  return explanation ? { title, explanation } : null;
}
function docExplanations(item) {
  const payload = docPayload(item) || {};
  const main = docMainExplanation(item);
  return dedupeBy(
    (payload.knowledge_explanation || []).map((entry) => ({
      title: sanitizeKnowledgeText(entry?.title || entry?.name || ""),
      explanation: sanitizeKnowledgeText(entry?.explanation || entry?.content || ""),
    })),
    (entry) => normalizeCompareText(entry.title),
  ).filter((entry) => {
    if (!(entry.title || entry.explanation)) return false;
    if (!main) return true;
    return normalizeCompareText(entry.title) !== normalizeCompareText(main.title);
  }).slice(0, 2);
}
function docMistakes(item) {
  const payload = docPayload(item) || {};
  return dedupeBy(
    (payload.mistakes || []).map((entry) => ({
      mistake_title: entry?.mistake_title || entry?.mistake || entry?.title || "",
      reason: entry?.reason || "",
      correction: entry?.correction || "",
    })),
    (entry) => normalizeCompareText(entry.mistake_title),
  ).filter((entry) => entry.mistake_title);
}
function docEvidence(item) {
  const payload = docPayload(item) || {};
  return dedupeBy(
    (payload.learningresources || []).map((entry) => ({
      title: sanitizeKnowledgeText(entry?.title || ""),
      content_preview: sanitizeKnowledgeText(entry?.content_preview || entry?.content || ""),
      section_path: Array.isArray(entry?.section_path) ? entry.section_path : [],
      pages: Array.isArray(entry?.pages) ? entry.pages : [],
      source_file: entry?.source_file || "",
    })),
    (entry) => `${normalizeCompareText(entry.title)}|${normalizeCompareText((entry.section_path || []).join(">"))}`,
  ).filter((entry) => entry.title || entry.content_preview);
}
function docEvidenceKey(entry) {
  return `${entry.title}-${(entry.section_path || []).join("-")}-${(entry.pages || []).join("-")}`;
}
function extractMindmapSource(text, fallbackTitle = "软件工程知识导图") {
  const mermaidFence = String(text || "").match(/```mermaid\s*([\s\S]*?)```/i);
  if (mermaidFence) return normalizeMindmapSource(mermaidFence[1], fallbackTitle);
  return normalizeMindmapSource(text, fallbackTitle);
}
function buildFallbackMindmap(item) {
  const title = cleanMindmapLabel(item.title || "软件工程知识导图") || "软件工程知识导图";
  const points = knowledgePoints(item).map(cleanMindmapLabel).filter(Boolean);
  const headings = String(item.content || "")
    .split("\n")
    .map((line) => line.replace(/^#+\s*/, "").replace(/^[-*+]\s*/, ""))
    .map(cleanMindmapLabel)
    .filter((line) => line && !line.startsWith("配图") && !line.startsWith("images"))
    .slice(0, 18);
  const branches = [...new Set([...points, ...headings])].slice(0, 24);
  const primary = branches.length ? branches : ["核心概念", "关键流程", "输入输出", "典型场景", "易错提醒", "学习建议"];
  const lines = ["mindmap", `  root((${escapeMindmapText(title)}))`];
  primary.slice(0, 6).forEach((branch, index) => {
    lines.push(`    ${escapeMindmapText(branch)}`);
    const details = primary.slice(index * 3 + 6, index * 3 + 9);
    const fallbackDetails = ["定义与作用", "关键输入输出", "常见误区"];
    (details.length ? details : fallbackDetails).slice(0, 3).forEach((detail) => {
      lines.push(`      ${escapeMindmapText(cleanMindmapLabel(detail))}`);
    });
  });
  return lines.join("\n");
}
function buildMindmapSource(item) {
  const title = item.title || "软件工程知识导图";
  const direct = extractMindmapSource(item.content, title);
  if (direct) return direct;
  const parsed = parseJsonLike(item.content);
  if (parsed) {
    const content = parsed.content || parsed.mindmap || parsed.markdown || "";
    const fromJson = extractMindmapSource(content, parsed.title || title);
    if (fromJson) return fromJson;
    const merged = {
      ...item,
      title: parsed.title || item.title,
      content: content || item.content,
      knowledge_points: parsed.knowledge_points || item.knowledge_points,
    };
    return buildFallbackMindmap(merged);
  }
  return buildFallbackMindmap(item);
}
function resourceImages(item) { return []; }
function shortImageName(path) { return String(path || "").split(/\\|\//).slice(-2).join(" / "); }
function typeLabel(type) { return ({ doc: "讲解文档", quiz: "分层练习", reading: "拓展阅读", mindmap: "思维导图", code: "代码实操", video: "教学视频" }[type] || type); }
function eventType(status) { return ({ completed: "success", warning: "warning", failed: "danger" }[status] || "primary"); }
function qualityObject(item) { return item.quality || item.metadata?.quality || {}; }
function qualityScore(item) { return Number(item.quality_score || qualityObject(item).total || 0); }
function qualityPassed(item) { const quality = qualityObject(item); return quality.passed !== false && qualityScore(item) >= 75; }
function qualityProblems(item) { return qualityObject(item).problems || []; }
function qualityChecks(item) { return qualityObject(item).checks || {}; }
function qualityMetrics(item) {
  const quality = qualityObject(item);
  return [
    { key: "accuracy", label: "准确性", value: Number(quality.accuracy || 0) },
    { key: "personalization", label: "个性化", value: Number(quality.personalization || 0) },
    { key: "completeness", label: "完整性", value: Number(quality.completeness || 0) },
    { key: "source_support", label: "来源支撑", value: Number(quality.source_support || 0) },
  ];
}
function hallucinationSummary(item) {
  const sourceCount = uniqueSources(item.sources).length;
  if (!sourceCount) return "当前资源缺少课程知识库来源，建议重新生成或检查知识库索引。";
  if (!qualityPassed(item)) return "资源已有课程依据，但质量审核提示存在需关注项，建议结合来源复核后使用。";
  return "资源已关联课程知识库来源，并通过质量评分与内容安全检查，可作为本次学习参考。";
}
function knowledgePoints(item) {
  if (Array.isArray(item.knowledge_points)) return item.knowledge_points;
  try { return JSON.parse(item.knowledge_points || "[]"); } catch { return []; }
}
function uniqueSources(sources = []) { return [...new Set((sources || []).map((item) => item.source || item.source_name).filter(Boolean))]; }
function resourceKey(item) { return String(item?.id || `${item?.resource_type || "resource"}-${item?.title || ""}`); }
function ensureResourceStart(item) {
  const key = resourceKey(item);
  if (!resourceStartTimes[key]) resourceStartTimes[key] = Date.now();
  return resourceStartTimes[key];
}
function resourceDurationSec(item) {
  const started = ensureResourceStart(item);
  return Math.max(0, Math.round((Date.now() - started) / 1000));
}
function feedbackStatus(item) {
  return resourceFeedbackState[resourceKey(item)]?.label || "可提交学习反馈，系统会据此调整后续资源与学习计划。";
}
async function markResourceHelpful(item, rating) {
  if (!item?.id) return;
  ensureResourceStart(item);
  const res = await resourceApi.feedback(item.id, {
    rating,
    duration_sec: resourceDurationSec(item),
    comment: rating >= 4 ? "该资源对当前理解很有帮助" : rating <= 2 ? "当前资源还需要补充基础讲解或换一种表达" : "当前资源可继续优化",
  });
  if (res.code === 200) {
    resourceFeedbackState[resourceKey(item)] = {
      label: rating >= 4 ? "已记录为高价值资源，将优先推荐同类资源。" : rating <= 2 ? "已记录为需加强，后续会调整资源难度与讲解方式。" : "已记录为一般反馈，系统会继续优化推荐。",
    };
    ElMessage.success(res.msg || "反馈已记录");
    window.dispatchEvent(new CustomEvent("a3-profile-session-refresh"));
  } else {
    ElMessage.warning(res.msg || "反馈记录失败");
  }
}
async function markResourceCompleted(item) {
  if (!item?.id) return;
  ensureResourceStart(item);
  const res = await resourceApi.usage(item.id, {
    duration_sec: resourceDurationSec(item),
    progress: 100,
    completed: true,
  });
  if (res.code === 200) {
    resourceFeedbackState[resourceKey(item)] = { label: "已记录为完成学习，系统会结合掌握情况调整下一阶段重点。" };
    ElMessage.success(res.msg || "学习行为已记录");
    window.dispatchEvent(new CustomEvent("a3-profile-session-refresh"));
  } else {
    ElMessage.warning(res.msg || "学习行为记录失败");
  }
}
function videoUrl(item) {
  const url = item.video_url || item.metadata?.video_url || "";
  if (!url) return "";
  if (/^https?:\/\//.test(url)) return url;
  if (url.startsWith("/api/")) return `${apiBase.replace(/\/api$/, "")}${url}`;
  return url;
}
function playableVideo(item) { const url = videoUrl(item); return Boolean(url) && !url.includes("example.com"); }

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
    DocumentAgent: 70,
    QuizAgent: 70,
    ReadingAgent: 70,
    MindMapAgent: 70,
    CodeAgent: 70,
    VideoAgent: 70,
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

function fitMindmapView(item, force = false) {
  const key = mindmapKey(item);
  const view = ensureMindmapView(key);
  if (view.fitted && !force) return;

  nextTick(() => {
    const viewport = document.querySelector(`[data-mindmap-key="${key}"]`);
    const svg = viewport?.querySelector("svg");
    if (!viewport || !svg) return;

    const viewBox = (svg.getAttribute("viewBox") || "").split(/\s+/).map(Number);
    const svgWidth = Number(svg.getAttribute("width")) || viewBox[2] || svg.getBoundingClientRect().width || 1200;
    const svgHeight = Number(svg.getAttribute("height")) || viewBox[3] || svg.getBoundingClientRect().height || 800;
    const viewportWidth = viewport.clientWidth;
    const viewportHeight = viewport.clientHeight;
    if (!viewportWidth || !viewportHeight || !svgWidth || !svgHeight) return;

    const padding = 72;
    const scale = clampMindmapScale(Math.min((viewportWidth - padding) / svgWidth, (viewportHeight - padding) / svgHeight, 1));
    view.scale = scale;
    view.x = Math.max((viewportWidth - svgWidth * scale) / 2, 24);
    view.y = Math.max((viewportHeight - svgHeight * scale) / 2, 20);
    view.fitted = true;
  });
}

async function renderMindmaps() {
  await nextTick();
  for (const item of resources.value.filter((entry) => entry.resource_type === "mindmap")) {
    const key = mindmapKey(item);
    const source = buildMindmapSource(item);
    const view = ensureMindmapView(key);
    view.fitted = false;
    if (source && await safeRenderMindmap(key, source)) {
      fitMindmapView(item);
      continue;
    }

    const safeSource = buildFallbackMindmap({ ...item, content: "", knowledge_points: knowledgePoints(item) });
    if (await safeRenderMindmap(`fallback-${key}`, safeSource)) {
      mindmapSvgs[key] = mindmapSvgs[`fallback-${key}`];
      delete mindmapSvgs[`fallback-${key}`];
      fitMindmapView(item);
    } else {
      mindmapSvgs[key] = `<div class="mindmap-error">思维导图渲染失败，已隐藏 Mermaid 原始错误，请重新生成资源。</div>`;
    }
  }
}

function refitAllMindmaps() {
  resources.value
    .filter((entry) => entry.resource_type === "mindmap")
    .forEach((item) => fitMindmapView(item, true));
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
    resources.value.forEach((item) => ensureResourceStart(item));
    displayMode.value = resources.value.length ? "history" : "empty";
  } else {
    resources.value = [];
    displayMode.value = "empty";
    ElMessage.warning(resourceRes.msg || "历史资源加载失败，可直接重新生成");
  }
  if (profileRes.code === 200 && profileRes.data?.study_goal) requestForm.learning_need = profileRes.data.study_goal;
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
  resources.value.forEach((item) => { resourceStartTimes[resourceKey(item)] = Date.now(); });
  trace.value = result.trace || trace.value;
  traceId.value = result.trace_id || traceId.value;
  Object.keys(plan).forEach((key) => delete plan[key]);
  Object.assign(plan, result.plan || {});
  displayMode.value = "current";
  streamCompleted.value = true;
  closeEventSource();
  finishProgress(100);
  loading.value = false;
  renderMindmaps();
  ElMessage.success(`六类资源生成完成，共记录${trace.value.length}个真实协作事件`);
}

function handleStreamError(payload) {
  if (streamCompleted.value || !loading.value) return;
  finishProgress(Math.max(generationProgress.value, 60));
  loading.value = false;
  displayMode.value = resources.value.length ? "history" : "empty";
  const detail = payload?.error ? `：${payload.error}` : "";
  ElMessage.error(`${payload?.message || "资源生成失败"}${detail}`);
}

async function generate() {
  loading.value = true;
  streamCompleted.value = false;
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
    if (streamCompleted.value) return;
    if (event.data) {
      handleStreamError(JSON.parse(event.data || "{}"));
    } else if (loading.value) {
      handleStreamError({ message: "SSE 连接中断，请确认后端服务正常运行" });
    }
  });
  source.onerror = () => {
    if (streamCompleted.value) return;
    if (loading.value) handleStreamError({ message: "SSE 连接中断，请确认后端服务正常运行" });
  };
}

onMounted(loadResources);
onMounted(() => window.addEventListener("resize", refitAllMindmaps));
onBeforeUnmount(() => {
  closeEventSource();
  window.removeEventListener("resize", refitAllMindmaps);
});
</script>

<style scoped>
.resource-page { display: grid; gap: 18px; }
.header-line, .resource-header { display: flex; align-items: center; justify-content: space-between; gap: 20px; }
.header-line p { margin: 6px 0 0; color: #64748b; font-weight: normal; }
.progress-panel { border-color: rgba(37, 99, 235, 0.22); background: linear-gradient(135deg, #ffffff, #f8fbff); }
.stage-grid { display: grid; grid-template-columns: repeat(6, minmax(0, 1fr)); gap: 12px; margin-top: 18px; }
.stage-card { min-height: 112px; padding: 14px; border: 1px solid #e2e8f0; border-radius: 16px; background: #fff; color: #64748b; }
.stage-card b { display: block; color: #94a3b8; font-size: 18px; }
.stage-card strong { display: block; margin: 8px 0 6px; color: #0f172a; }
.stage-card span { font-size: 12px; line-height: 1.6; }
.stage-card.running { border-color: #60a5fa; background: #eff6ff; box-shadow: 0 12px 32px rgba(37, 99, 235, 0.12); }
.stage-card.done { border-color: #86efac; background: #f0fdf4; }
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
.agent-dashboard { background: linear-gradient(180deg, #fff, #f8fbff); }
.agent-grid { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 14px; }
.agent-card { min-height: 150px; padding: 14px; border: 1px solid #e2e8f0; border-radius: 18px; background: #fff; }
.agent-card.agent-running { border-color: #60a5fa; background: #eff6ff; box-shadow: 0 12px 28px rgba(37, 99, 235, 0.12); }
.agent-card.agent-completed { border-color: #bbf7d0; }
.agent-card.agent-warning { border-color: #fcd34d; background: #fffbeb; }
.agent-card.agent-failed { border-color: #fca5a5; background: #fef2f2; }
.agent-head { display: flex; align-items: center; gap: 10px; }
.agent-head > div:nth-child(2) { flex: 1; min-width: 0; }
.agent-head strong, .agent-head span { display: block; }
.agent-head span { margin-top: 3px; color: #64748b; font-size: 12px; }
.agent-avatar { display: grid; width: 38px; height: 38px; flex: 0 0 auto; place-items: center; border-radius: 13px; color: #fff; background: linear-gradient(135deg, #2563eb, #06b6d4); font-weight: 800; }
.agent-card p { min-height: 42px; margin: 12px 0; color: #475569; line-height: 1.6; font-size: 13px; }
.agent-meta { display: flex; flex-wrap: wrap; gap: 8px; color: #64748b; font-size: 12px; }
.cards { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 18px; }
.resource-card { min-width: 0; }
.resource-header > div:first-child { display: flex; align-items: center; gap: 10px; }
.resource-feedback-box { margin-top: 14px; padding: 14px 16px; border: 1px solid #e8eef8; border-radius: 16px; background: linear-gradient(180deg, #fcfdff 0%, #f7fbff 100%); }
.resource-feedback-head { display: flex; align-items: center; justify-content: space-between; gap: 12px; margin-bottom: 10px; color: #64748b; font-size: 12px; }
.resource-feedback-actions { display: flex; flex-wrap: wrap; gap: 10px; }
.personalization { margin-bottom: 14px; }
.audit-collapse { margin-bottom: 18px; border-radius: 12px; }
.audit-grid { display: grid; grid-template-columns: 180px 1fr 1fr; gap: 18px; align-items: center; }
.audit-score { display: grid; justify-items: center; gap: 8px; text-align: center; }
.audit-score span { color: #64748b; font-size: 12px; line-height: 1.5; }
.audit-bars { display: grid; gap: 10px; }
.metric-row { display: grid; grid-template-columns: 74px 1fr; gap: 10px; align-items: center; color: #475569; font-size: 13px; }
.guard-card { padding: 14px; border: 1px solid #dbeafe; border-radius: 14px; background: #f8fbff; }
.guard-card p { margin: 8px 0 12px; color: #475569; line-height: 1.7; }
.guard-tags { display: flex; flex-wrap: wrap; gap: 8px; }
.markdown-body { max-height: 650px; overflow: auto; line-height: 1.75; }
.markdown-body :deep(pre) { overflow: auto; padding: 16px; border-radius: 12px; background: #0f172a; color: #e2e8f0; }
.mindmap-shell { min-height: 620px; overflow: hidden; border: 1px solid #bfdbfe; border-radius: 8px; background: #ffffff; box-shadow: inset 0 0 0 1px rgba(59, 130, 246, 0.06), 0 14px 36px rgba(30, 64, 175, 0.08); }
.doc-view { display: grid; gap: 18px; }
.doc-section { padding: 16px; border: 1px solid #dbeafe; border-radius: 12px; background: #ffffff; }
.doc-section h4 { margin: 0 0 12px; color: #1d4ed8; font-size: 16px; }
.doc-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 12px; }
.doc-stack { display: grid; gap: 12px; }
.doc-card { display: grid; gap: 8px; padding: 14px; border: 1px solid #e2e8f0; border-radius: 10px; background: #f8fbff; }
.doc-card strong { color: #0f172a; }
.doc-card p { margin: 0; color: #334155; line-height: 1.7; }
.doc-card-main p { font-size: 15px; line-height: 1.85; }
.doc-card small { color: #64748b; line-height: 1.6; }
.doc-location { display: flex; flex-wrap: wrap; gap: 8px; }
.doc-location span { padding: 6px 10px; border-radius: 999px; background: #eff6ff; color: #1d4ed8; }
.doc-empty { color: #64748b; }
.mindmap-toolbar { display: flex; justify-content: space-between; align-items: center; gap: 12px; padding: 12px 14px; border-bottom: 1px solid #dbeafe; color: #1d4ed8; font-weight: 700; background: linear-gradient(90deg, #eff6ff 0%, #ffffff 100%); }
.mindmap-toolbar > div { display: flex; align-items: center; gap: 8px; }
.mindmap-actions { flex-wrap: wrap; justify-content: flex-end; }
.mindmap-viewport { position: relative; height: 560px; overflow: hidden; cursor: grab; touch-action: none; user-select: none; background-color: #fbfdff; background-image: linear-gradient(#e6f0ff 1px, transparent 1px), linear-gradient(90deg, #e6f0ff 1px, transparent 1px); background-size: 28px 28px; }
.mindmap-viewport.dragging { cursor: grabbing; }
.mindmap-canvas { min-width: 1280px; min-height: 560px; padding: 42px; display: grid; place-items: center; transform-origin: 0 0; transition: transform 0.08s ease-out; }
.mindmap-viewport.dragging .mindmap-canvas { transition: none; }
.mindmap { min-width: 980px; min-height: 460px; display: grid; place-items: center; }
.mindmap :deep(svg) { max-width: none; min-width: 980px; height: auto; pointer-events: none; filter: drop-shadow(0 10px 22px rgba(37, 99, 235, 0.14)); }
.mindmap :deep(.mindmap-node rect),
.mindmap :deep(.node rect),
.mindmap :deep(.node circle),
.mindmap :deep(.node ellipse),
.mindmap :deep(.node polygon) { fill: #eff6ff !important; stroke: #60a5fa !important; stroke-width: 1.4px !important; }
.mindmap :deep(.section-root rect),
.mindmap :deep(.section-root circle),
.mindmap :deep(.section-root ellipse) { fill: #2563eb !important; stroke: #1d4ed8 !important; }
.mindmap :deep(text) { fill: #0f172a !important; font-size: 15px !important; font-weight: 600 !important; }
.mindmap :deep(.edge),
.mindmap :deep(path) { stroke: #60a5fa !important; }
.mindmap-error { padding: 24px; color: #1d4ed8; font-weight: 700; background: #eff6ff; border: 1px dashed #93c5fd; border-radius: 8px; }
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
@media (max-width: 1200px) {
  .stage-grid, .agent-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .audit-grid { grid-template-columns: 1fr; }
}
@media (max-width: 1000px) {
  .cards, .request-form { grid-template-columns: 1fr; }
  .status-content { flex-direction: column; }
  .status-metrics { grid-template-columns: 1fr; min-width: 0; }
}
@media (max-width: 700px) {
  .stage-grid, .agent-grid { grid-template-columns: 1fr; }
}
</style>
