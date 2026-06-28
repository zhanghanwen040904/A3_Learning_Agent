<template>
  <div class="portrait-page">
    <div class="chat-home" v-if="showHome">
      <div class="home-center">
        <h1>Ready when you are.</h1>

        <div class="home-composer">
          <el-input
            ref="inputRef"
            v-model="draft"
            type="textarea"
            :autosize="{ minRows: 1, maxRows: 6 }"
            resize="none"
            :disabled="sending"
            placeholder="说说你的专业、课程、基础、薄弱点和目标，我会逐步帮你建立综合画像"
            @keydown.enter.exact.prevent="sendMessage"
            @keydown.ctrl.enter.prevent="sendMessage"
          />

          <div class="home-actions">
            <el-button text @click="createProfile" :disabled="!canGenerate || sending" :loading="loading">生成画像</el-button>
            <el-button type="primary" circle @click="sendMessage" :disabled="!draft.trim() || sending || loading">发送</el-button>
          </div>
        </div>
      </div>
    </div>

    <div class="chat-stage" v-else>
      <div class="stage-header">
        <div>
          <h1>{{ activeSessionTitle }}</h1>
          <p>通过多轮自然对话持续补全当前会话，并自动汇总为综合学习画像。</p>
        </div>

        <div class="stage-badges">
          <el-tag round>{{ modelEnabled ? "大模型分析中" : "本地辅助模式" }}</el-tag>
          <el-tag round type="info">{{ Math.round(confidence * 100) }}% 完整度</el-tag>
        </div>
      </div>

      <div ref="messageBoxRef" class="message-stream">
        <div
          v-for="(item, index) in messages"
          :key="index"
          :class="['message-row', item.role]"
        >
          <div v-if="item.role === 'assistant'" class="assistant-avatar">AI</div>

          <div :class="['message-bubble', item.role]">
            <div class="message-meta">
              <span>{{ item.role === "assistant" ? "画像助手" : "我" }}</span>
              <small v-if="item.time">{{ item.time }}</small>
            </div>
            <div class="message-content">{{ item.content }}</div>
          </div>
        </div>

        <div v-if="sending" class="message-row assistant">
          <div class="assistant-avatar thinking">AI</div>
          <div class="message-bubble assistant thinking-bubble">
            <div class="thinking-title">Thinking</div>
            <div class="typing-dots">
              <span></span>
              <span></span>
              <span></span>
            </div>
            <p>{{ loading ? "正在汇总并生成综合画像..." : "正在理解你的补充信息并生成下一轮追问..." }}</p>
          </div>
        </div>
      </div>

      <div class="summary-strip">
        <div class="summary-main">
          <span class="summary-label">综合画像</span>
          <strong>{{ previewSummary }}</strong>
        </div>
        <div class="summary-tags">
          <el-tag
            v-for="field in missingFields.slice(0, 4)"
            :key="field"
            size="small"
            round
            type="warning"
            effect="plain"
          >
            {{ fieldLabel(field) }}
          </el-tag>
        </div>
      </div>

      <div class="composer-card">
        <el-input
          ref="inputRef"
          v-model="draft"
          type="textarea"
          :autosize="{ minRows: 2, maxRows: 8 }"
          resize="none"
          :disabled="sending"
          placeholder="继续补充你的学习情况，按 Enter 发送，Shift+Enter 换行"
          @keydown.enter.exact.prevent="sendMessage"
          @keydown.ctrl.enter.prevent="sendMessage"
        />

        <div class="composer-footer">
          <div class="composer-status">
            <el-icon v-if="sending" class="is-loading"><Loading /></el-icon>
            <span>{{ statusText }}</span>
          </div>

          <div class="composer-buttons">
            <el-button :disabled="sending" @click="resetConversation">重置当前会话</el-button>
            <el-button :loading="sending && !loading" :disabled="!draft.trim() || loading" @click="sendMessage">发送</el-button>
            <el-button type="primary" :loading="loading" :disabled="!canGenerate || sending" @click="createProfile">
              生成画像
            </el-button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref, watch } from "vue";
import { Loading } from "@element-plus/icons-vue";
import { ElMessage, ElMessageBox } from "element-plus";
import { ACTIVE_PROFILE_SESSION_KEY, profileApi, setActiveProfileSessionId } from "../api";

