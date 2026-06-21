<template>
  <div class="page profile-grid">
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
          <span>{{ item.profile_summary || item.target_course || '空白画像' }}</span>
        </button>
      </div>
      <el-alert
        type="info"
        :closable="false"
        title="新建或切换画像对话框后，学生画像、学习资源和学习路径会同步切换。"
      />
    </el-card>

    <el-card class="panel chat-panel">
      <template #header>
        <div class="panel-head">
          <div>
            <strong>对话式画像构建</strong>
            <p>支持自由自然语言输入，由大模型实时抽取画像维度、识别缺失信息并动态追问。</p>
          </div>
          <el-tag :type="modelEnabled ? 'success' : 'warning'">{{ modelEnabled ? '大模型画像中' : 'MOCK兜底模式' }}</el-tag>
        </div>
      </template>

      <div ref="messageBoxRef" class="messages">
        <div v-for="(item, index) in messages" :key="index" :class="['msg', item.role]">
          <div class="msg-role">
            <span>{{ item.role === "assistant" ? "画像助手" : "我" }}</span>
            <small v-if="item.time">{{ item.time }}</small>
          </div>
          <div class="msg-content">{{ item.content }}</div>
        </div>
        <div v-if="sending" class="msg assistant typing-msg">
          <div class="msg-role">画像助手</div>
          <div class="typing-dots" aria-label="处理中">
            <span></span>
            <span></span>
            <span></span>
            <em>{{ loading ? "正在调用画像智能体生成结构化画像" : "正在整理你的回答" }}</em>
          </div>
        </div>
      </div>

      <div class="prompt-card" :class="{ 'followup-card': isComplete }">
        <div class="prompt-label">{{ isComplete ? '画像基本完整' : '大模型动态追问' }}</div>
        <div class="prompt-text">{{ nextQuestion }}</div>
        <div class="prompt-meta">
          <el-tag size="small" type="info">置信度 {{ Math.round(confidence * 100) }}%</el-tag>
          <el-tag v-for="field in missingFields" :key="field" size="small" type="warning" plain>{{ fieldLabel(field) }}</el-tag>
        </div>
      </div>

      <el-input
        ref="inputRef"
        v-model="draft"
        type="textarea"
        :autosize="{ minRows: 3, maxRows: 8 }"
        resize="none"
        :disabled="sending"
        placeholder="输入你的当前回答，按 Enter 发送，Shift+Enter 换行"
        @keydown.enter.exact.prevent="sendMessage"
        @keydown.ctrl.enter.prevent="sendMessage"
      />

      <div class="actions">
        <div class="action-tip">
          <el-icon v-if="sending" class="is-loading"><Loading /></el-icon>
          <span>{{ statusText }}</span>
        </div>
        <div class="action-buttons">
          <el-button :disabled="sending" @click="resetConversation">重新开始</el-button>
          <el-button :loading="sending && !loading" :disabled="!draft.trim() || loading" @click="sendMessage">发送回答</el-button>
          <el-button type="primary" :loading="loading" :disabled="!canGenerate || sending" @click="createProfile">
            生成画像
          </el-button>
        </div>
      </div>

      <el-progress v-if="loading" :percentage="progress" striped striped-flow />
    </el-card>

    <div class="profile-side">
      <el-card class="panel">
        <template #header>画像摘要与关键档案</template>
        <el-alert
          :title="previewSummary"
          type="info"
          :closable="false"
          show-icon
        />
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
      </el-card>

      <el-card class="panel">
        <template #header>
          <div class="radar-head">
            <span>六维画像雷达图</span>
            <small>当前展示的是各维度信息清晰度，不是考试分数</small>
          </div>
        </template>
        <div ref="chartRef" class="radar"></div>
        <el-descriptions :column="1" border>
          <el-descriptions-item v-for="field in radarFields" :key="field.key" :label="field.label">
            {{ previewProfile[field.key] }}
          </el-descriptions-item>
        </el-descriptions>
      </el-card>
    </div>
  </div>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref, watch } from "vue";
import { Loading } from "@element-plus/icons-vue";
import * as echarts from "echarts";
import { ElMessage, ElMessageBox } from "element-plus";
import { ACTIVE_PROFILE_SESSION_KEY, profileApi, setActiveProfileSessionId } from "../api";

