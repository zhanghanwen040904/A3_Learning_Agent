<template>
  <div class="portrait-view-page">
    <div class="page-header">
      <div>
        <span class="eyebrow">Student Portrait</span>
        <h1>学生画像</h1>
        <p>这里展示系统根据全部学习对话自动沉淀的综合学习状态，会随着真实学习交流持续更新。</p>
      </div>

      <div class="header-actions">
        <el-button @click="goToChat">返回对话</el-button>
        <el-button type="primary" :loading="loading" @click="refreshData">刷新画像</el-button>
      </div>
    </div>

    <template v-if="hasAnyMeaningfulProfile">
      <section class="hero-panel">
        <div class="hero-main">
          <span class="eyebrow">综合概览</span>
          <h2>学生学习状态总览</h2>
          <p>{{ previewSummary }}</p>
          <div class="hero-tags">
            <el-tag
              v-for="item in summaryTags"
              :key="item.id"
              round
              size="small"
              effect="plain"
            >
              {{ item.label }}
            </el-tag>
          </div>
        </div>
        <div class="hero-side">
          <div class="hero-side-card">
            <span>当前聚焦课程</span>
            <strong>{{ displayCourse }}</strong>
            <small>{{ displayMajor }}</small>
          </div>
          <div class="hero-side-card">
            <span>画像置信度</span>
            <strong>{{ confidenceLabel }}</strong>
            <small>{{ scoringMethod }}</small>
          </div>
        </div>
      </section>

      <div class="metric-row">
        <div class="metric-card metric-card-primary">
          <span>画像完整度</span>
          <strong>{{ Math.round(completionRatio * 100) }}%</strong>
          <small>{{ completedCount }}/{{ corePrompts.length }} 个核心维度已识别</small>
        </div>

        <div class="metric-card">
          <span>当前综合掌握</span>
          <strong>{{ dynamicProfile.overall_mastery_score || 0 }}分</strong>
          <small>综合自掌握度、答题、错题与资源行为证据</small>
        </div>

        <div class="metric-card">
          <span>更新轨迹</span>
          <strong>{{ portraitHistory.length }}</strong>
          <small>已记录 {{ portraitHistory.length }} 次画像快照</small>
        </div>

        <button class="metric-card knowledge-asset-card" type="button" @click="router.push('/knowledge-jar')">
          <span>知识收藏瓶</span>
          <strong>{{ knowledgeJarStats.total || 0 }} 个</strong>
          <small>查看个人动态知识资产 →</small>
        </button>
      </div>

      <section class="effect-overview">
        <div class="effect-heading">
          <div>
            <span class="eyebrow">Learning Outcomes</span>
            <h2>学习效果概览</h2>
            <p>基于资源学习、阶段任务与测评记录自动统计</p>
          </div>
          <span class="effect-period">近 7 日 · {{ learningEffect.period || "暂无周期数据" }}</span>
        </div>

        <div class="effect-body">
          <div class="effect-stat-grid">
            <article v-for="item in effectStats" :key="item.label" class="effect-stat-card">
              <span>{{ item.label }}</span>
              <strong>{{ item.value }}<small>{{ item.unit }}</small></strong>
              <p>{{ item.hint }}</p>
            </article>
          </div>
          <div class="effect-trend-card">
            <div class="effect-trend-title">
              <strong>学习趋势</strong>
              <span>综合学习时长、任务完成和测评表现</span>
            </div>
            <div ref="effectTrendRef" class="effect-trend-chart"></div>
          </div>
        </div>
      </section>

      <div class="visual-panel">
        <section class="radar-stage">
          <div class="radar-card radar-card-main">
            <div class="card-header">
              <div>
                <span class="eyebrow">核心状态雷达</span>
                <strong>对学生当前学习状态的综合判断</strong>
                <p v-if="radarCompareHint" class="radar-compare-hint">{{ radarCompareHint }}</p>
              </div>
              <div class="radar-meta">
                <div class="radar-legend" v-if="hasHistoryComparison">
                  <span class="legend-item">
                    <i class="legend-dot previous"></i>
                    上一轮画像
                  </span>
                  <span class="legend-item">
                    <i class="legend-dot current"></i>
                    当前画像
                  </span>
                </div>
                <el-tag round :type="completionRatio >= 0.8 ? 'success' : 'warning'" effect="plain">
                  {{ completionRatio >= 0.8 ? "画像已较完整" : "画像仍在持续生长" }}
                </el-tag>
              </div>
            </div>

            <div class="radar-layout">
              <div class="radar-chart-wrap">
                <div ref="radarRef" class="profile-radar"></div>
              </div>
              <div class="radar-highlight-list">
                <div
                  v-for="item in coreCards.slice(0, 4)"
                  :key="`highlight-${item.id}`"
                  class="radar-highlight-item"
                >
                  <span>{{ item.label }}</span>
                  <strong>{{ item.score }}</strong>
                  <small>{{ item.value }}</small>
                </div>
              </div>
            </div>
            <div v-if="hasHistoryComparison" class="portrait-compare-strip">
              <div class="compare-chip">
                <span>上一轮画像</span>
                <strong>{{ formatTime(previousPortraitSnapshot?.create_time) }}</strong>
              </div>
              <div class="compare-chip compare-chip-current">
                <span>当前画像</span>
                <strong>{{ formatTime(currentPortraitSnapshot?.create_time) }}</strong>
              </div>
            </div>
          </div>

          <div class="radar-side-panel">
            <div class="mini-focus-card">
              <span class="eyebrow">当前关注</span>
              <strong>{{ dynamicValue("current_stage_label") }}</strong>
              <p>{{ dynamicValue("weak_knowledge_points") }}</p>
            </div>
            <div class="mini-focus-card">
              <span class="eyebrow">下一步建议</span>
              <strong>{{ previewProfile.recommended_next_step }}</strong>
              <p>{{ dynamicValue("goal_risk") }}</p>
            </div>
          </div>
        </section>

        <div class="portrait-analysis-card" v-if="hasPortraitAnalysisReason">
          <div class="card-header">
            <div>
              <span class="eyebrow">Portrait Diagnosis</span>
              <strong>核心能力诊断</strong>
            </div>
            <el-tag round effect="plain">{{ confidenceLabel }}</el-tag>
          </div>
          <div class="diagnosis-intro">
            <p v-if="portraitScoring.teacher_summary" class="analysis-summary">{{ portraitScoring.teacher_summary }}</p>
            <p v-if="portraitScoring.evidence_summary" class="analysis-evidence">{{ portraitScoring.evidence_summary }}</p>
          </div>
          <div class="diagnosis-grid">
            <article v-for="item in coreCards" :key="item.id" :class="['diagnosis-item', { filled: item.filled }]">
              <div class="diagnosis-item-head">
                <span>{{ item.label }}</span>
                <div><strong>{{ item.score }}</strong><em v-if="item.deltaText" :class="item.deltaClass">{{ item.deltaText }}</em></div>
              </div>
              <el-progress :percentage="Number.parseInt(item.score) || 0" :stroke-width="6" :show-text="false" />
              <b>{{ item.value }}</b>
              <p>{{ item.reason }}</p>
              <details v-if="item.formula || item.changeReason">
                <summary>查看计算依据</summary>
                <small v-if="item.formula">{{ item.formula }}</small>
                <small v-if="item.changeReason">{{ item.changeReason }}</small>
              </details>
            </article>
          </div>
          <div v-if="portraitScoring.overall_comment" class="analysis-next-step">
            <b>下一步建议</b><span>{{ portraitScoring.overall_comment }}</span>
          </div>
        </div>
      </div>

      <section class="learning-trace-panel">
        <div class="trace-heading">
          <div><span class="eyebrow">Growth Signals</span><h2>成长线索与更新记录</h2></div>
          <span>由对话、资源学习、测评与反馈共同沉淀</span>
        </div>
        <div class="trace-overview">
          <div class="support-summary">
            <article v-for="item in supportCards" :key="item.id">
              <span>{{ item.label }}</span><strong>{{ item.value }}</strong>
            </article>
          </div>
          <div class="compact-timeline">
            <div v-for="item in timelineItems.slice(0, 4)" :key="item.id" class="compact-timeline-item">
              <i></i><div><strong>{{ item.title }}</strong><p>{{ item.desc }}</p></div>
            </div>
          </div>
        </div>
        <el-collapse class="evidence-archive">
          <el-collapse-item name="evidence">
            <template #title><div class="evidence-title"><b>学习证据档案</b><span>反馈 {{ resourceFeedbackItems.length }} · 资源行为 {{ resourceUsageItems.length }} · 学习事件 {{ learningEventItems.length }}</span></div></template>
            <div class="evidence-columns">
              <div><h3>资源反馈</h3><div v-if="resourceFeedbackItems.length" class="feedback-evidence-list"><div v-for="(item,index) in resourceFeedbackItems.slice(0,4)" :key="`feedback-${index}`" class="feedback-evidence-item"><strong>{{ item.ratingText }}</strong><p>{{ item.comment }}</p><small>{{ item.time }}</small></div></div><el-empty v-else description="暂无资源反馈" /></div>
              <div><h3>资源使用</h3><div v-if="resourceUsageItems.length" class="feedback-evidence-list"><div v-for="(item,index) in resourceUsageItems.slice(0,4)" :key="`usage-${index}`" class="feedback-evidence-item"><strong>{{ item.resource_type }}</strong><p>{{ item.title }}</p><small>{{ item.time }}</small></div></div><el-empty v-else description="暂无资源使用记录" /></div>
              <div><h3>自适应事件</h3><div v-if="learningEventItems.length" class="feedback-evidence-list"><div v-for="(item,index) in learningEventItems.slice(0,4)" :key="`event-${index}`" class="feedback-evidence-item"><strong>{{ item.event_type }}</strong><p>{{ item.detail }}</p><small>{{ item.time }}</small></div></div><el-empty v-else description="暂无学习行为事件" /></div>
            </div>
          </el-collapse-item>
        </el-collapse>
      </section>
    </template>

    <el-empty v-else description="当前还没有足够的学生画像信息，先去对话区交流几轮吧。">
      <el-button type="primary" @click="goToChat">前往对话</el-button>
    </el-empty>
  </div>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref } from "vue";