const DEFAULT_VALUE = "待进一步观察";
const STORAGE_PREFIX = "a3_learning_agent_profile_conversation_v5";
const WELCOME_MESSAGE = "你好，我是学习画像助手。你可以像和 GPT 对话一样，直接告诉我你的专业、课程、基础、薄弱点、目标和偏好的学习方式；我会在多轮对话中持续提取信息，并把所有会话汇总成你的综合学习画像。";
const LEGACY_WELCOME_MESSAGES = [
  WELCOME_MESSAGE,
  "你好，我是大模型画像助手。你可以直接用一段自然语言描述学习情况，我会自动抽取专业、目标、基础、薄弱点、偏好等画像维度，并根据缺失信息动态追问。",
  "你可以自由描述你的专业、课程目标、基础、薄弱点和偏好的学习方式。我会自动提取画像，并只追问缺失或模糊的信息。",
];

const prompts = [
  { id: "major", label: "专业背景" },
  { id: "target_course", label: "目标课程" },
  { id: "knowledge_level", label: "基础情况" },
  { id: "weak_points", label: "薄弱点" },
  { id: "study_goal", label: "学习目标" },
  { id: "study_style", label: "学习方式" },
  { id: "study_time_prefer", label: "时间偏好" },
  { id: "course_progress", label: "课程进度" },
  { id: "challenge_scene", label: "困难场景" },
  { id: "preferred_resource", label: "资源偏好" },
];

const loading = ref(false);
const sending = ref(false);
const draft = ref("");
const inputRef = ref(null);
const messageBoxRef = ref(null);
const messages = ref([]);
const profile = reactive({});
const aggregateProfile = reactive({});
const missingFields = ref([]);
const nextQuestion = ref("先用一段自然语言告诉我你的学习情况吧，我会根据你说的内容自动追问缺失信息。");
const confidence = ref(0);
const isComplete = ref(false);
const modelEnabled = ref(false);
const sessions = ref([]);
const activeSessionId = ref("");
let saveTimer = null;

const showHome = computed(() => {
  const meaningfulMessages = messages.value.filter((item) => item.role === "user");
  return meaningfulMessages.length === 0 && !draft.value.trim();
});

const completedCount = computed(() => prompts.filter((item) => previewProfile.value[item.id] && previewProfile.value[item.id] !== DEFAULT_VALUE).length);
const canGenerate = computed(() => messages.value.some((item) => item.role === "user") || completedCount.value >= 3);

const statusText = computed(() => {
  if (loading.value) return "正在汇总当前会话并生成综合画像...";
  if (sending.value) return "正在理解上下文并生成下一轮追问...";
  if (isComplete.value) return "当前信息已经比较完整，可以继续补充，也可以直接生成画像。";
  return `已识别 ${completedCount.value}/${prompts.length} 个画像维度`;
});

const previewProfile = computed(() => {
  const merged = {};
  for (const prompt of prompts) {
    merged[prompt.id] = aggregateProfile[prompt.id] || profile[prompt.id] || DEFAULT_VALUE;
  }
  merged.major = aggregateProfile.major || profile.major || DEFAULT_VALUE;
  merged.profile_summary = aggregateProfile.profile_summary || profile.profile_summary || DEFAULT_VALUE;
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
  if (weak !== DEFAULT_VALUE) parts.push(`主要薄弱点是${weak}`);
  if (style !== DEFAULT_VALUE) parts.push(`偏好${style}`);

  return parts.join("；") || "完成几轮对话后，这里会自动生成一句综合学习画像摘要。";
});