const DEFAULT_VALUE = "待进一步观察";
const STORAGE_PREFIX = "a3_learning_agent_profile_conversation_v2";

const prompts = [
  { id: "major", label: "专业背景", question: "你现在的专业或方向是什么？如果这门课和你的专业结合很紧，也可以一起说。" },
  { id: "target_course", label: "目标课程", question: "你这次主要想针对哪门课或哪一章节来学？" },
  { id: "knowledge_level", label: "基础情况", question: "你现在的基础大概在哪个水平？哪些概念已经会，哪些还不稳？" },
  { id: "weak_points", label: "知识短板", question: "你最容易卡住的知识点是什么？可以具体到一个概念、公式或题型。" },
  { id: "study_goal", label: "学习目标", question: "你希望在多长时间内达到什么结果？例如应付考试、完成作业、能讲清楚原理或能写实验。" },
  { id: "study_style", label: "学习方式", question: "你更适合什么学习方式？图解、案例、分层练习、视频、代码实操都可以说。" },
  { id: "study_time_prefer", label: "时间偏好", question: "你一般什么时候学习效率最高？每天大概能投入多久？" },
  { id: "course_progress", label: "课程进度", question: "你这门课现在学到哪里了？如果有作业、实验或考试节点，也可以顺带说。" },
  { id: "challenge_scene", label: "困难场景", question: "你最常在哪种场景下觉得难？比如看公式、看图、写代码、做题、听课跟不上。" },
  { id: "preferred_resource", label: "资源偏好", question: "后面生成学习资源时，你最想优先看到哪几类？" },
];

const radarFields = [
  { key: "knowledge_level", label: "知识基础" },
  { key: "study_style", label: "学习风格" },
  { key: "weak_points", label: "薄弱点" },
  { key: "study_goal", label: "学习目标" },
  { key: "study_time_prefer", label: "时间偏好" },
  { key: "course_progress", label: "课程进度" },
];

const loading = ref(false);
const sending = ref(false);
const progress = ref(0);
const draft = ref("");
const chartRef = ref(null);
const messageBoxRef = ref(null);
const inputRef = ref(null);
const messages = ref([]);
const profile = reactive({});
const missingFields = ref([]);
const nextQuestion = ref("你可以用一段话自由描述你的专业、课程目标、基础、薄弱点和偏好的学习方式。我会自动提取画像，并只追问缺失或模糊的信息。");
const confidence = ref(0);
const isComplete = ref(false);
const modelEnabled = ref(false);
const sessions = ref([]);
const activeSessionId = ref("");
let chartInstance = null;
let saveTimer = null;

const completedCount = computed(() => prompts.filter((item) => previewProfile.value[item.id] && previewProfile.value[item.id] !== DEFAULT_VALUE).length);
const canGenerate = computed(() => messages.value.some((item) => item.role === "user") || completedCount.value >= 3);
const statusText = computed(() => {
  if (loading.value) return "AI 正在整理画像，请稍候...";
  if (sending.value) return "大模型正在理解上下文并生成追问...";
  if (isComplete.value) return "画像已基本完整，可继续补充或生成画像";
  return `大模型已识别 ${completedCount.value}/${prompts.length} 个画像维度`;
});

const previewProfile = computed(() => {
  const merged = {};

  for (const prompt of prompts) {
    const key = prompt.id;
    merged[key] = profile[key] || DEFAULT_VALUE;
  }

  merged.profile_summary = profile.profile_summary || DEFAULT_VALUE;
  return merged;
});

const previewSummary = computed(() => {
  const major = previewProfile.value.major;
  const course = previewProfile.value.target_course;
  const weak = previewProfile.value.weak_points;
  const style = previewProfile.value.study_style;

  const parts = [];
  if (major !== DEFAULT_VALUE) parts.push(`${major}方向学生`);
  if (course !== DEFAULT_VALUE) parts.push(`当前聚焦${course}`);
  if (weak !== DEFAULT_VALUE) parts.push(`主要短板是${weak}`);
  if (style !== DEFAULT_VALUE) parts.push(`偏好${style}式学习`);

  return parts.join("，") || "完成几轮回答后，这里会自动生成一句话画像摘要。";
});