import { useRouter } from "vue-router";
import * as echarts from "echarts/core";
import { LineChart, RadarChart } from "echarts/charts";
import { GridComponent, TooltipComponent } from "echarts/components";
import { CanvasRenderer } from "echarts/renderers";
import { evaluationApi, knowledgeJarApi, pathApi, profileApi } from "../api";

echarts.use([LineChart, RadarChart, GridComponent, TooltipComponent, CanvasRenderer]);

const router = useRouter();
const radarRef = ref(null);
const effectTrendRef = ref(null);
const loading = ref(false);
const aggregateProfile = reactive({});
const knowledgeJarStats = reactive({ total: 0, auto_count: 0, manual_count: 0, stage_count: 0 });
const taskProgress = reactive({
  stageCount: 0,
  completedStages: 0,
  completedAssessments: 0,
  quizCount: 0,
});
const sessions = ref([]);
let radarChart = null;
let effectTrendChart = null;
let refreshTimer = null;
let refreshRequestId = 0;
let refreshPending = false;

const DEFAULT_VALUE = "待进一步观察";
const corePrompts = [
  { id: "knowledge_foundation", label: "知识基础" },
  { id: "knowledge_mastery", label: "知识点掌握" },
  { id: "weak_point_distribution", label: "薄弱点分布" },
  { id: "learning_progress", label: "学习进度" },
  { id: "engagement_level", label: "学习投入" },
  { id: "support_match", label: "支持方式匹配" },
  { id: "error_pattern_stability", label: "易错类型稳定性" },
  { id: "goal_attainment_risk", label: "目标达成把握" },
];

const supportPrompts = [
  { id: "current_stage_label", label: "当前学习阶段" },
  { id: "weak_knowledge_points", label: "当前薄弱知识点" },
  { id: "strong_knowledge_points", label: "当前优势知识点" },
  { id: "error_pattern", label: "易错类型" },
  { id: "goal_risk", label: "目标状态" },
  { id: "recommended_next_step", label: "下一步建议" },
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
  current_topic: valueOfProfile("current_topic", "course_progress"),
  mastery_level: valueOfProfile("mastery_level", "knowledge_base"),
  current_difficulty: valueOfProfile("current_difficulty", "error_prone_points"),
  task_goal: valueOfProfile("task_goal", "study_goal"),
  support_preference: valueOfProfile("support_preference", "cognitive_style"),
  engagement_level: valueOfProfile("engagement_level"),
  learning_background: valueOfProfile("learning_background", "learning_history"),
  recent_progress: valueOfProfile("recent_progress", "course_progress"),
  schedule_pattern: valueOfProfile("schedule_pattern", "study_time_prefer"),
  preferred_resource: valueOfProfile("preferred_resource"),
  weak_knowledge_points: valueOfProfile("weak_knowledge_points", "weak_points"),
  recommended_next_step: valueOfProfile("recommended_next_step"),
  portrait_confidence: valueOfProfile("portrait_confidence"),
  profile_summary: valueOfProfile("profile_summary"),
}));