const activeSessionTitle = computed(() => {
  const current = sessions.value.find((item) => Number(item.id) === Number(activeSessionId.value));
  return current?.title || "新的学习会话";
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

function normalizeText(text) {
  return String(text || "").trim();
}

function sameMessage(a, b) {
  return a?.role === b?.role && normalizeText(a?.content) === normalizeText(b?.content);
}

function isWelcomeContent(content) {
  const normalized = normalizeText(content);
  return normalized === WELCOME_MESSAGE
    || LEGACY_WELCOME_MESSAGES.includes(normalized)
    || (normalized.includes("画像助手") && normalized.includes("综合学习画像"));
}

function cleanMessages(list = []) {
  const cleaned = [];
  let welcomeInserted = false;

  for (const item of list) {
    if (!item?.role || !normalizeText(item.content)) continue;
    const content = normalizeText(item.content);

    if (item.role === "assistant" && isWelcomeContent(content)) {
      if (!welcomeInserted) {
        cleaned.push({ ...item, content: WELCOME_MESSAGE });
        welcomeInserted = true;
      }
      continue;
    }

    const next = { ...item, content };
    if (!sameMessage(cleaned[cleaned.length - 1], next)) cleaned.push(next);
  }

  if (!cleaned.length) return [assistantMessage(WELCOME_MESSAGE)];
  if (cleaned[0].role !== "assistant" || !isWelcomeContent(cleaned[0].content)) {
    cleaned.unshift(assistantMessage(WELCOME_MESSAGE));
  }
  return cleaned;
}

function initConversation() {
  messages.value = [assistantMessage(WELCOME_MESSAGE)];
}

function pushAssistant(content) {
  const msg = assistantMessage(normalizeText(content));
  if (!sameMessage(messages.value[messages.value.length - 1], msg)) {
    messages.value.push(msg);
  }
}

function fieldLabel(key) {
  return prompts.find((item) => item.id === key)?.label || key;
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

    const restoredMessages = cleanMessages(saved.messages);
    messages.value = restoredMessages;
    draft.value = saved.draft || "";
    Object.keys(profile).forEach((key) => delete profile[key]);
    Object.assign(profile, saved.profile || {});
    missingFields.value = Array.isArray(saved.missingFields) ? saved.missingFields : [];
    nextQuestion.value = saved.nextQuestion || nextQuestion.value;
    confidence.value = Number(saved.confidence || 0);
    isComplete.value = Boolean(saved.isComplete);
    modelEnabled.value = Boolean(saved.modelEnabled);
    return true;
  } catch (error) {
    localStorage.removeItem(storageKey());
    return false;
  }
}

function clearCurrentSessionState() {
  draft.value = "";
  missingFields.value = [];
  confidence.value = 0;
  isComplete.value = false;
  modelEnabled.value = false;
  Object.keys(profile).forEach((key) => delete profile[key]);
  nextQuestion.value = "先用一段自然语言告诉我你的学习情况吧，我会根据你说的内容自动追问缺失信息。";
  initConversation();
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

async function saveConversationRemote() {
  if (!activeSessionId.value) return;
  try {
    await profileApi.saveConversation({ ...snapshotState(), answer_map: {}, extra_notes: [], current_index: 0 });
  } catch {
    // 本地兜底
  }
}

async function loadConversationRemote() {
  try {
    const res = await profileApi.getConversation();
    if (res.code === 200 && Array.isArray(res.data?.messages) && res.data.messages.length) {
      messages.value = cleanMessages(res.data.messages);
      persistState();
    }
  } catch {
    // ignore
  }
}

async function loadSessions() {
  const res = await profileApi.sessions();
  if (res.code !== 200) return;
  sessions.value = res.data.sessions || [];
  const id = res.data.active_session_id || sessions.value[0]?.id;
  if (id) {
    activeSessionId.value = Number(id);
    setActiveProfileSessionId(id);
  }
}

async function loadAggregateProfile() {
  try {
    const res = await profileApi.getAggregate();
    Object.keys(aggregateProfile).forEach((key) => delete aggregateProfile[key]);
    if (res.code === 200 && res.data && Object.keys(res.data).length > 0) {
      Object.assign(aggregateProfile, res.data);
      persistState();
    }
  } catch {
    // ignore
  }
}

async function switchSession(id) {
  if (!id || id === activeSessionId.value || sending.value || loading.value) return;
  const res = await profileApi.activateSession(id);
  if (res.code !== 200) return;
  activeSessionId.value = Number(id);
  setActiveProfileSessionId(id);
  Object.keys(profile).forEach((key) => delete profile[key]);
  if (!restoreState()) initConversation();
  await loadConversationRemote();
  await loadAggregateProfile();
  scrollToBottom();
}

async function reloadFromActiveSession() {
  activeSessionId.value = Number(localStorage.getItem(ACTIVE_PROFILE_SESSION_KEY) || activeSessionId.value || "");
  Object.keys(profile).forEach((key) => delete profile[key]);
  if (!restoreState()) initConversation();
  await loadConversationRemote();
  await loadAggregateProfile();
  scrollToBottom();
  focusInput();
}

function bindGlobalSidebarEvents() {
  window.addEventListener("a3-profile-session-change", reloadFromActiveSession);
  window.addEventListener("a3-profile-session-created", reloadFromActiveSession);
}

function unbindGlobalSidebarEvents() {
  window.removeEventListener("a3-profile-session-change", reloadFromActiveSession);
  window.removeEventListener("a3-profile-session-created", reloadFromActiveSession);
  window.dispatchEvent(new CustomEvent("a3-profile-session-refresh"));
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
      messages.value.push(assistantMessage(`分析失败：${res.msg || "请稍后重试"}`));
      ElMessage.error(res.msg || "对话分析失败");
      return;
    }

    Object.assign(profile, res.data.profile || {});
    missingFields.value = res.data.missing_fields || [];
    nextQuestion.value = res.data.next_question || "画像已经基本完整，你可以继续补充，或直接点击生成画像。";
    confidence.value = Number(res.data.confidence || 0);
    isComplete.value = Boolean(res.data.is_complete);
    modelEnabled.value = Boolean(res.data.model_enabled);
    pushAssistant(nextQuestion.value);
    messages.value = cleanMessages(messages.value);
    persistState();
    await saveConversationRemote();
    window.dispatchEvent(new CustomEvent("a3-profile-session-refresh"));
  } catch (error) {
    messages.value.push(assistantMessage("大模型对话接口异常，请确认后端已启动，并检查模型配置。"));
    ElMessage.error(error?.message || "发送失败，请重试");
  } finally {
    sending.value = false;
    scrollToBottom();
    focusInput();
  }
}

