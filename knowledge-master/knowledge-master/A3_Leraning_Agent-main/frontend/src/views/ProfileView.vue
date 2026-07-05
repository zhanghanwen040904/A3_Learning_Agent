<template>
  <div class="page profile-layout">
    <el-card class="panel session-panel">
      <template #header>
        <div class="session-head">
          <strong>画像对话框</strong>
          <el-button type="primary" size="small" @click="newSession">新建</el-button>
        </div>
      </template>
      <div class="session-list">
        <button
          v-for="item in sessions"
          :key="item.id"
          :class="['session-item', { active: item.id === activeSessionId }]"
          @click="switchSession(item.id)"
        >
          <strong>{{ item.title || `画像对话 ${item.id}` }}</strong>
          <span>{{ item.profile_summary || "空白画像" }}</span>
        </button>
      </div>
      <el-alert
        type="info"
        :closable="false"
        title="切换对话框后，学生画像、学习资源和学习路径会同步切换。"
      />
    </el-card>

    <el-card class="panel chat-panel">
      <template #header>
        <div class="panel-head">
          <div>
            <strong>对话式画像构建</strong>
            <p>通过多轮问答采集专业背景、课程目标、知识短板和资源偏好，自动整理成结构化学习画像。</p>
          </div>
          <el-tag type="success">{{ completedCount }}/{{ prompts.length }} 已采集</el-tag>
        </div>
      </template>

      <div class="messages">
        <div v-for="(item, index) in messages" :key="index" :class="['msg', item.role]">
          <div class="msg-role">{{ item.role === "assistant" ? "画像助手" : "我" }}</div>
          <div>{{ item.content }}</div>
        </div>
      </div>

      <div v-if="currentPrompt" class="prompt-card">
        <div class="prompt-label">{{ currentPrompt.label }}</div>
        <div class="prompt-text">{{ currentPrompt.question }}</div>
      </div>

      <div v-else class="prompt-card followup-card">
        <div class="prompt-label">补充说明</div>
        <div class="prompt-text">你可以继续补充新的学习情况，点击“生成画像”后会写入当前对话框的学生画像。</div>
      </div>

      <el-input
        v-model="draft"
        type="textarea"
        :rows="4"
        resize="none"
        placeholder="输入你的当前回答，按 Ctrl+Enter 发送"
        @keydown.ctrl.enter.prevent="sendMessage"
      />

      <div class="actions">
        <el-button @click="resetCurrentSession">重新开始</el-button>
        <el-button @click="sendMessage">发送回答</el-button>
        <el-button type="primary" :loading="loading" :disabled="!canGenerate" @click="createProfile">
          生成画像
        </el-button>
      </div>

      <el-progress v-if="loading" :percentage="progress" striped striped-flow />
    </el-card>

    <div class="profile-side">
      <el-card class="panel">
        <template #header>当前画像摘要</template>
        <el-empty v-if="!hasProfile" description="当前对话框还是空白画像，生成画像后才会出现资源和路径。" />
        <template v-else>
          <el-alert :title="previewSummary" type="info" :closable="false" show-icon />
          <div class="summary-grid">
            <div class="summary-item">
              <span>专业</span>
              <strong>{{ previewProfile.major }}</strong>
            </div>
            <div class="summary-item">
              <span>目标课程</span>
              <strong>{{ previewProfile.target_course }}</strong>
            </div>
            <div class="summary-item">
              <span>困难场景</span>
              <strong>{{ previewProfile.challenge_scene }}</strong>
            </div>
            <div class="summary-item">
              <span>资源偏好</span>
              <strong>{{ previewProfile.preferred_resource }}</strong>
            </div>
          </div>
        </template>
      </el-card>

      <el-card class="panel">
        <template #header>
          <div class="radar-head">
            <span>六维学生画像</span>
            <small>展示当前画像的信息清晰度</small>
          </div>
        </template>
        <div ref="chartRef" class="radar"></div>
        <el-descriptions :column="1" border>
          <el-descriptions-item v-for="field in radarFields" :key="field.key" :label="field.label">
            {{ previewProfile[field.key] || "待生成" }}
          </el-descriptions-item>
        </el-descriptions>
      </el-card>
    </div>
  </div>
</template>

<script setup>
import { computed, nextTick, onMounted, reactive, ref, watch } from "vue";
import * as echarts from "echarts";
import { ElMessage } from "element-plus";
import { ACTIVE_PROFILE_SESSION_KEY, profileApi, setActiveProfileSessionId } from "../api";

const DEFAULT_VALUE = "";