const portraitScoring = computed(() => aggregateProfile.portrait_scoring || {});
const portraitDimensions = computed(() => portraitScoring.value.dimensions || {});
const dynamicProfile = computed(() => aggregateProfile.dynamic_profile || portraitScoring.value.dynamic_profile || {});
const learningEffect = computed(() => aggregateProfile.learning_effect_overview || {});
const pathAssessmentTaskTotal = computed(() => taskProgress.stageCount * 2);
const pathAssessmentCompleted = computed(() =>
  Math.min(pathAssessmentTaskTotal.value, taskProgress.completedStages + taskProgress.completedAssessments)
);
const taskCompletionRate = computed(() => {
  if (pathAssessmentTaskTotal.value > 0) {
    return Math.round((pathAssessmentCompleted.value / pathAssessmentTaskTotal.value) * 100);
  }
  return Number(learningEffect.value.task_completion_rate || 0);
});
const completedTaskCount = computed(() => {
  if (pathAssessmentTaskTotal.value > 0) return pathAssessmentCompleted.value;
  return Number(learningEffect.value.completed_tasks || 0);
});
const taskCompletionHint = computed(() => {
  if (pathAssessmentTaskTotal.value > 0) {
    return `阶段完成 ${taskProgress.completedStages}/${taskProgress.stageCount}，阶段测评 ${taskProgress.completedAssessments}/${taskProgress.stageCount}`;
  }
  return "资源学习进度均值";
});

function formatStudyDuration(seconds) {
  const value = Math.max(0, Number(seconds) || 0);
  if (value >= 3600) return { value: (value / 3600).toFixed(1), unit: "小时" };
  if (value > 0 && value < 60) return { value: "<1", unit: "分钟" };
  return { value: Math.round(value / 60), unit: "分钟" };
}

const effectStats = computed(() => {
  const duration = formatStudyDuration(learningEffect.value.total_duration_sec);
  return [
    { label: "学习时长", value: duration.value, unit: duration.unit, hint: "来自资源实际停留时长" },
    { label: "完成任务", value: completedTaskCount.value, unit: "个", hint: "已完成学习阶段与阶段测评" },
    { label: "任务完成度", value: taskCompletionRate.value, unit: "%", hint: taskCompletionHint.value },
    { label: "测评正确率", value: learningEffect.value.correct_rate || 0, unit: "%", hint: `累计 ${taskProgress.quizCount || learningEffect.value.quiz_count || 0} 次测评` },
  ];
});

function dynamicValue(key) {
  return normalizeValue(dynamicProfile.value[key]);
}

const portraitReasonCards = computed(() =>
  corePrompts.map((item) => {
    const info = portraitDimensions.value[item.id] || {};
    const reason = normalizeValue(info.reason);
    const teacherJudgement = normalizeValue(info.teacher_judgement);
    return {
      ...item,
      score: info.score !== undefined && info.score !== null && info.score !== "" ? `${info.score}分` : "评估中",
      level: info.level || "待观察",
      teacher_judgement: teacherJudgement !== DEFAULT_VALUE ? teacherJudgement : "",
      reason: reason !== DEFAULT_VALUE ? reason : "该维度正在等待更多答题、错题或学习行为证据。",
    };
  }).filter((item) => item.teacher_judgement || item.reason)
);

const hasPortraitAnalysisReason = computed(() =>
  Boolean(
    portraitScoring.value.teacher_summary
    || portraitScoring.value.evidence_summary
    || portraitScoring.value.overall_comment
    || portraitReasonCards.value.length
  )
);
const portraitHistory = computed(() =>
  Array.isArray(aggregateProfile.portrait_history) ? aggregateProfile.portrait_history : []
);
const currentPortraitSnapshot = computed(() => portraitHistory.value[0] || null);
const previousPortraitSnapshot = computed(() => portraitHistory.value[1] || null);
const currentSnapshotDimensions = computed(() =>
  currentPortraitSnapshot.value?.portrait_scoring?.dimensions || {}
);
const previousSnapshotDimensions = computed(() =>
  previousPortraitSnapshot.value?.portrait_scoring?.dimensions || {}
);
const hasHistoryComparison = computed(() =>
  Boolean(currentPortraitSnapshot.value && previousPortraitSnapshot.value)
);
const completedCount = computed(() =>
  corePrompts.filter((item) => {
    const score = Number(portraitDimensions.value[item.id]?.score);
    return !Number.isNaN(score) && score > 0;
  }).length
);
const completionRatio = computed(() => {
  const backendRatio = Number(portraitScoring.value.completion_ratio);
  if (!Number.isNaN(backendRatio) && backendRatio > 0) return backendRatio;
  return completedCount.value / Math.max(corePrompts.length, 1);
});
const confidenceLabel = computed(() => {
  if (portraitScoring.value.confidence_label) return portraitScoring.value.confidence_label;
  if (completedCount.value >= 6) return "较完整";
  if (completedCount.value >= 4) return "初步形成";
  return "待观察";
});
const scoringMethod = computed(() =>
  portraitScoring.value.method || "当前画像已开始根据学习证据动态更新。"
);

const hasAnyMeaningfulProfile = computed(() => {
  const values = [
    ...Object.values(previewProfile.value),
    ...corePrompts.map((item) => dynamicValue(item.id)),
  ];
  return values.some((item) => item && item !== DEFAULT_VALUE);
});

const displayCourse = computed(() =>
  previewProfile.value.target_course !== DEFAULT_VALUE
    ? previewProfile.value.target_course
    : (previewProfile.value.current_topic !== DEFAULT_VALUE ? previewProfile.value.current_topic : "待观察")
);

const displayMajor = computed(() =>
  previewProfile.value.major !== DEFAULT_VALUE ? previewProfile.value.major : "专业信息待观察"
);

const summaryTags = computed(() =>
  corePrompts.filter((item) => dynamicValue(item.id) !== DEFAULT_VALUE).slice(0, 4)
);

const previewSummary = computed(() => {
  if (portraitScoring.value.teacher_summary) return portraitScoring.value.teacher_summary;
  const summary = previewProfile.value.profile_summary;
  if (summary !== DEFAULT_VALUE) return summary;
  const parts = [];
  if (displayCourse.value !== DEFAULT_VALUE) parts.push(`当前课程：${displayCourse.value}`);
  if (dynamicValue("learning_progress") !== DEFAULT_VALUE) parts.push(dynamicValue("learning_progress"));
  if (dynamicValue("weak_point_distribution") !== DEFAULT_VALUE) parts.push(dynamicValue("weak_point_distribution"));
  if (dynamicValue("goal_attainment_risk") !== DEFAULT_VALUE) parts.push(dynamicValue("goal_attainment_risk"));
  return parts.join("；") || "继续进行真实学习、答题与反馈后，这里会形成更稳定的动态学生画像。";
});

