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
            placeholder="说说你的学习目标、学习历史、知识基础、易错点和资源偏好，我会自动构建八维动态画像"
            @keydown.enter.exact.prevent="sendMessage"
            @keydown.ctrl.enter.prevent="sendMessage"
          />

          <div class="home-actions">
            <el-button type="primary" circle @click="sendMessage" :disabled="!draft.trim() || sending || loading">发送</el-button>
          </div>
        </div>
      </div>
    </div>

    <div class="chat-stage" v-else>
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
            <p>{{ loading ? "正在汇总并生成综合画像..." : "正在理解你的问题，并在后台同步更新画像..." }}</p>
          </div>
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
const LEGACY_WELCOME_MESSAGES = [
  "你好，我是学习画像助手。你可以直接用自然语言告诉我你的专业、学习目标、学习历史、课程进度、易错点和资源偏好；我会自动抽取八维动态学习画像，并在后续学习中随学随新。",
  "你好，我是大模型画像助手。你可以直接用一段自然语言描述学习情况，我会自动抽取专业、目标、基础、薄弱点、偏好等画像维度，并根据缺失信息动态追问。",
  "你可以自由描述你的专业、课程目标、基础、薄弱点和偏好的学习方式。我会自动提取画像，并只追问缺失或模糊的信息。",
];

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

const loading = ref(false);
const sending = ref(false);
const draft = ref("");
const inputRef = ref(null);
const messageBoxRef = ref(null);
const messages = ref([]);
const profile = reactive({});
const aggregateProfile = reactive({});
const missingFields = ref([]);
const nextQuestion = ref("");
const confidence = ref(0);
const isComplete = ref(false);
const modelEnabled = ref(false);
const sessions = ref([]);
const activeSessionId = ref("");
let saveTimer = null;

const showHome = computed(() => {
  const meaningfulMessages = messages.value.filter((item) => item.role === "user");
  return meaningfulMessages.length === 0;
});

const completedCount = computed(() => prompts.filter((item) => previewProfile.value[item.id] && previewProfile.value[item.id] !== DEFAULT_VALUE).length);

const statusText = computed(() => {
  if (loading.value) return "正在汇总当前会话并生成综合画像...";
  if (sending.value) return "正在理解你的问题，并在后台更新画像...";
  if (isComplete.value) return "当前画像信息已经比较完整，后续对话仍会持续自动补充。";
  return `已识别 ${completedCount.value}/${prompts.length} 个画像维度，后续会随对话自动更新`;
});

const valueOfProfile = (primary, legacy) => aggregateProfile[primary] || profile[primary] || (legacy ? aggregateProfile[legacy] || profile[legacy] : "") || DEFAULT_VALUE;

