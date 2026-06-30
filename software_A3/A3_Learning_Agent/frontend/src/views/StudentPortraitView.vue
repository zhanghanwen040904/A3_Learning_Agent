<template>
  <div class="portrait-view-page">
    <div class="page-header">
      <div>
        <span class="eyebrow">Student Portrait</span>
        <h1>学生画像</h1>
        <p>这里展示系统根据你全部学习对话自动沉淀的综合画像，会随着每一轮交流持续更新。</p>
      </div>

      <div class="header-actions">
        <el-button @click="goToChat">返回对话</el-button>
        <el-button type="primary" :loading="loading" @click="refreshData">刷新画像</el-button>
      </div>
    </div>

    <template v-if="hasAnyMeaningfulProfile">
      <div class="summary-strip">
        <div class="summary-main">
          <span class="summary-label">画像摘要</span>
          <strong>{{ previewSummary }}</strong>
        </div>

        <div class="summary-tags">
          <el-tag
            v-for="item in identifiedTags"
            :key="item.id"
            round
            size="small"
            type="warning"
            effect="plain"
          >
            {{ item.label }}
          </el-tag>
        </div>
      </div>

      <div class="metric-row">
        <div class="metric-card">
          <span>画像完整度</span>
          <strong>{{ Math.round(confidence * 100) }}%</strong>
          <small>{{ completedCount }}/{{ prompts.length }} 个核心维度已识别</small>
        </div>

        <div class="metric-card">
          <span>综合评分</span>
          <strong>{{ overallScore }}分</strong>
          <small>{{ scoringMethod }}</small>
        </div>

        <div class="metric-card">
          <span>当前聚焦课程</span>
          <strong>{{ previewProfile.target_course }}</strong>
          <small>{{ previewProfile.major }}</small>
        </div>
      </div>

      <div class="visual-panel">
        <div class="radar-card">
          <div class="card-header">
            <div>
              <span class="eyebrow">八维画像</span>
              <strong>综合能力分布</strong>
            </div>

            <el-tag round :type="completedCount >= 6 ? 'success' : 'warning'" effect="plain">
              {{ completedCount >= 6 ? "画像已较完整" : "仍在持续补充" }}
            </el-tag>
          </div>

          <div ref="radarRef" class="profile-radar"></div>
        </div>

        <div class="dimension-card-grid">
          <div
            v-for="item in dimensionCards"
            :key="item.id"
            :class="['dimension-card', { filled: item.filled }]"
          >
            <div class="dimension-card-top">
              <span>{{ item.label }}</span>
              <strong>{{ item.score }}</strong>
            </div>
            <p class="dimension-value">{{ item.value }}</p>
            <p class="dimension-reason">{{ item.reason }}</p>
          </div>
        </div>
      </div>

      <div class="timeline-card">
        <div class="card-header">
          <div>
            <span class="eyebrow">最近变化</span>
            <strong>画像更新轨迹</strong>
          </div>
        </div>

        <div class="timeline-list">
          <div v-for="item in timelineItems" :key="item.id" class="timeline-item">
            <span class="timeline-dot"></span>
            <div>
              <strong>{{ item.title }}</strong>
              <p>{{ item.desc }}</p>
            </div>
          </div>
        </div>
      </div>
    </template>

    <el-empty v-else description="当前还没有足够的画像信息，先去对话区交流几轮吧。">
      <el-button type="primary" @click="goToChat">前往对话</el-button>
    </el-empty>
  </div>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref } from "vue";
import { useRouter } from "vue-router";
import * as echarts from "echarts/core";
import { RadarChart } from "echarts/charts";
import { GridComponent, TooltipComponent } from "echarts/components";
import { CanvasRenderer } from "echarts/renderers";
import { profileApi } from "../api";

echarts.use([RadarChart, GridComponent, TooltipComponent, CanvasRenderer]);

const router = useRouter();
const radarRef = ref(null);
const loading = ref(false);
const aggregateProfile = reactive({});
const sessions = ref([]);
let radarChart = null;