function timeLabel() {
  return new Date().toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit" });
}

function assistantMessage(content) {
  return { role: "assistant", content, time: timeLabel() };
}

function userMessage(content) {
  return { role: "user", content, time: timeLabel() };
}

function initConversation() {
  messages.value = [
    assistantMessage("你好，我是大模型画像助手。你可以直接用一段自然语言描述学习情况，我会自动抽取专业、目标、基础、薄弱点、偏好等画像维度，并根据缺失信息动态追问。"),
    assistantMessage(nextQuestion.value),
  ];
}

function fieldLabel(key) {
  return prompts.find((item) => item.id === key)?.label || key;
}

function normalizeText(text) {
  return String(text || "").trim();
}

function scrollToBottom() {
  nextTick(() => {
    const box = messageBoxRef.value;
    if (box) box.scrollTop = box.scrollHeight;
  });
}

function focusInput() {
  nextTick(() => {
    inputRef.value?.focus?.();
  });
}

function storageKey(id = activeSessionId.value) {
  return `${STORAGE_PREFIX}_${id || "none"}`;
}

function snapshotState() {
  return {
    profile_session_id: activeSessionId.value,
    messages: messages.value,
    draft: draft.value,
    profile: { ...profile },
    missingFields: missingFields.value,
    nextQuestion: nextQuestion.value,
    confidence: confidence.value,
    isComplete: isComplete.value,
    modelEnabled: modelEnabled.value,
    savedAt: Date.now(),
  };
}

function persistState() {
  try {
    localStorage.setItem(storageKey(), JSON.stringify(snapshotState()));
  } catch (error) {
    console.warn("画像会话本地保存失败", error);
  }
}

function schedulePersist() {
  window.clearTimeout(saveTimer);
  saveTimer = window.setTimeout(persistState, 120);
}

function restoreState() {
  try {
    const raw = localStorage.getItem(storageKey());
    if (!raw) return false;
    const saved = JSON.parse(raw);
    if (!Array.isArray(saved.messages) || saved.messages.length === 0) return false;

    messages.value = saved.messages;
    draft.value = saved.draft || "";
    Object.assign(profile, saved.profile || {});
    missingFields.value = Array.isArray(saved.missingFields) ? saved.missingFields : [];
    nextQuestion.value = saved.nextQuestion || nextQuestion.value;
    confidence.value = Number(saved.confidence || 0);
    isComplete.value = Boolean(saved.isComplete);
    modelEnabled.value = Boolean(saved.modelEnabled);
    return true;
  } catch (error) {
    console.warn("画像会话恢复失败", error);
    localStorage.removeItem(storageKey());
    return false;
  }
}

function applyState(saved = {}) {
  messages.value = Array.isArray(saved.messages) && saved.messages.length ? saved.messages : [];
  draft.value = saved.draft || "";
  Object.keys(profile).forEach((key) => delete profile[key]);
  Object.assign(profile, saved.profile || {});
  missingFields.value = Array.isArray(saved.missingFields) ? saved.missingFields : [];
  nextQuestion.value = saved.nextQuestion || "你可以用一段话自由描述你的专业、课程目标、基础、薄弱点和偏好的学习方式。我会自动提取画像，并只追问缺失或模糊的信息。";
  confidence.value = Number(saved.confidence || 0);
  isComplete.value = Boolean(saved.isComplete);
  modelEnabled.value = Boolean(saved.modelEnabled);
  if (!messages.value.length) initConversation();
}

async function saveConversationRemote() {
  if (!activeSessionId.value) return;
  try {
    await profileApi.saveConversation({ ...snapshotState(), answer_map: {}, extra_notes: [], current_index: 0 });
  } catch {
    // 本地存储作为即时兜底。
  }
}