const dimensionScores = computed(() =>
  corePrompts.map((item) => {
    const backendScore = currentSnapshotDimensions.value[item.id]?.score ?? portraitDimensions.value[item.id]?.score;
    if (backendScore !== undefined && backendScore !== null && backendScore !== "") {
      return Number(backendScore);
    }
    return 0;
  })
);
const previousDimensionScores = computed(() =>
  corePrompts.map((item) => {
    const previousScore = previousSnapshotDimensions.value[item.id]?.score;
    if (previousScore !== undefined && previousScore !== null && previousScore !== "") {
      return Number(previousScore);
    }
    return 0;
  })
);
const radarCompareHint = computed(() => {
  if (hasHistoryComparison.value) {
    const previousTime = formatTime(previousPortraitSnapshot.value?.create_time);
    const currentTime = formatTime(currentPortraitSnapshot.value?.create_time);
    return `浅色表示上一轮画像（${previousTime}），深色表示当前画像（${currentTime}）。每次真实学习、答题和反馈后，画像都会继续更新。`;
  }
  if (currentPortraitSnapshot.value) {
    return "当前已经形成一轮画像；继续学习后，这里会展示上一轮与当前轮的变化对比。";
  }
  return "";
});

const coreCards = computed(() =>
  corePrompts.map((item) => {
    const value = dynamicValue(item.id);
    const backendInfo = portraitDimensions.value[item.id] || {};
    const previousInfo = previousSnapshotDimensions.value[item.id] || {};
    const formula = normalizeValue(dynamicProfile.value.score_details?.[item.id]);
    const filled = value !== DEFAULT_VALUE;
    const currentScore = backendInfo.score !== undefined ? Number(backendInfo.score) : null;
    const previousScore = previousInfo.score !== undefined ? Number(previousInfo.score) : null;
    const hasDelta = currentScore !== null && previousScore !== null && !Number.isNaN(currentScore) && !Number.isNaN(previousScore);
    const delta = hasDelta ? currentScore - previousScore : 0;
    let deltaText = "";
    let deltaClass = "";
    let changeReason = "";
    if (hasDelta) {
      if (delta > 0) {
        deltaText = `+${delta}`;
        deltaClass = "up";
        changeReason = `较上一轮上升 ${delta} 分。通常表示近期在这个维度上新增了更有利的学习证据。`;
      } else if (delta < 0) {
        deltaText = `${delta}`;
        deltaClass = "down";
        changeReason = `较上一轮下降 ${Math.abs(delta)} 分。通常表示近期错题、薄弱点或目标压力在这个维度上占比更高。`;
      } else {
        deltaText = "0";
        deltaClass = "flat";
        changeReason = "与上一轮持平，说明当前新增证据暂未显著改变该维度判断。";
      }
    }
    return {
      ...item,
      value: filled ? value : "当前证据还不足，系统会在后续对话、答题和资源反馈后继续补全。",
      filled,
      score: backendInfo.score !== undefined ? `${backendInfo.score}分` : (filled ? "评估中" : "待识别"),
      reason: backendInfo.reason || (filled ? "该维度已接入学习证据，后续会继续根据新记录自动修正。" : "当前尚缺少足够学习证据，暂时无法稳定判断。"),
      formula: formula !== DEFAULT_VALUE ? formula : "",
      deltaText,
      deltaClass,
      changeReason,
    };
  })
);

const supportCards = computed(() => {
  const supportData = {
    current_stage_label: dynamicValue("current_stage_label"),
    weak_knowledge_points: dynamicValue("weak_knowledge_points"),
    strong_knowledge_points: dynamicValue("strong_knowledge_points"),
    error_pattern: dynamicValue("error_pattern"),
    goal_risk: dynamicValue("goal_risk"),
    recommended_next_step: previewProfile.value.recommended_next_step,
  };
  return supportPrompts.map((item) => ({
    ...item,
    value: supportData[item.id] !== DEFAULT_VALUE ? supportData[item.id] : "待进一步观察",
  }));
});

const resourceFeedbackItems = computed(() =>
  (aggregateProfile.resource_feedback || []).slice(0, 6).map((item) => ({
    ratingText: item.rating ? `${item.rating} / 5 分反馈` : "资源反馈",
    comment: normalizeValue(item.comment) !== DEFAULT_VALUE ? normalizeValue(item.comment) : "学生未填写具体文字反馈，系统已记录评分。",
    time: formatTime(item.time),
  }))
);

const resourceUsageItems = computed(() =>
  (aggregateProfile.resource_usage || []).slice(0, 6).map((item) => ({
    resource_type: normalizeValue(item.resource_type) !== DEFAULT_VALUE ? normalizeValue(item.resource_type) : "学习资源",
    title: normalizeValue(item.title) !== DEFAULT_VALUE ? normalizeValue(item.title) : "资源标题待记录",
    time: formatTime(item.time),
  }))
);

const learningEventItems = computed(() =>
  (aggregateProfile.learning_events || []).slice(0, 8).map((item) => ({
    event_type: normalizeValue(item.event_type) !== DEFAULT_VALUE ? normalizeValue(item.event_type) : "学习事件",
    detail: normalizeValue(item.detail) !== DEFAULT_VALUE ? normalizeValue(item.detail) : "系统已记录一次新的学习行为。",
    time: formatTime(item.time),
  }))
);