async function resetConversation() {
  try {
    await ElMessageBox.confirm("重置后会清空当前会话中的对话与局部画像信息，确定继续吗？", "确认重置", {
      confirmButtonText: "重置",
      cancelButtonText: "取消",
      type: "warning",
    });
  } catch {
    return;
  }

  if (activeSessionId.value) {
    await profileApi.resetSession(activeSessionId.value);
  }
  clearCurrentSessionState();
  await loadAggregateProfile();
  persistState();
  window.dispatchEvent(new CustomEvent("a3-profile-session-refresh"));
  scrollToBottom();
  focusInput();
}

function buildDialogue() {
  return messages.value
    .filter((item) => item.role === "user")
      .map((item, index) => `学生第 ${index + 1} 轮回答：${item.content}`)
    .join("\n");
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
  try {
    const res = await profileApi.create({ dialogue, profile: { ...profile }, conversation: snapshotState() });
    if (res.code !== 200) {
      messages.value.push(assistantMessage(`画像生成失败：${res.msg || "服务暂不可用，请稍后重试。"}`));
      ElMessage.error(res.msg || "画像生成失败");
      return;
    }

    const data = res.data || {};
    Object.assign(profile, data);
    if (data.aggregate_profile) {
      Object.keys(aggregateProfile).forEach((key) => delete aggregateProfile[key]);
      Object.assign(aggregateProfile, data.aggregate_profile);
    }
    messages.value.push(assistantMessage(`画像已生成：${data.profile_summary || "我已经把当前会话与历史会话汇总成综合学习画像。"}`));
    persistState();
    await saveConversationRemote();
    await loadSessions();
    await loadAggregateProfile();
    window.dispatchEvent(new CustomEvent("a3-profile-session-refresh"));
    ElMessage.success("画像生成成功");
  } catch (error) {
    messages.value.push(assistantMessage("画像生成时出现网络或服务异常，请确认后端已启动后再试。"));
    ElMessage.error(error?.message || "画像生成异常");
  } finally {
    loading.value = false;
    sending.value = false;
    scrollToBottom();
    focusInput();
  }
}

watch([messages, draft, missingFields, confidence, isComplete, modelEnabled], () => {
  schedulePersist();
}, { deep: true });

watch(profile, () => {
  schedulePersist();
}, { deep: true });

watch(aggregateProfile, () => {
  schedulePersist();
}, { deep: true });

onMounted(async () => {
  const saved = localStorage.getItem(ACTIVE_PROFILE_SESSION_KEY);
  if (saved) activeSessionId.value = Number(saved);
  await loadSessions();
  if (!restoreState()) initConversation();
  await loadConversationRemote();
  await loadAggregateProfile();
  bindGlobalSidebarEvents();
  scrollToBottom();
  focusInput();
});

onBeforeUnmount(() => {
  persistState();
  window.clearTimeout(saveTimer);
  unbindGlobalSidebarEvents();
});
</script>

<style scoped>
.portrait-page {
  min-height: 100vh;
  padding: 32px 40px;
  background: #ffffff;
}

.chat-home,
.chat-stage {
  min-height: calc(100vh - 64px);
}

.chat-home {
  display: grid;
  place-items: center;
}

.home-center {
  width: min(840px, 100%);
  display: grid;
  gap: 24px;
  justify-items: center;
}