const DEFAULT_VALUE = "待进一步观察";
const prompts = [
  { id: "knowledge_base", label: "知识基础" },
  { id: "cognitive_style", label: "认知风格" },
  { id: "error_prone_points", label: "易错点偏好" },
  { id: "study_goal", label: "学习目标" },
  { id: "learning_history", label: "学习历史" },
  { id: "course_progress", label: "课程进度" },
  { id: "study_time_prefer", label: "时间节奏" },
  { id: "preferred_resource", label: "资源偏好" },
];

function normalizeValue(value) {
  const text = String(value || "").trim();
  return text && text !== "undefined" && text !== "null" ? text : DEFAULT_VALUE;
}

function valueOfProfile(primary, legacy) {
  const primaryValue = normalizeValue(aggregateProfile[primary]);
  if (primaryValue !== DEFAULT_VALUE) return primaryValue;
  if (!legacy) return DEFAULT_VALUE;
  return normalizeValue(aggregateProfile[legacy]);
}

const previewProfile = computed(() => ({
  major: valueOfProfile("major"),
  target_course: valueOfProfile("target_course"),
  knowledge_base: valueOfProfile("knowledge_base", "knowledge_level"),
  cognitive_style: valueOfProfile("cognitive_style", "study_style"),
  error_prone_points: valueOfProfile("error_prone_points", "weak_points"),
  study_goal: valueOfProfile("study_goal"),
  learning_history: valueOfProfile("learning_history"),
  course_progress: valueOfProfile("course_progress"),
  study_time_prefer: valueOfProfile("study_time_prefer"),
  preferred_resource: valueOfProfile("preferred_resource"),
  profile_summary: valueOfProfile("profile_summary"),
}));

const portraitScoring = computed(() => aggregateProfile.portrait_scoring || {});
const portraitDimensions = computed(() => portraitScoring.value.dimensions || {});

const completedCount = computed(() => prompts.filter((item) => previewProfile.value[item.id] !== DEFAULT_VALUE).length);
const confidence = computed(() => completedCount.value / prompts.length);
const overallScore = computed(() => Number(portraitScoring.value.overall_score || 0));
const scoringMethod = computed(() => portraitScoring.value.method || "当前主要依据画像识别结果综合判断");

const hasAnyMeaningfulProfile = computed(() => {
  const values = Object.values(previewProfile.value);
  return values.some((item) => item && item !== DEFAULT_VALUE);
});

const identifiedTags = computed(() =>
  prompts.filter((item) => previewProfile.value[item.id] !== DEFAULT_VALUE).slice(0, 4)
);

const previewSummary = computed(() => {
  const summary = previewProfile.value.profile_summary;
  if (summary !== DEFAULT_VALUE) return summary;

  const parts = [];
  if (previewProfile.value.major !== DEFAULT_VALUE) parts.push(`${previewProfile.value.major}方向学生`);
  if (previewProfile.value.target_course !== DEFAULT_VALUE) parts.push(`当前聚焦${previewProfile.value.target_course}`);
  if (previewProfile.value.knowledge_base !== DEFAULT_VALUE) parts.push(`知识基础：${previewProfile.value.knowledge_base}`);
  if (previewProfile.value.error_prone_points !== DEFAULT_VALUE) parts.push(`薄弱点：${previewProfile.value.error_prone_points}`);
  if (previewProfile.value.study_goal !== DEFAULT_VALUE) parts.push(`目标：${previewProfile.value.study_goal}`);
  if (previewProfile.value.cognitive_style !== DEFAULT_VALUE) parts.push(`认知风格：${previewProfile.value.cognitive_style}`);

  return parts.join("；") || "继续进行几轮真实对话后，这里会自动沉淀出你的综合学习画像。";
});