const timelineItems = computed(() => {
  const list = portraitHistory.value
    .slice(0, 6)
    .map((item) => ({
      id: item.id,
      title: formatTime(item.create_time),
      desc: normalizeValue(item.profile_summary) !== DEFAULT_VALUE
        ? normalizeValue(item.profile_summary)
        : normalizeValue(item.portrait_scoring?.overall_comment) !== DEFAULT_VALUE
          ? normalizeValue(item.portrait_scoring?.overall_comment)
          : "画像已根据新学习证据完成一次更新。",
    }));

  return list.length
    ? list
    : [
        {
          id: "empty",
          title: "等待更多学习记录",
          desc: "当你继续提问、学习、做题或复盘后，这里会持续记录画像变化。",
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
    if (!radarChart) radarChart = echarts.init(radarRef.value);

    const seriesData = [];
    if (hasHistoryComparison.value) {
      seriesData.push({
        value: previousDimensionScores.value,
        name: "上一轮画像",
        areaStyle: { color: "rgba(196, 181, 253, 0.10)" },
        lineStyle: { color: "#c4b5fd", width: 2, type: "dashed" },
        itemStyle: { color: "#c4b5fd" },
        symbolSize: 5,
      });
    }
    seriesData.push({
      value: dimensionScores.value,
      name: "当前画像",
      areaStyle: { color: "rgba(109, 93, 252, 0.18)" },
      lineStyle: { color: "#6d5dfc", width: 2.5 },
      itemStyle: { color: "#6d5dfc" },
      symbolSize: 6,
    });

    radarChart.setOption({
      tooltip: {
        trigger: "item",
        confine: true,
      },
      radar: {
        radius: "66%",
        center: ["50%", "56%"],
        indicator: corePrompts.map((item) => ({ name: item.label, max: 100 })),
        axisName: { color: "#475569", fontSize: 12 },
        splitLine: { lineStyle: { color: "#e8edf7" } },
        splitArea: { areaStyle: { color: ["#ffffff", "#f8faff"] } },
        axisLine: { lineStyle: { color: "#d8e3f5" } },
      },
      series: [
        {
          type: "radar",
          data: seriesData,
        },
      ],
    });

    radarChart.resize();
  });
}

function renderEffectTrend() {
  nextTick(() => {
    if (!effectTrendRef.value || !hasAnyMeaningfulProfile.value) return;
    if (!effectTrendChart) effectTrendChart = echarts.init(effectTrendRef.value);
    const trend = Array.isArray(learningEffect.value.trend) ? learningEffect.value.trend : [];
    effectTrendChart.setOption({
      grid: { left: 34, right: 18, top: 28, bottom: 28 },
      tooltip: {
        trigger: "axis",
        confine: true,
        formatter(params) {
          const index = params?.[0]?.dataIndex || 0;
          const item = trend[index] || {};
          return `${item.date || ""}<br/>学习活跃度：${item.activity_score || 0}<br/>学习时长：${Math.round((item.duration_sec || 0) / 60)} 分钟<br/>完成任务：${item.completed_tasks || 0} 个<br/>测评均分：${item.avg_score || 0}%`;
        },
      },
      xAxis: {
        type: "category",
        boundaryGap: false,
        data: trend.map((item) => item.date),
        axisLine: { lineStyle: { color: "#dbe5f2" } },
        axisTick: { show: false },
        axisLabel: { color: "#7b8798", fontSize: 11 },
      },
      yAxis: {
        type: "value",
        min: 0,
        max: 100,
        splitNumber: 4,
        axisLabel: { color: "#94a3b8", fontSize: 11 },
        splitLine: { lineStyle: { color: "#edf2f8" } },
      },
      series: [{
        name: "学习活跃度",
        type: "line",
        smooth: 0.35,
        symbol: "circle",
        symbolSize: 7,
        data: trend.map((item) => item.activity_score || 0),
        lineStyle: { color: "#3478f6", width: 3 },
        itemStyle: { color: "#3478f6", borderColor: "#ffffff", borderWidth: 2 },
        areaStyle: { color: "rgba(52, 120, 246, 0.09)" },
      }],
    });
    effectTrendChart.resize();
  });
}

function renderCharts() {
  renderRadar();
  renderEffectTrend();
}

function readCompletedAssessmentRecords() {
  try {
    const records = JSON.parse(localStorage.getItem("a3_stage_assessment_records") || "[]");
    if (!Array.isArray(records)) return 0;
    return new Set(records.filter((item) => item?.completed).map((item) => Number(item.stageIndex))).size;
  } catch {
    return 0;
  }
}

function stageCountFromIntegrated(value) {
  const stages = value?.stages;
  if (Array.isArray(stages)) return stages.length;
  return 0;
}

async function refreshTaskProgress() {
  const [integratedRes, stageProgressRes, summaryRes] = await Promise.all([
    pathApi.integrated(),
    pathApi.stageProgress(),
    evaluationApi.summary(),
  ]);

  const stageItems = stageProgressRes.code === 200 && Array.isArray(stageProgressRes.data?.items)
    ? stageProgressRes.data.items
    : [];
  const stageCount = stageCountFromIntegrated(integratedRes.code === 200 ? integratedRes.data : {});
  taskProgress.stageCount = Math.max(stageCount, stageItems.length);
  taskProgress.completedStages = stageItems.filter((item) => item.completed).length;
  taskProgress.completedAssessments = readCompletedAssessmentRecords();
  taskProgress.quizCount = summaryRes.code === 200 ? Number(summaryRes.data?.quiz_count || 0) : 0;
}

async function refreshData() {
  if (loading.value) {
    refreshPending = true;
    return;
  }
  refreshPending = false;
  const requestId = ++refreshRequestId;
  loading.value = true;
  try {
    const [aggregateRes, sessionRes, jarRes] = await Promise.all([
      profileApi.getAggregate(),
      profileApi.sessions(),
      knowledgeJarApi.list(),
      refreshTaskProgress(),
    ]);

    if (requestId !== refreshRequestId) return;

    Object.keys(aggregateProfile).forEach((key) => delete aggregateProfile[key]);
    if (aggregateRes.code === 200 && aggregateRes.data) {
      Object.assign(aggregateProfile, aggregateRes.data);
    }

    if (sessionRes.code === 200) {
      sessions.value = sessionRes.data.sessions || [];
    }
    if (jarRes.code === 200) Object.assign(knowledgeJarStats, jarRes.data?.stats || {});

    renderCharts();
  } finally {
    if (requestId === refreshRequestId) {
      loading.value = false;
      if (refreshPending) {
        refreshData();
      }
    }
  }
}

function handleRefreshEvent() {
  if (refreshTimer) clearTimeout(refreshTimer);
  refreshTimer = setTimeout(() => {
    refreshTimer = null;
    refreshData();
  }, 350);
}

onMounted(() => {
  refreshData();
  window.addEventListener("resize", renderCharts);
  window.addEventListener("a3-profile-session-refresh", handleRefreshEvent);
});

onBeforeUnmount(() => {
  if (refreshTimer) {
    clearTimeout(refreshTimer);
    refreshTimer = null;
  }
  window.removeEventListener("resize", renderCharts);
  window.removeEventListener("a3-profile-session-refresh", handleRefreshEvent);
  if (radarChart) {
    radarChart.dispose();
    radarChart = null;
  }
  if (effectTrendChart) {
    effectTrendChart.dispose();
    effectTrendChart = null;
  }
});
</script>

<style scoped>
.portrait-view-page {
  min-height: 100vh;
  padding: 24px 28px 32px;
  background: #f5f7fb;
  display: grid;
  gap: 18px;
}

.page-header,
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
  color: #0f172a;
}

.page-header p {
  margin: 0;
  color: #64748b;
}

.eyebrow {
  font-size: 12px;
  font-weight: 700;
  letter-spacing: .04em;
  color: #4386d8;
}

.header-actions {
  display: flex;
  gap: 12px;
}

.hero-panel,
.metric-card,
.effect-overview,
.radar-card,
.portrait-analysis-card,
.dimension-card,
.support-card,
.timeline-card {
  border: 1px solid #e6ebf2;
  background: #ffffff;
  border-radius: 20px;
  box-shadow: 0 8px 24px rgba(15, 23, 42, 0.04);
}