async function loadConversationRemote() {
  try {
    const res = await profileApi.getConversation();
    if (res.code === 200 && Array.isArray(res.data?.messages) && res.data.messages.length) {
      messages.value = res.data.messages;
      persistState();
    }
  } catch {
    // 本地会话仍可继续使用。
  }
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

async function switchSession(id) {
  if (!id || id === activeSessionId.value || sending.value || loading.value) return;
  await profileApi.activateSession(id);
  activeSessionId.value = Number(id);
  setActiveProfileSessionId(id);
  Object.keys(profile).forEach((key) => delete profile[key]);
  if (!restoreState()) initConversation();
  await loadConversationRemote();
  await loadProfile();
  scrollToBottom();
  ElMessage.success("已切换画像对话框");
}

async function newSession() {
  if (sending.value || loading.value) return;
  const res = await profileApi.createSession();
  if (res.code !== 200) {
    ElMessage.error(res.msg || "新建画像对话失败");
    return;
  }
  activeSessionId.value = Number(res.data.id);
  setActiveProfileSessionId(res.data.id);
  await loadSessions();
  clearCurrentSessionState();
  persistState();
  ElMessage.success("已新建空白画像对话");
}

function clearCurrentSessionState() {
  draft.value = "";
  missingFields.value = [];
  confidence.value = 0;
  isComplete.value = false;
  modelEnabled.value = false;
  Object.keys(profile).forEach((key) => delete profile[key]);
  nextQuestion.value = "你可以用一段话自由描述你的专业、课程目标、基础、薄弱点和偏好的学习方式。我会自动提取画像，并只追问缺失或模糊的信息。";
  initConversation();
}

async function resetRemoteSession() {
  if (!activeSessionId.value) return;
  await profileApi.resetSession(activeSessionId.value);
  localStorage.removeItem(storageKey());
}

async function sendMessage() {
  const text = normalizeText(draft.value);
  if (!text) {
    ElMessage.warning("请输入当前回答");
    return;
  }
  if (sending.value || loading.value) return;

  sending.value = true;
  messages.value.push(userMessage(text));
  draft.value = "";
  scrollToBottom();

  try {
    const payloadMessages = messages.value.map((item) => ({ role: item.role, content: item.content }));
    const res = await profileApi.chat({ messages: payloadMessages, current_profile: { ...profile } });
    if (res.code !== 200) {
      messages.value.push(assistantMessage(`画像分析失败：${res.msg || "请稍后重试"}`));
      ElMessage.error(res.msg || "画像分析失败");
      return;
    }

    Object.assign(profile, res.data.profile || {});
    missingFields.value = res.data.missing_fields || [];
    nextQuestion.value = res.data.next_question || "画像已经基本完整。你可以继续补充，或点击“生成画像”保存。";
    confidence.value = Number(res.data.confidence || 0);
    isComplete.value = Boolean(res.data.is_complete);
    modelEnabled.value = Boolean(res.data.model_enabled);
    messages.value.push(assistantMessage(nextQuestion.value));
    persistState();
    saveConversationRemote();
  } catch (error) {
    messages.value.push(assistantMessage("大模型画像对话接口异常，请确认后端已启动，并检查讯飞配置或 MOCK_AI 设置。"));
    ElMessage.error(error?.message || "发送失败，请重试");
  } finally {
    sending.value = false;
    scrollToBottom();
    focusInput();
  }
}

async function resetConversation() {
  try {
    await ElMessageBox.confirm("重新开始会清空当前画像对话框的对话、画像、学习资源和学习路径。确定继续吗？", "确认重新开始", {
      confirmButtonText: "重新开始",
      cancelButtonText: "取消",
      type: "warning",
    });
  } catch {
    return;
  }

  await resetRemoteSession();
  clearCurrentSessionState();
  persistState();
  scrollToBottom();
  focusInput();
}

function buildDialogue() {
  return messages.value
    .filter((item) => item.role === "user")
    .map((item, index) => `学生第${index + 1}轮回答：${item.content}`)
    .join("\n");
}

function keywordCount(text, keywords) {
  return keywords.reduce((count, keyword) => count + (text.includes(keyword) ? 1 : 0), 0);
}

function scoreByContent(key, value) {
  const text = String(value || "").trim();
  if (!text || text === DEFAULT_VALUE) return 18;

  let score = Math.min(72, 28 + text.length * 1.2);

  if (key === "knowledge_level") {
    if (/刚入门|零基础|不会/.test(text)) score += 4;
    if (/一般|还可以|基础较弱/.test(text)) score += 12;
    if (/扎实|较好|比较熟悉/.test(text)) score += 20;
  }

  if (key === "study_style") {
    score += keywordCount(text, ["图", "案例", "练习", "视频", "代码", "讲解"]) * 4;
  }

  if (key === "weak_points") {
    score += keywordCount(text, ["监督学习", "无监督学习", "反向传播", "公式", "推导", "做题", "代码"]) * 3;
  }

  if (key === "study_goal") {
    score += keywordCount(text, ["周", "天", "考试", "作业", "实验", "掌握", "完成"]) * 4;
  }

  if (key === "study_time_prefer") {
    score += keywordCount(text, ["晚上", "白天", "周末", "分钟", "小时"]) * 5;
  }

  if (key === "course_progress") {
    score += keywordCount(text, ["已学", "刚学完", "正在", "准备", "考试", "实验", "复盘"]) * 4;
  }

  return Math.max(18, Math.min(96, Math.round(score)));
}

function radarScores() {
  return radarFields.map((item) => scoreByContent(item.key, previewProfile.value[item.key]));
}

function drawRadar() {
  if (!chartRef.value) return;
  if (!chartInstance) chartInstance = echarts.init(chartRef.value);
  chartInstance.setOption({
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
            name: "画像信息清晰度",
            areaStyle: { color: "rgba(14, 116, 144, 0.22)" },
            lineStyle: { color: "#0f766e" },
          },
        ],
      },
    ],
  });
}