const dimensionScores = computed(() => prompts.map((item) => {
  const backendScore = portraitDimensions.value[item.id]?.score;
  if (backendScore !== undefined && backendScore !== null) return Number(backendScore);
  const value = previewProfile.value[item.id];
  return value && value !== DEFAULT_VALUE ? 60 : 15;
}));

const dimensionCards = computed(() => prompts.map((item, index) => {
  const value = previewProfile.value[item.id];
  const filled = value !== DEFAULT_VALUE;
  const backendInfo = portraitDimensions.value[item.id] || {};
  return {
    ...item,
    value: filled ? value : "当前还未识别出稳定结论，后续会随着对话自动补充。",
    filled,
    score: backendInfo.score !== undefined ? `${backendInfo.score}分` : (filled ? `${dimensionScores.value[index]}分` : "未识别"),
    reason: backendInfo.reason || (filled ? "当前主要依据对话中的画像信息进行判断。" : "当前证据不足，暂时还无法稳定判断该维度。"),
  };
}));

const timelineItems = computed(() => {
  const list = [...sessions.value]
    .sort((a, b) => new Date(b.create_time || b.update_time || 0).getTime() - new Date(a.create_time || a.update_time || 0).getTime())
    .slice(0, 5)
    .map((item) => ({
      id: item.id,
      title: item.title || `画像对话 ${item.id}`,
      desc: normalizeValue(item.profile_summary) !== DEFAULT_VALUE
        ? normalizeValue(item.profile_summary)
        : `创建于 ${formatTime(item.create_time || item.update_time)}`,
    }));

  return list.length
    ? list
    : [
        {
          id: "empty",
          title: "等待第一轮对话",
          desc: "当你开始提问、交流学习情况后，画像变化会自动记录在这里。",
        },
      ];
});