.hero-panel {
  padding: 24px 26px;
  display: grid;
  grid-template-columns: minmax(0, 1.55fr) minmax(260px, 0.75fr);
  gap: 16px;
  color: #0f172a;
}

.hero-main {
  display: grid;
  gap: 14px;
}

.hero-main h2 {
  margin: 0;
  font-size: 26px;
  line-height: 1.2;
  color: #0f172a;
}

.hero-main p {
  margin: 0;
  font-size: 15px;
  line-height: 1.85;
  color: #475569;
}

.hero-tags {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
}

.hero-tags :deep(.el-tag) {
  border-color: #d9e2ef;
  background: #f8fafc;
  color: #516072;
}

.hero-side {
  display: grid;
  gap: 12px;
}

.hero-side-card {
  border-radius: 16px;
  padding: 18px 20px;
  background: #f8fafc;
  border: 1px solid #e6ebf2;
  display: grid;
  gap: 8px;
}

.hero-side-card span,
.hero-side-card small {
  color: #64748b;
}

.hero-side-card strong {
  color: #0f172a;
  font-size: 24px;
  line-height: 1.2;
}

.metric-row {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
}

.metric-card {
  padding: 18px 20px;
  display: grid;
  gap: 8px;
}

.metric-card span,
.metric-card small {
  color: #64748b;
}

.metric-card strong {
  font-size: 24px;
  color: #0f172a;
}

.metric-card-primary {
  border-color: #d9e2ef;
}

.knowledge-asset-card {
  width: 100%;
  border: 1px solid #d6e5fb;
  background: linear-gradient(135deg, #ffffff, #f2f7ff);
  text-align: left;
  cursor: pointer;
  font: inherit;
  transition: 0.2s ease;
}

.knowledge-asset-card:hover {
  transform: translateY(-2px);
  border-color: #73a6f2;
  box-shadow: 0 12px 26px rgba(37, 99, 235, 0.1);
}

.knowledge-asset-card strong {
  color: #2867d8;
}

.effect-overview {
  padding: 22px 24px;
}

.effect-heading,
.effect-trend-title {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
}

.effect-heading h2 {
  margin: 5px 0 4px;
  color: #0f172a;
  font-size: 22px;
}

.effect-heading p,
.effect-trend-title span {
  margin: 0;
  color: #8491a3;
  font-size: 13px;
}

.effect-period {
  padding: 7px 11px;
  border-radius: 999px;
  background: #f3f7fd;
  color: #607089;
  font-size: 12px;
  white-space: nowrap;
}

.effect-body {
  margin-top: 18px;
  display: grid;
  grid-template-columns: minmax(360px, .85fr) minmax(460px, 1.15fr);
  gap: 18px;
}

.effect-stat-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}

.effect-stat-card,
.effect-trend-card {
  border: 1px solid #e5ebf4;
  border-radius: 16px;
  background: #fbfcff;
}

.effect-stat-card {
  padding: 16px 18px;
  display: grid;
  align-content: center;
  gap: 7px;
}

.effect-stat-card > span,
.effect-stat-card p {
  color: #718096;
  font-size: 12px;
}

.effect-stat-card strong {
  color: #175fd2;
  font-size: 28px;
  line-height: 1;
}

.effect-stat-card strong small {
  margin-left: 5px;
  color: #52627a;
  font-size: 13px;
  font-weight: 600;
}

.effect-stat-card p {
  margin: 0;
}

.effect-trend-card {
  padding: 16px 18px 8px;
  min-width: 0;
}

.effect-trend-title strong {
  color: #26354d;
  font-size: 14px;
}

.effect-trend-chart {
  height: 210px;
}

.visual-panel {
  display: grid;
  gap: 14px;
}

.radar-stage {
  display: grid;
  grid-template-columns: minmax(0, 1.9fr) minmax(240px, 0.6fr);
  gap: 14px;
}

.radar-card-main {
  background: #ffffff;
}

.radar-layout {
  display: grid;
  grid-template-columns: minmax(0, 1.45fr) minmax(210px, 0.55fr);
  align-items: center;
  gap: 12px;
}

.radar-chart-wrap {
  min-width: 0;
  padding: 0 6px 0 0;
}

.radar-highlight-list {
  display: grid;
  gap: 10px;
}

.radar-highlight-item {
  padding: 14px 16px;
  border-radius: 14px;
  background: #f8fafc;
  border: 1px solid #e6ebf2;
  display: grid;
  gap: 6px;
}

.radar-highlight-item span {
  color: #64748b;
  font-size: 12px;
  font-weight: 700;
}

.radar-highlight-item strong {
  color: #1e293b;
  font-size: 18px;
}

.radar-highlight-item small {
  color: #475569;
  font-size: 13px;
  line-height: 1.6;
}

.portrait-compare-strip {
  margin-top: 14px;
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
}

.compare-chip {
  min-width: 160px;
  padding: 10px 12px;
  border-radius: 14px;
  border: 1px solid #ddd6fe;
  background: #f8f5ff;
  display: grid;
  gap: 4px;
}

.compare-chip span {
  font-size: 12px;
  color: #7c6bb3;
}

.compare-chip strong {
  color: #4338ca;
  font-size: 14px;
}

.compare-chip-current {
  border-color: #c7d2fe;
  background: #eef2ff;
}

.radar-side-panel {
  display: grid;
  gap: 12px;
}

.mini-focus-card {
  border: 1px solid #e6ebf2;
  background: #ffffff;
  border-radius: 20px;
  box-shadow: 0 8px 24px rgba(15, 23, 42, 0.04);
  padding: 18px 20px;
  display: grid;
  gap: 8px;
}

.mini-focus-card strong {
  color: #0f172a;
  font-size: 22px;
  line-height: 1.4;
}

.mini-focus-card p {
  margin: 0;
  color: #64748b;
  line-height: 1.7;
}

.portrait-analysis-card {
  display: grid;
  gap: 16px;
  background: #ffffff;
}

.analysis-summary,
.analysis-evidence,
.analysis-next-step,
.analysis-reason-item p,
.analysis-reason-item small {
  margin: 0;
  line-height: 1.75;
}

.analysis-summary {
  color: #0f172a;
  font-size: 15px;
  font-weight: 600;
}

.analysis-evidence {
  color: #64748b;
  font-size: 14px;
}

.analysis-reason-list {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
}

.analysis-reason-item {
  padding: 14px 16px;
  border: 1px solid #e6ebf2;
  border-radius: 14px;
  background: #f8fafc;
  display: grid;
  gap: 8px;
}

.analysis-reason-item div {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
}