const previewProfile = computed(() => {
  const merged = {};
  for (const prompt of prompts) {
    merged[prompt.id] = valueOfProfile(prompt.id);
  }
  merged.major = valueOfProfile("major");
  merged.target_course = valueOfProfile("target_course");
  merged.knowledge_base = valueOfProfile("knowledge_base", "knowledge_level");
  merged.cognitive_style = valueOfProfile("cognitive_style", "study_style");
  merged.error_prone_points = valueOfProfile("error_prone_points", "weak_points");
  merged.profile_summary = aggregateProfile.profile_summary || profile.profile_summary || DEFAULT_VALUE;
  return merged;
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
  return LEGACY_WELCOME_MESSAGES.includes(normalized)
    || (normalized.includes("画像助手") && normalized.includes("综合学习画像"));
}

function cleanMessages(list = []) {
  const cleaned = [];

  for (const item of list) {
    if (!item?.role || !normalizeText(item.content)) continue;
    const content = normalizeText(item.content);

    if (item.role === "assistant" && isWelcomeContent(content)) {
      continue;
    }

    const next = { ...item, content };
    if (!sameMessage(cleaned[cleaned.length - 1], next)) cleaned.push(next);
  }

  return cleaned;
}

function initConversation() {
  messages.value = [];
}

function pushAssistant(content) {
  const msg = assistantMessage(normalizeText(content));
  if (!sameMessage(messages.value[messages.value.length - 1], msg)) {
    messages.value.push(msg);
  }
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
  nextQuestion.value = "";
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
  if (!activeSessionId.value) {
    messages.value = [];
    return;
  }
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
  } else {
    activeSessionId.value = "";
    setActiveProfileSessionId("");
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
  const savedId = localStorage.getItem(ACTIVE_PROFILE_SESSION_KEY) || "";
  activeSessionId.value = savedId ? Number(savedId) : "";
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
    nextQuestion.value = res.data.next_question || "";
    confidence.value = Number(res.data.confidence || 0);
    isComplete.value = Boolean(res.data.is_complete);
    modelEnabled.value = Boolean(res.data.model_enabled);
    if (res.data.aggregate_profile) {
      Object.keys(aggregateProfile).forEach((key) => delete aggregateProfile[key]);
      Object.assign(aggregateProfile, res.data.aggregate_profile);
    }
    if (res.data.profile_session_id) {
      activeSessionId.value = Number(res.data.profile_session_id);
      setActiveProfileSessionId(res.data.profile_session_id);
    }
    const assistantReply = (res.data.assistant_reply || res.data.next_question || "我已经记录了这条信息，并在后台更新学习画像。").trim();
    pushAssistant(assistantReply);
    messages.value = cleanMessages(messages.value);
    persistState();
    await saveConversationRemote();
    await loadSessions();
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
  else activeSessionId.value = "";
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
  height: 100vh;
  padding: 0 0 24px;
  overflow: hidden;
  background: #ffffff;
}

.chat-home,
.chat-stage {
  height: 100vh;
  min-height: 0;
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

.personal-info-card {
  width: min(840px, 100%);
  border: 1px solid #e5e7eb;
  border-radius: 20px;
  background: linear-gradient(135deg, #ffffff, #f8fbff);
}

.personal-info-card :deep(.el-card__body) {
  padding: 18px;
}

.personal-info-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 14px;
  margin-bottom: 12px;
}

.personal-info-head div {
  display: grid;
  gap: 4px;
}

.personal-info-head b {
  color: #111827;
  font-size: 15px;
}

.personal-info-head span {
  color: #6b7280;
  font-size: 13px;
}

.personal-info-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
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
  position: relative;
  display: flex;
  flex-direction: column;
  width: 100%;
  max-width: none;
  margin: 0;
  padding: 0;
}

.visual-only-stage {
  width: min(1120px, 100%);
  overflow-y: auto;
  padding-right: 6px;
}

.visual-only-stage .profile-visual-panel {
  flex: 0 0 auto;
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
  min-height: 0;
  overflow-y: auto;
  overflow-x: hidden;
  padding: 32px 0 180px;
}

.message-row {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  width: 100%;
  max-width: 1040px;
  margin: 0 auto 30px;
  padding: 0 28px;
}

.message-row.user {
  justify-content: flex-end;
}

.assistant-avatar {
  display: grid;
  width: 28px;
  height: 28px;
  place-items: center;
  border-radius: 8px;
  background: #1f2937;
  color: #ffffff;
  font-size: 11px;
  font-weight: 700;
  flex: 0 0 auto;
  margin-top: 2px;
}

.assistant-avatar.thinking {
  animation: pulse 1.4s ease-in-out infinite;
}

.message-bubble {
  max-width: min(780px, 78%);
  padding: 0;
  border-radius: 0;
  box-shadow: none;
}

.message-bubble.assistant {
  background: transparent;
  border: none;
}

.message-bubble.user {
  padding: 16px 18px;
  border-radius: 24px;
  background: #f4f4f5;
  color: #111827;
}

.message-meta {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 10px;
  color: #6b7280;
  font-size: 12px;
}

.message-bubble.user .message-meta {
  margin-bottom: 6px;
}

.message-content {
  color: inherit;
  white-space: pre-wrap;
  word-break: break-word;
  line-height: 1.95;
  font-size: 17px;
}

.message-bubble.assistant .message-meta span {
  letter-spacing: 0.08em;
  text-transform: uppercase;
  font-size: 11px;
  font-weight: 700;
  color: #9ca3af;
}

.message-bubble.assistant .message-content {
  color: #1f2937;
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

.profile-visual-panel {
  display: grid;
  grid-template-columns: 320px minmax(0, 1fr);
  gap: 14px;
  margin-bottom: 14px;
}

.radar-card,
.profile-timeline-card,
.dimension-card {
  border: 1px solid #ececec;
  border-radius: 18px;
  background: #ffffff;
  box-shadow: 0 8px 24px rgba(15, 23, 42, 0.04);
}

.radar-card {
  min-width: 0;
  padding: 14px;
}

.visual-card-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 10px;
  margin-bottom: 10px;
}

.visual-card-header.compact {
  margin-bottom: 8px;
}

.visual-card-header strong,
.dimension-card-top strong {
  display: block;
  color: #111827;
  font-size: 14px;
}

.eyebrow {
  display: block;
  margin-bottom: 4px;
  color: #6b7280;
  font-size: 12px;
  font-weight: 700;
}

.profile-radar {
  width: 100%;
  height: 230px;
}

.dimension-card-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 10px;
}