const prompts = [
  { id: "major", label: "专业背景", question: "你现在的专业或方向是什么？如果这门课和你的专业结合很紧，也可以一起说。" },
  { id: "target_course", label: "目标课程", question: "你这次主要想针对哪门课或哪一章节来学？" },
  { id: "knowledge_level", label: "基础情况", question: "你现在的基础大概在哪个水平？哪些概念已经会，哪些还不稳？" },
  { id: "weak_points", label: "知识短板", question: "你最容易卡住的知识点是什么？可以具体到一个概念、流程、图或题型。" },
  { id: "study_goal", label: "学习目标", question: "你希望在多长时间内达到什么结果？例如应付考试、完成作业、能讲清原理或能做项目。" },
  { id: "study_style", label: "学习方式", question: "你更适合什么学习方式？图解、案例、分层练习、视频、代码实操都可以说。" },
  { id: "study_time_prefer", label: "时间偏好", question: "你一般什么时候学习效率最高？每天大概能投入多久？" },
  { id: "course_progress", label: "课程进度", question: "这门课现在学到哪里了？如果有作业、实验或考试节点，也可以顺带说。" },
  { id: "challenge_scene", label: "困难场景", question: "你最常在哪种场景下觉得难？比如看图、写文档、做题、听课跟不上、做项目拆不动。" },
  { id: "preferred_resource", label: "资源偏好", question: "后面生成学习资源时，你最想优先看到哪几类？例如讲解文档、题库、知识导图、视频脚本、实操案例。" },
];

const radarFields = [
  { key: "knowledge_level", label: "知识基础" },
  { key: "study_style", label: "学习风格" },
  { key: "weak_points", label: "薄弱知识点" },
  { key: "study_goal", label: "学习目标" },
  { key: "study_time_prefer", label: "时间偏好" },
  { key: "course_progress", label: "课程进度" },
];

const loading = ref(false);
const progress = ref(0);
const draft = ref("");
const currentIndex = ref(0);
const chartRef = ref(null);
const messages = ref([]);
const answerMap = reactive({});
const extraNotes = ref([]);
const profile = reactive({});
const sessions = ref([]);
const activeSessionId = ref("");

const currentPrompt = computed(() => prompts[currentIndex.value] || null);
const completedCount = computed(() => prompts.filter((item) => answerMap[item.id]).length);
const canGenerate = computed(() => completedCount.value > 0 || extraNotes.value.length > 0);
const hasProfile = computed(() => prompts.some((item) => Boolean(profile[item.id])) || Boolean(profile.profile_summary));

const previewProfile = computed(() => {
  const merged = {};
  for (const prompt of prompts) {
    merged[prompt.id] = answerMap[prompt.id] || profile[prompt.id] || DEFAULT_VALUE;
  }
  merged.profile_summary = profile.profile_summary || "";
  return merged;
});

const previewSummary = computed(() => {
  const parts = [];
  if (previewProfile.value.major) parts.push(`${previewProfile.value.major}方向学生`);
  if (previewProfile.value.target_course) parts.push(`聚焦${previewProfile.value.target_course}`);
  if (previewProfile.value.weak_points) parts.push(`短板：${previewProfile.value.weak_points}`);
  if (previewProfile.value.study_style) parts.push(`偏好：${previewProfile.value.study_style}`);
  return profile.profile_summary || parts.join("；") || "画像已生成";
});

function initConversation() {
  messages.value = [
    { role: "assistant", content: "我们从专业和课程开始。我会边聊边整理成学生画像，你不需要一次性全部写完。" },
    { role: "assistant", content: prompts[0].question },
  ];
}

function clearLocalState() {
  draft.value = "";
  currentIndex.value = 0;
  extraNotes.value = [];
  Object.keys(answerMap).forEach((key) => delete answerMap[key]);
  Object.keys(profile).forEach((key) => delete profile[key]);
  initConversation();
  drawRadar();
}

function storageKey(id = activeSessionId.value) {
  return `a3_profile_conversation_${id || "none"}`;
}

function conversationSnapshot() {
  return {
    profile_session_id: activeSessionId.value,
    messages: messages.value,
    answer_map: { ...answerMap },
    extra_notes: [...extraNotes.value],
    current_index: currentIndex.value,
  };
}