.analysis-reason-item b {
  color: #0f172a;
  font-size: 14px;
}

.analysis-reason-item span {
  color: #5b6b82;
  font-size: 12px;
  font-weight: 700;
  white-space: nowrap;
}

.analysis-reason-item p {
  color: #1e293b;
  font-size: 13px;
  font-weight: 600;
}

.analysis-reason-item small {
  color: #64748b;
  font-size: 12px;
}

.analysis-next-step {
  padding: 14px 16px;
  border-radius: 14px;
  background: #f8fafc;
  color: #334155;
  display: flex;
  gap: 10px;
  align-items: flex-start;
}

.analysis-next-step b {
  white-space: nowrap;
}

.radar-card,
.portrait-analysis-card,
.timeline-card,
.secondary-panel {
  padding: 18px 20px;
}

.profile-radar {
  height: 460px;
  width: 100%;
}

.radar-meta {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
  justify-content: flex-end;
}

.radar-legend {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}

.legend-item {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  color: #64748b;
  font-size: 12px;
  font-weight: 600;
}

.legend-dot {
  width: 10px;
  height: 10px;
  border-radius: 999px;
  display: inline-block;
}

.legend-dot.previous {
  background: #cbd5e1;
  box-shadow: 0 0 0 4px rgba(203, 213, 225, 0.18);
}

.legend-dot.current {
  background: #64748b;
  box-shadow: 0 0 0 4px rgba(100, 116, 139, 0.12);
}

.radar-compare-hint {
  margin: 10px 0 0;
  color: #64748b;
  font-size: 13px;
  line-height: 1.7;
  max-width: 360px;
}

.dimension-card-grid,
.support-grid {
  display: grid;
  gap: 12px;
}