async function loadProfile() {
  try {
    const res = await profileApi.get();
    Object.keys(profile).forEach((key) => delete profile[key]);
    if (res.code === 200 && res.data && Object.keys(res.data).length > 0) {
      Object.assign(profile, res.data);
      persistState();
      await nextTick();
      drawRadar();
    } else if (res.code !== 200) {
      ElMessage.warning(res.msg || "历史画像读取失败，可继续本地对话采集");
    }
  } catch (error) {
    ElMessage.warning(error?.message || "历史画像读取异常，可继续本地对话采集");
  }
}

async function createProfile() {
  const dialogue = buildDialogue();
  if (!dialogue) {
    ElMessage.warning("请先完成至少一轮对话");
    return;
  }
  if (loading.value || sending.value) return;

  loading.value = true;
  sending.value = true;
  progress.value = 15;
  scrollToBottom();
  const timer = window.setInterval(() => {
    progress.value = Math.min(progress.value + 10, 92);
  }, 450);

  try {
    let data = { ...profile };
    if (completedCount.value < 3) {
      const res = await profileApi.create({ dialogue, profile: data, conversation: snapshotState() });
      if (res.code !== 200) {
        messages.value.push(assistantMessage(`画像生成失败：${res.msg || "服务暂不可用，请稍后重试。"}`));
        ElMessage.error(res.msg || "画像生成失败");
        return;
      }
      data = res.data || {};
    } else {
      const res = await profileApi.create({ dialogue, profile: data, conversation: snapshotState() });
      if (res.code === 200 && res.data) data = { ...data, ...res.data };
    }
    Object.assign(profile, data);
    messages.value.push(assistantMessage(`画像已生成：${data.profile_summary || "我已经把你的多轮自然语言对话整理成结构化画像，并写入数据库。"}`));
    persistState();
    saveConversationRemote();
    await loadSessions();
    drawRadar();
    ElMessage.success("画像生成成功");
  } catch (error) {
    messages.value.push(assistantMessage("画像生成时出现网络或服务异常，请确认后端已启动后再试。"));
    ElMessage.error(error?.message || "画像生成异常");
  } finally {
    window.clearInterval(timer);
    progress.value = 100;
    loading.value = false;
    sending.value = false;
    scrollToBottom();
    focusInput();
  }
}

watch(previewProfile, async () => {
  await nextTick();
  drawRadar();
}, { deep: true });

watch([messages, draft, missingFields, confidence, isComplete, modelEnabled], () => {
  schedulePersist();
}, { deep: true });

watch(profile, () => {
  schedulePersist();
}, { deep: true });