function applyConversation(snapshot = {}) {
  messages.value = Array.isArray(snapshot.messages) && snapshot.messages.length ? snapshot.messages : [];
  Object.keys(answerMap).forEach((key) => delete answerMap[key]);
  Object.assign(answerMap, snapshot.answer_map || snapshot.answerMap || {});
  extraNotes.value = Array.isArray(snapshot.extra_notes) ? snapshot.extra_notes : [];
  const savedIndex = Number(snapshot.current_index ?? 0);
  currentIndex.value = Number.isFinite(savedIndex) ? Math.min(Math.max(savedIndex, 0), prompts.length) : 0;
  if (!messages.value.length) initConversation();
}

function saveConversationLocal() {
  if (activeSessionId.value) {
    localStorage.setItem(storageKey(), JSON.stringify(conversationSnapshot()));
  }
}

async function saveConversationRemote() {
  if (!activeSessionId.value) return;
  try {
    await profileApi.saveConversation(conversationSnapshot());
  } catch {
    // localStorage is the immediate fallback.
  }
}

function persistConversation() {
  saveConversationLocal();
  saveConversationRemote();
}

async function loadSessions() {
  const res = await profileApi.sessions();
  if (res.code !== 200) {
    ElMessage.error(res.msg || "画像会话读取失败");
    return;
  }
  sessions.value = res.data.sessions || [];
  const id = res.data.active_session_id || sessions.value[0]?.id;
  if (id) {
    activeSessionId.value = Number(id);
    setActiveProfileSessionId(id);
  }
}

async function loadConversation() {
  const localRaw = activeSessionId.value ? localStorage.getItem(storageKey()) : "";
  if (localRaw) {
    try {
      applyConversation(JSON.parse(localRaw));
    } catch {
      localStorage.removeItem(storageKey());
    }
  } else {
    initConversation();
  }

  const res = await profileApi.getConversation();
  if (res.code === 200 && res.data?.messages?.length) {
    applyConversation(res.data);
    saveConversationLocal();
  }
}

async function loadProfile() {
  const res = await profileApi.get();
  Object.keys(profile).forEach((key) => delete profile[key]);
  if (res.code === 200 && res.data) {
    Object.assign(profile, res.data);
  }
  await nextTick();
  drawRadar();
}

async function switchSession(id) {
  if (!id || id === activeSessionId.value) return;
  await profileApi.activateSession(id);
  activeSessionId.value = Number(id);
  setActiveProfileSessionId(id);
  await loadConversation();
  await loadProfile();
  ElMessage.success("已切换画像对话框");
}

async function newSession() {
  const res = await profileApi.createSession();
  if (res.code !== 200) {
    ElMessage.error(res.msg || "新建画像对话失败");
    return;
  }
  activeSessionId.value = Number(res.data.id);
  setActiveProfileSessionId(res.data.id);
  await loadSessions();
  clearLocalState();
  saveConversationLocal();
  ElMessage.success("已新建空白画像对话");
}

function normalizeText(text) {
  return String(text || "").trim();
}

function sendMessage() {
  const text = normalizeText(draft.value);
  if (!text) {
    ElMessage.warning("请输入当前回答");
    return;
  }

  messages.value.push({ role: "user", content: text });
  if (currentPrompt.value) {
    answerMap[currentPrompt.value.id] = text;
    currentIndex.value += 1;
    if (currentIndex.value < prompts.length) {
      messages.value.push({ role: "assistant", content: prompts[currentIndex.value].question });
    } else {
      messages.value.push({ role: "assistant", content: "基础画像信息已经采集完成。你可以继续补充，也可以点击生成画像。" });
    }
  } else {
    extraNotes.value.push(text);
    messages.value.push({ role: "assistant", content: "这条补充我记下了，生成画像时会一起纳入。" });
  }
  draft.value = "";
  persistConversation();
}

async function resetCurrentSession() {
  if (!activeSessionId.value) return;
  await profileApi.resetSession(activeSessionId.value);
  localStorage.removeItem(storageKey());
  clearLocalState();
  saveConversationLocal();
  await loadSessions();
  ElMessage.success("当前画像已清空，学习资源和学习路径也已清空");
}

function buildDialogue() {
  const baseLines = prompts.filter((item) => answerMap[item.id]).map((item) => `${item.label}：${answerMap[item.id]}`);
  const noteLines = extraNotes.value.map((item, index) => `补充说明${index + 1}：${item}`);
  return [...baseLines, ...noteLines].join("\n");
}

function scoreByContent(value) {
  const text = String(value || "").trim();
  if (!text) return 0;
  return Math.max(25, Math.min(96, Math.round(28 + text.length * 1.4)));
}

function radarScores() {
  return radarFields.map((item) => scoreByContent(previewProfile.value[item.key]));
}