.dimension-card-grid {
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.support-grid {
  grid-template-columns: repeat(3, minmax(0, 1fr));
}

.dimension-card,
.support-card {
  padding: 18px 18px 16px;
}

.dimension-card.filled {
  border-color: #dbe3ee;
  box-shadow: 0 10px 24px rgba(15, 23, 42, 0.05);
}

.dimension-card-top span,
.support-card span {
  color: #64748b;
  font-size: 13px;
  font-weight: 600;
}

.dimension-card-top strong {
  color: #0f172a;
  font-size: 14px;
}

.dimension-score-wrap {
  display: flex;
  align-items: center;
  gap: 8px;
}

.dimension-delta {
  font-size: 12px;
  font-weight: 700;
}

.dimension-delta.up {
  color: #16a34a;
}

.dimension-delta.down {
  color: #dc2626;
}

.dimension-delta.flat {
  color: #94a3b8;
}

.dimension-value,
.dimension-reason,
.support-card strong {
  margin: 0;
  line-height: 1.7;
}

.dimension-value,
.support-card strong {
  color: #0f172a;
  font-size: 16px;
}

.dimension-reason {
  margin-top: 10px;
  color: #64748b;
  font-size: 13px;
}

.dimension-formula {
  margin: 8px 0 0;
  color: #94a3b8;
  font-size: 12px;
  line-height: 1.7;
}

.dimension-change {
  margin: 8px 0 0;
  color: #475569;
  font-size: 12px;
  line-height: 1.7;
}

.section-header {
  display: grid;
  gap: 6px;
  margin-bottom: 16px;
}

.section-header strong {
  color: #0f172a;
  font-size: 20px;
}

.timeline-list {
  display: grid;
  gap: 12px;
}

.timeline-item {
  display: grid;
  grid-template-columns: 14px 1fr;
  gap: 12px;
  align-items: start;
}

.timeline-dot {
  width: 10px;
  height: 10px;
  margin-top: 7px;
  border-radius: 999px;
  background: #94a3b8;
  box-shadow: 0 0 0 4px rgba(148, 163, 184, 0.12);
}

.timeline-item strong {
  color: #0f172a;
}

.timeline-item p {
  margin: 6px 0 0;
  color: #64748b;
  line-height: 1.6;
}

@media (max-width: 1280px) {
  .hero-panel,
  .effect-body,
  .radar-stage,
  .radar-layout {
    grid-template-columns: 1fr;
  }

  .profile-radar {
    height: 420px;
  }

  .support-grid,
  .dimension-card-grid,
  .analysis-reason-list,
  .metric-row {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 860px) {
  .portrait-view-page {
    padding: 16px;
  }

  .page-header,
  .hero-panel {
    flex-direction: column;
  }

  .support-grid,
  .effect-stat-grid,
  .dimension-card-grid,
  .analysis-reason-list,
  .metric-row {
    grid-template-columns: 1fr;
  }

  .profile-radar {
    height: 360px;
  }

  .effect-heading,
  .effect-trend-title {
    flex-direction: column;
  }
}

.feedback-evidence-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 18px;
}
.feedback-evidence-card {
  padding: 22px;
  border-radius: 24px;
  border: 1px solid #e7ecf5;
  background: linear-gradient(180deg, #ffffff 0%, #f9fbff 100%);
  box-shadow: 0 10px 30px rgba(15, 23, 42, 0.05);
}
.feedback-evidence-card-wide {
  grid-column: 1 / -1;
}
.feedback-evidence-list {
  display: grid;
  gap: 12px;
}
.feedback-evidence-item {
  padding: 14px 16px;
  border-radius: 16px;
  background: #ffffff;
  border: 1px solid #ecf1f7;
}
.feedback-evidence-item strong {
  display: block;
  color: #0f172a;
  font-size: 14px;
}
.feedback-evidence-item p {
  margin: 6px 0 4px;
  color: #475569;
  line-height: 1.7;
}
.feedback-evidence-item small {
  color: #94a3b8;
}
@media (max-width: 960px) {
  .feedback-evidence-grid {
    grid-template-columns: 1fr;
  }
  .feedback-evidence-card-wide {
    grid-column: auto;
  }
}

.diagnosis-intro {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}
.diagnosis-intro p {
  margin: 0;
  padding: 14px 16px;
  border-radius: 14px;
  background: #f6f9fd;
  color: #526072;
  font-size: 13px;
  line-height: 1.7;
}
.diagnosis-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
}
.diagnosis-item {
  min-width: 0;
  padding: 15px;
  border: 1px solid #e3eaf3;
  border-radius: 16px;
  background: linear-gradient(145deg, #ffffff, #f8fbff);
}
.diagnosis-item-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  margin-bottom: 10px;
}
.diagnosis-item-head > span { color: #526072; font-size: 13px; font-weight: 700; }
.diagnosis-item-head div { display: flex; align-items: center; gap: 5px; }
.diagnosis-item-head strong { color: #172033; font-size: 18px; }
.diagnosis-item-head em { color: #94a3b8; font-size: 11px; font-style: normal; }
.diagnosis-item-head em.up { color: #159a73; }
.diagnosis-item-head em.down { color: #e56a68; }
.diagnosis-item > b {
  display: -webkit-box;
  overflow: hidden;
  margin-top: 10px;
  color: #172033;
  font-size: 13px;
  line-height: 1.55;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 2;
}
.diagnosis-item > p {
  display: -webkit-box;
  overflow: hidden;
  margin: 6px 0 0;
  color: #718096;
  font-size: 12px;
  line-height: 1.6;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 3;
}
.diagnosis-item details { margin-top: 9px; color: #64748b; font-size: 11px; }
.diagnosis-item summary { color: #2f72dc; cursor: pointer; }
.diagnosis-item details small { display: block; margin-top: 7px; line-height: 1.6; }

.learning-trace-panel {
  padding: 22px 24px;
  border: 1px solid #e3eaf3;
  border-radius: 24px;
  background: #fff;
  box-shadow: 0 10px 30px rgba(15, 23, 42, .045);
}
.trace-heading { display: flex; align-items: flex-end; justify-content: space-between; gap: 20px; }
.trace-heading h2 { margin: 5px 0 0; color: #111827; font-size: 24px; }
.trace-heading > span { color: #8a99ad; font-size: 12px; }
.trace-overview {
  display: grid;
  grid-template-columns: minmax(0, 1.2fr) minmax(320px, .8fr);
  gap: 18px;
  margin-top: 18px;
}
.support-summary { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 10px; }
.support-summary article { padding: 13px 14px; border: 1px solid #e7edf5; border-radius: 14px; background: #f8fafc; }
.support-summary span { display: block; color: #78879a; font-size: 11px; }
.support-summary strong { display: -webkit-box; overflow: hidden; margin-top: 5px; color: #1f2937; font-size: 13px; line-height: 1.55; -webkit-box-orient: vertical; -webkit-line-clamp: 2; }
.compact-timeline { padding: 4px 0 4px 16px; border-left: 1px solid #dce6f2; }
.compact-timeline-item { position: relative; display: grid; grid-template-columns: 8px minmax(0, 1fr); gap: 10px; padding: 0 0 13px; }
.compact-timeline-item:last-child { padding-bottom: 0; }
.compact-timeline-item i { width: 8px; height: 8px; margin-left: -20px; border: 2px solid #fff; border-radius: 50%; background: #4f8df7; box-shadow: 0 0 0 2px #dbeafe; }
.compact-timeline-item strong { color: #334155; font-size: 12px; }
.compact-timeline-item p { display: -webkit-box; overflow: hidden; margin: 3px 0 0; color: #7b899c; font-size: 11px; line-height: 1.55; -webkit-box-orient: vertical; -webkit-line-clamp: 2; }
.evidence-archive { margin-top: 18px; border-top: 1px solid #edf1f6; border-bottom: 0; }
.evidence-title { display: flex; flex: 1; align-items: center; justify-content: space-between; gap: 14px; padding-right: 10px; }
.evidence-title b { color: #26364b; }
.evidence-title span { color: #8b99aa; font-size: 11px; }
.evidence-columns { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 12px; padding-bottom: 6px; }
.evidence-columns > div { min-width: 0; padding: 14px; border-radius: 16px; background: #f7f9fc; }
.evidence-columns h3 { margin: 0 0 10px; color: #334155; font-size: 13px; }
.evidence-columns .feedback-evidence-item { padding: 10px 11px; border-radius: 12px; }
.evidence-columns .feedback-evidence-item p { display: -webkit-box; overflow: hidden; font-size: 11px; -webkit-box-orient: vertical; -webkit-line-clamp: 2; }

@media (max-width: 1180px) {
  .diagnosis-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .evidence-columns { grid-template-columns: 1fr; }
}
@media (max-width: 860px) {
  .diagnosis-intro, .diagnosis-grid, .trace-overview, .support-summary { grid-template-columns: 1fr; }
  .trace-heading { align-items: flex-start; flex-direction: column; }
  .evidence-title { align-items: flex-start; flex-direction: column; gap: 2px; }
}

/* Keep the portrait summary visible without pushing learning outcomes below the fold. */
.portrait-view-page {
  gap: 26px;
  padding: 24px 16px 28px;
}

.page-header {
  align-items: center;
  padding: 0 24px;
  box-sizing: border-box;
}

.page-header h1 {
  margin: 3px 0 4px;
  font-size: 30px;
}

.page-header p {
  font-size: 13px;
  line-height: 1.5;
}

.header-actions {
  gap: 8px;
}

.header-actions :deep(.el-button) {
  height: 36px;
  padding: 0 16px;
  border-radius: 11px;
}

.hero-panel {
  grid-template-columns: minmax(0, 1.7fr) minmax(230px, .65fr);
  gap: 12px;
  padding: 17px 20px;
  border-radius: 17px;
}

.hero-main {
  gap: 8px;
}

.hero-main h2 {
  font-size: 22px;
}

.hero-main p {
  display: -webkit-box;
  overflow: hidden;
  font-size: 13px;
  line-height: 1.65;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 3;
}

.hero-tags {
  gap: 6px;
}

.hero-side {
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 8px;
}

.hero-side-card {
  align-content: center;
  gap: 4px;
  padding: 12px 14px;
  border-radius: 13px;
}

.hero-side-card strong {
  font-size: 19px;
}

.hero-side-card small {
  display: -webkit-box;
  overflow: hidden;
  font-size: 11px;
  line-height: 1.4;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 2;
}

.metric-row {
  gap: 9px;
}

.metric-card {
  grid-template-columns: minmax(0, 1fr) auto;
  align-items: center;
  gap: 3px 10px;
  min-height: 72px;
  padding: 11px 14px;
  border-radius: 15px;
}

.metric-card strong {
  grid-column: 2;
  grid-row: 1 / 3;
  font-size: 22px;
}

.metric-card small {
  grid-column: 1;
  font-size: 11px;
  line-height: 1.35;
}

@media (max-width: 1100px) {
  .hero-side { grid-template-columns: 1fr; }
  .metric-row { grid-template-columns: repeat(2, minmax(0, 1fr)); }
}

.page-header > div:first-child {
  display: flex;
  min-width: 0;
  flex-direction: column;
  gap: 6px;
}

.page-header .eyebrow {
  color: #4386d8;
  font-weight: 800;
  letter-spacing: .1em;
  text-transform: uppercase;
}

.page-header h1 {
  margin: 0;
  font-size: 38px;
  line-height: 1.25;
  letter-spacing: -0.04em;
}

.page-header p {
  max-width: 50em;
  margin: 0;
  font-size: 16px;
  line-height: 1.7;
}

</style>