onMounted(async () => {
  const saved = localStorage.getItem(ACTIVE_PROFILE_SESSION_KEY);
  if (saved) activeSessionId.value = Number(saved);
  await loadSessions();
  if (!restoreState()) initConversation();
  await loadConversationRemote();
  await loadProfile();
  await nextTick();
  drawRadar();
  scrollToBottom();
  focusInput();
  window.addEventListener("resize", drawRadar);
});

onBeforeUnmount(() => {
  persistState();
  window.clearTimeout(saveTimer);
  window.removeEventListener("resize", drawRadar);
  chartInstance?.dispose?.();
  chartInstance = null;
});
</script>

<style scoped>
.profile-grid {
  display: grid;
  grid-template-columns: 260px minmax(0, 1.1fr) minmax(340px, 0.85fr);
  gap: 24px;
}

.session-head {
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
  border-radius: 12px;
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
  border-color: #0f766e;
  background: #ecfdf5;
  box-shadow: 0 8px 18px rgba(15, 118, 110, 0.12);
}

.profile-side {
  display: grid;
  gap: 24px;
}

.panel-head,
.radar-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
}

.panel-head p {
  margin: 6px 0 0;
  color: #64748b;
  font-weight: 400;
}

.radar-head small {
  color: #64748b;
  font-size: 12px;
  font-weight: 400;
}

.chat-panel :deep(.el-card__body) {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.messages {
  height: 390px;
  overflow: auto;
  padding: 18px;
  scroll-behavior: smooth;
  border-radius: 18px;
  background:
    radial-gradient(circle at top right, rgba(186, 230, 253, 0.8), transparent 34%),
    linear-gradient(180deg, #f8fafc 0%, #eff6ff 100%);
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
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  margin-bottom: 6px;
  font-size: 12px;
  color: #64748b;
}

.msg-role small {
  color: #94a3b8;
  font-size: 11px;
}

.msg-content {
  white-space: pre-wrap;
  word-break: break-word;
}

.msg.assistant {
  background: #ffffff;
  border-top-left-radius: 6px;
}

.msg.user {
  margin-left: auto;
  color: #064e3b;
  background: linear-gradient(135deg, #dcfce7, #bbf7d0);
  border-top-right-radius: 6px;
}

.typing-msg {
  width: fit-content;
  min-width: 260px;
}

.typing-dots {
  display: flex;
  align-items: center;
  gap: 7px;
  color: #475569;
}

.typing-dots span {
  width: 7px;
  height: 7px;
  border-radius: 999px;
  background: #38bdf8;
  animation: typingBlink 1.2s infinite ease-in-out;
}

.typing-dots span:nth-child(2) {
  animation-delay: 0.15s;
}

.typing-dots span:nth-child(3) {
  animation-delay: 0.3s;
}

.typing-dots em {
  margin-left: 4px;
  font-style: normal;
  font-size: 13px;
}

@keyframes typingBlink {
  0%, 80%, 100% { opacity: 0.25; transform: translateY(0); }
  40% { opacity: 1; transform: translateY(-3px); }
}

.prompt-card {
  padding: 16px;
  border-radius: 16px;
  background: #f8fafc;
  border: 1px dashed #94a3b8;
}

.followup-card {
  background: #f0fdf4;
  border-color: #86efac;
}

.prompt-label {
  font-size: 12px;
  color: #0f766e;
  margin-bottom: 6px;
}

.prompt-text {
  color: #0f172a;
  line-height: 1.7;
}

.prompt-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 12px;
}

.actions {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.action-tip {
  display: flex;
  align-items: center;
  gap: 6px;
  color: #64748b;
  font-size: 13px;
}

.action-buttons {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
}

.summary-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
  margin-top: 16px;
}

.summary-item {
  padding: 14px;
  border-radius: 14px;
  background: #f8fafc;
  border: 1px solid rgba(148, 163, 184, 0.18);
}

.summary-item span {
  display: block;
  margin-bottom: 6px;
  font-size: 12px;
  color: #64748b;
}

.summary-item strong {
  color: #0f172a;
  line-height: 1.6;
}

.radar {
  height: 320px;
}

@media (max-width: 1000px) {
  .profile-grid {
    grid-template-columns: 1fr;
  }

  .summary-grid {
    grid-template-columns: 1fr;
  }

  .actions,
  .action-buttons {
    flex-wrap: wrap;
  }
}
</style>