function drawRadar() {
  if (!chartRef.value) return;
  const chart = echarts.init(chartRef.value);
  chart.setOption({
    tooltip: {},
    radar: {
      indicator: radarFields.map((item) => ({ name: item.label, max: 100 })),
      radius: "62%",
    },
    series: [
      {
        type: "radar",
        data: [
          {
            value: radarScores(),
            name: "画像清晰度",
            areaStyle: { color: "rgba(59, 130, 246, 0.18)" },
            lineStyle: { color: "#3b82f6" },
          },
        ],
      },
    ],
  });
}

async function createProfile() {
  const dialogue = buildDialogue();
  if (!dialogue) {
    ElMessage.warning("请先完成至少一轮对话");
    return;
  }
  loading.value = true;
  progress.value = 15;
  const timer = setInterval(() => {
    progress.value = Math.min(progress.value + 10, 92);
  }, 450);
  try {
    const res = await profileApi.create({ dialogue, conversation: conversationSnapshot() });
    if (res.code !== 200) {
      ElMessage.error(res.msg || "画像生成失败");
      return;
    }
    Object.keys(profile).forEach((key) => delete profile[key]);
    Object.assign(profile, res.data);
    messages.value.push({ role: "assistant", content: `画像已生成：${res.data.profile_summary || "已整理成结构化学生画像。"}` });
    persistConversation();
    await loadSessions();
    await nextTick();
    drawRadar();
    ElMessage.success("画像生成成功，资源和路径将基于当前画像重新生成");
  } finally {
    clearInterval(timer);
    progress.value = 100;
    loading.value = false;
  }
}

watch(previewProfile, async () => {
  await nextTick();
  drawRadar();
}, { deep: true });

onMounted(async () => {
  const saved = localStorage.getItem(ACTIVE_PROFILE_SESSION_KEY);
  if (saved) activeSessionId.value = Number(saved);
  await loadSessions();
  await loadConversation();
  await loadProfile();
});
</script>

<style scoped>
.profile-layout {
  display: grid;
  grid-template-columns: 260px minmax(0, 1.1fr) minmax(340px, 0.8fr);
  gap: 20px;
}
.session-head,
.panel-head,
.radar-head,
.actions {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}
.session-list {
  display: grid;
  gap: 10px;
  margin-bottom: 14px;
}
.session-item {
  display: grid;
  gap: 6px;
  width: 100%;
  padding: 12px;
  text-align: left;
  border: 1px solid #dbeafe;
  border-radius: 8px;
  background: #fff;
  color: #0f172a;
  cursor: pointer;
}
.session-item span {
  color: #64748b;
  font-size: 12px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.session-item.active {
  border-color: #3b82f6;
  background: #eff6ff;
  box-shadow: 0 8px 18px rgba(59, 130, 246, 0.12);
}
.profile-side,
.chat-panel :deep(.el-card__body) {
  display: grid;
  gap: 16px;
}
.panel-head p {
  margin: 6px 0 0;
  color: #64748b;
  font-weight: 400;
}
.messages {
  height: 390px;
  overflow: auto;
  padding: 18px;
  border-radius: 18px;
  background: linear-gradient(180deg, #f8fafc 0%, #eff6ff 100%);
  border: 1px solid rgba(148, 163, 184, 0.2);
}
.msg {
  max-width: 88%;
  margin-bottom: 12px;
  padding: 12px 14px;
  border-radius: 16px;
  line-height: 1.7;
  box-shadow: 0 10px 24px rgba(15, 23, 42, 0.05);
}
.msg-role {
  margin-bottom: 6px;
  font-size: 12px;
  color: #64748b;
}
.msg.assistant {
  background: #ffffff;
  border-top-left-radius: 6px;
}
.msg.user {
  margin-left: auto;
  background: #dbeafe;
  border-top-right-radius: 6px;
}
.prompt-card {
  padding: 16px;
  border-radius: 12px;
  background: #f8fafc;
  border: 1px dashed #93c5fd;
}
.followup-card {
  background: #f0f9ff;
}
.prompt-label {
  margin-bottom: 8px;
  color: #0369a1;
  font-size: 13px;
  font-weight: 700;
}
.summary-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
  margin-top: 16px;
}
.summary-item {
  display: grid;
  gap: 6px;
  padding: 12px;
  border-radius: 8px;
  background: #f8fafc;
}
.summary-item span,
.radar-head small {
  color: #64748b;
  font-size: 12px;
}
.radar {
  height: 300px;
}
@media (max-width: 1200px) {
  .profile-layout {
    grid-template-columns: 1fr;
  }
}
</style>