function formatTime(value) {
  if (!value) return "刚刚";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "刚刚";
  return date.toLocaleString("zh-CN", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function goToChat() {
  router.push("/profile");
}

function renderRadar() {
  nextTick(() => {
    if (!radarRef.value || !hasAnyMeaningfulProfile.value) return;
    if (!radarChart) {
      radarChart = echarts.init(radarRef.value);
    }

    radarChart.setOption({
      tooltip: { trigger: "item" },
      radar: {
        radius: "66%",
        center: ["50%", "54%"],
        indicator: prompts.map((item) => ({ name: item.label, max: 100 })),
        axisName: { color: "#475569", fontSize: 12 },
        splitLine: { lineStyle: { color: "#e5e7eb" } },
        splitArea: { areaStyle: { color: ["#ffffff", "#f8fafc"] } },
        axisLine: { lineStyle: { color: "#d1d5db" } },
      },
      series: [
        {
          type: "radar",
          data: [{ value: dimensionScores.value }],
          areaStyle: { color: "rgba(59, 130, 246, 0.16)" },
          lineStyle: { color: "#2563eb", width: 2 },
          itemStyle: { color: "#2563eb" },
          symbolSize: 6,
        },
      ],
    });

    radarChart.resize();
  });
}

async function refreshData() {
  loading.value = true;
  try {
    const [aggregateRes, sessionRes] = await Promise.all([
      profileApi.getAggregate(),
      profileApi.sessions(),
    ]);

    Object.keys(aggregateProfile).forEach((key) => delete aggregateProfile[key]);
    if (aggregateRes.code === 200 && aggregateRes.data) {
      Object.assign(aggregateProfile, aggregateRes.data);
    }

    if (sessionRes.code === 200) {
      sessions.value = sessionRes.data.sessions || [];
    }

    renderRadar();
  } finally {
    loading.value = false;
  }
}

function handleRefreshEvent() {
  refreshData();
}

onMounted(() => {
  refreshData();
  window.addEventListener("resize", renderRadar);
  window.addEventListener("a3-profile-session-refresh", handleRefreshEvent);
});

onBeforeUnmount(() => {
  window.removeEventListener("resize", renderRadar);
  window.removeEventListener("a3-profile-session-refresh", handleRefreshEvent);
  if (radarChart) {
    radarChart.dispose();
    radarChart = null;
  }
});
</script>

<style scoped>
.portrait-view-page {
  min-height: 100vh;
  padding: 32px 40px;
  background: #fff;
  display: grid;
  gap: 18px;
}

.page-header,
.summary-strip,
.card-header,
.dimension-card-top {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
}

.page-header h1 {
  margin: 6px 0 8px;
  font-size: 36px;
  color: #111827;
}

.page-header p {
  margin: 0;
  color: #6b7280;
  line-height: 1.7;
}

.eyebrow {
  display: block;
  color: #94a3b8;
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.header-actions {
  display: flex;
  gap: 12px;
}

.summary-strip,
.metric-card,
.radar-card,
.dimension-card,
.timeline-card {
  border: 1px solid #ececec;
  border-radius: 22px;
  background: #fff;
  box-shadow: 0 8px 30px rgba(15, 23, 42, 0.04);
}

.summary-strip {
  padding: 18px 22px;
}

.summary-main {
  display: grid;
  gap: 8px;
}

.summary-label {
  color: #6b7280;
  font-size: 12px;
  font-weight: 700;
}

.summary-main strong {
  color: #111827;
  line-height: 1.8;
  font-size: 28px;
}

.summary-tags {
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: 8px;
}

.metric-row {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 14px;
}

.metric-card {
  padding: 18px 20px;
}

.metric-card span {
  display: block;
  color: #6b7280;
  font-size: 13px;
  margin-bottom: 10px;
}

.metric-card strong {
  display: block;
  color: #111827;
  font-size: 28px;
  line-height: 1.2;
}

.metric-card small {
  display: block;
  color: #94a3b8;
  margin-top: 8px;
}

.visual-panel {
  display: grid;
  grid-template-columns: 340px minmax(0, 1fr);
  gap: 16px;
}

.radar-card,
.timeline-card {
  padding: 16px 18px;
}

.card-header {
  margin-bottom: 12px;
}

.card-header strong {
  display: block;
  color: #111827;
  font-size: 16px;
}

.profile-radar {
  width: 100%;
  height: 300px;
}

.dimension-card-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
}

.dimension-card {
  min-height: 118px;
  padding: 14px;
  background: #fafafa;
}

.dimension-card.filled {
  background: #f8fbff;
  border-color: #dbeafe;
}

.dimension-card-top {
  margin-bottom: 8px;
}

.dimension-card-top span {
  color: #111827;
  font-size: 13px;
  font-weight: 700;
}

.dimension-card-top strong {
  color: #2563eb;
  font-size: 12px;
}

.dimension-card p {
  margin: 0;
  color: #4b5563;
  font-size: 12px;
  line-height: 1.6;
}

.dimension-value {
  display: -webkit-box;
  overflow: hidden;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 3;
}

.dimension-reason {
  margin-top: 8px !important;
  color: #64748b !important;
}

.timeline-list {
  display: grid;
  gap: 14px;
}

.timeline-item {
  display: flex;
  align-items: flex-start;
  gap: 10px;
}

.timeline-dot {
  width: 9px;
  height: 9px;
  flex: 0 0 auto;
  margin-top: 6px;
  border-radius: 999px;
  background: #2563eb;
  box-shadow: 0 0 0 4px #dbeafe;
}

.timeline-item strong {
  display: block;
  color: #111827;
  font-size: 14px;
}

.timeline-item p {
  margin: 4px 0 0;
  color: #6b7280;
  font-size: 13px;
  line-height: 1.6;
}

@media (max-width: 1200px) {
  .visual-panel {
    grid-template-columns: 1fr;
  }

  .dimension-card-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 768px) {
  .portrait-view-page {
    padding: 20px;
  }

  .page-header,
  .summary-strip,
  .card-header {
    flex-direction: column;
  }

  .metric-row,
  .dimension-card-grid {
    grid-template-columns: 1fr;
  }
}
</style>