.dimension-card {
  min-height: 108px;
  padding: 12px;
  background: #fafafa;
}

.dimension-card.filled {
  background: #f8fbff;
  border-color: #dbeafe;
}

.dimension-card-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
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
  display: -webkit-box;
  margin: 0;
  overflow: hidden;
  color: #4b5563;
  font-size: 12px;
  line-height: 1.6;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 3;
}

.profile-timeline-card {
  margin-bottom: 14px;
  padding: 12px 14px;
  background: #fbfbfc;
}

.profile-timeline {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
}

.timeline-item {
  display: flex;
  align-items: flex-start;
  gap: 9px;
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
  font-size: 13px;
}

.timeline-item p {
  margin: 4px 0 0;
  color: #6b7280;
  font-size: 12px;
  line-height: 1.5;
}

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
  position: absolute;
  left: 50%;
  bottom: 28px;
  transform: translateX(-50%);
  width: min(920px, calc(100% - 56px));
  padding: 14px 18px 12px;
  border: 1px solid #e8e8eb;
  border-radius: 24px;
  background: #ffffff;
  box-shadow: 0 10px 36px rgba(15, 23, 42, 0.08);
  z-index: 5;
}

.composer-card :deep(.el-textarea__inner) {
  font-size: 15px;
  line-height: 1.75;
}

.composer-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 14px;
  margin-top: 10px;
}

.composer-status {
  display: flex;
  align-items: center;
  gap: 8px;
  color: #8b93a1;
  font-size: 12px;
}

.composer-buttons {
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: 8px;
}

.composer-buttons :deep(.el-button) {
  height: 40px;
  border-radius: 999px;
  padding: 0 18px;
}

.composer-buttons :deep(.el-button--primary) {
  box-shadow: none;
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
    padding: 0 0 16px;
  }

  .home-center h1 {
    font-size: 36px;
  }

  .message-row {
    padding: 0 16px;
  }

  .stage-header,
  .summary-strip,
  .composer-footer {
    flex-direction: column;
  }

  .profile-visual-panel,
  .profile-timeline {
    grid-template-columns: 1fr;
  }

  .dimension-card-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .profile-radar {
    height: 220px;
  }

  .message-bubble {
    max-width: 100%;
  }

  .composer-card {
    width: calc(100% - 24px);
    bottom: 12px;
  }
}
</style>