.home-center h1 {
  margin: 0;
  color: #111827;
  font-size: 48px;
  font-weight: 500;
}

.home-composer {
  width: 100%;
  padding: 16px 18px;
  border: 1px solid #ececec;
  border-radius: 28px;
  background: #ffffff;
  box-shadow: 0 8px 30px rgba(15, 23, 42, 0.05);
}

.home-composer :deep(.el-textarea__inner),
.composer-card :deep(.el-textarea__inner) {
  padding: 0;
  border: none;
  box-shadow: none;
  background: transparent;
  color: #111827;
  font-size: 16px;
  line-height: 1.8;
}

.home-actions {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 10px;
  margin-top: 12px;
}

.chat-stage {
  display: flex;
  flex-direction: column;
  width: min(960px, 100%);
  margin: 0 auto;
}

.stage-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 18px;
}

.stage-header h1 {
  margin: 0;
  color: #111827;
  font-size: 28px;
}

.stage-header p {
  margin: 8px 0 0;
  color: #6b7280;
  line-height: 1.6;
}

.stage-badges {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.message-stream {
  flex: 1;
  min-height: 420px;
  max-height: calc(100vh - 360px);
  overflow: auto;
  padding: 8px 0 24px;
}

.message-row {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  width: 100%;
  margin-bottom: 18px;
}

.message-row.user {
  justify-content: flex-end;
}

.assistant-avatar {
  display: grid;
  width: 32px;
  height: 32px;
  place-items: center;
  border-radius: 10px;
  background: #111827;
  color: #ffffff;
  font-size: 12px;
  font-weight: 700;
}

.assistant-avatar.thinking {
  animation: pulse 1.4s ease-in-out infinite;
}

.message-bubble {
  max-width: min(760px, 82%);
  padding: 14px 16px;
  border-radius: 20px;
}

.message-bubble.assistant {
  background: #ffffff;
  border: 1px solid #ececec;
}

.message-bubble.user {
  background: #f3f4f6;
  color: #111827;
}

.message-meta {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 8px;
  color: #6b7280;
  font-size: 12px;
}

.message-content {
  color: inherit;
  white-space: pre-wrap;
  word-break: break-word;
  line-height: 1.85;
}

.thinking-title {
  color: #6b7280;
  font-size: 14px;
  font-weight: 600;
}

.thinking-bubble p {
  margin: 10px 0 0;
  color: #6b7280;
  font-size: 13px;
}

.typing-dots {
  display: flex;
  align-items: center;
  gap: 7px;
  margin-top: 10px;
}

.typing-dots span {
  width: 7px;
  height: 7px;
  border-radius: 999px;
  background: #111827;
  animation: typingBlink 1.2s infinite ease-in-out;
}

.typing-dots span:nth-child(2) { animation-delay: 0.15s; }
.typing-dots span:nth-child(3) { animation-delay: 0.3s; }

.summary-strip {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 14px;
  margin-bottom: 14px;
  padding: 14px 16px;
  border: 1px solid #ececec;
  border-radius: 18px;
  background: #fafafa;
}

.summary-main {
  display: grid;
  gap: 6px;
}

.summary-label {
  color: #6b7280;
  font-size: 12px;
  font-weight: 700;
}

.summary-main strong {
  color: #111827;
  line-height: 1.7;
}

.summary-tags {
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: 8px;
}

.composer-card {
  padding: 16px 18px;
  border: 1px solid #ececec;
  border-radius: 24px;
  background: #ffffff;
  box-shadow: 0 8px 30px rgba(15, 23, 42, 0.05);
}

.composer-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 14px;
  margin-top: 14px;
}

.composer-status {
  display: flex;
  align-items: center;
  gap: 8px;
  color: #6b7280;
  font-size: 13px;
}

.composer-buttons {
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: 10px;
}

@keyframes typingBlink {
  0%, 80%, 100% { opacity: 0.25; transform: translateY(0); }
  40% { opacity: 1; transform: translateY(-3px); }
}

@keyframes pulse {
  0%, 100% { transform: scale(1); opacity: 1; }
  50% { transform: scale(1.05); opacity: 0.86; }
}

@media (max-width: 960px) {
  .portrait-page {
    padding: 20px;
  }

  .home-center h1 {
    font-size: 36px;
  }

  .stage-header,
  .summary-strip,
  .composer-footer {
    flex-direction: column;
  }

  .message-bubble {
    max-width: 100%;
  }
}
</style>
