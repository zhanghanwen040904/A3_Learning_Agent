<template>
  <div class="page profile-grid">
    <section class="conversation-workspace panel">
      <aside class="session-panel">
        <div class="session-head">
          <strong>画像会话</strong>
          <el-button type="primary" size="small" @click="newSession">新建</el-button>
        </div>
      <div class="session-list">
        <div
          v-for="item in sessions"
          :key="item.id"
          :class="['session-item', { active: item.id === activeSessionId }]"
          @click="switchSession(item.id)"
        >
          <div class="session-title-row">
            <strong>{{ item.title || `画像对话 ${item.id}` }}</strong>
            <el-button
              class="session-delete"
              text
              type="danger"
              size="small"
              :disabled="sending || loading"
              @click.stop="deleteSession(item)"
            >删除</el-button>
          </div>
        </div>
      </div>
      <el-alert
        type="info"
        :closable="false"
        title="切换画像会话后，学习资源、路径和评估数据会随当前画像同步更新。"
      />
      </aside>

      <section class="chat-panel">
        <div class="panel-head">
          <div>
            <strong>学习画像构建</strong>
            <p>通过自然语言对话收集学习目标、基础水平、薄弱点和资源偏好。</p>
          </div>
          <el-tag :type="modelEnabled ? 'success' : 'info'">{{ modelEnabled ? '智能分析中' : '本地辅助模式' }}</el-tag>
        </div>

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
      </section>
    </section>

    <div class="profile-side">
      <el-card class="panel">
        <template #header>画像摘要</template>
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
            <span>基础情况</span>
            <strong>{{ previewProfile.knowledge_level }}</strong>
          </div>
          <div class="summary-item">
            <span>知识短板</span>
            <strong>{{ previewProfile.weak_points }}</strong>
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
const STORAGE_PREFIX = "a3_learning_agent_profile_conversation_v3";
const WELCOME_MESSAGE = "\u4f60\u597d\uff0c\u6211\u662f\u5927\u6a21\u578b\u753b\u50cf\u52a9\u624b\u3002\u4f60\u53ef\u4ee5\u76f4\u63a5\u7528\u4e00\u6bb5\u81ea\u7136\u8bed\u8a00\u63cf\u8ff0\u5b66\u4e60\u60c5\u51b5\uff0c\u6211\u4f1a\u81ea\u52a8\u62bd\u53d6\u4e13\u4e1a\u3001\u76ee\u6807\u3001\u57fa\u7840\u3001\u8584\u5f31\u70b9\u3001\u504f\u597d\u7b49\u753b\u50cf\u7ef4\u5ea6\uff0c\u5e76\u6839\u636e\u7f3a\u5931\u4fe1\u606f\u52a8\u6001\u8ffd\u95ee\u3002\u4f60\u53ef\u4ee5\u7528\u4e00\u6bb5\u8bdd\u81ea\u7531\u63cf\u8ff0\u4f60\u7684\u4e13\u4e1a\u3001\u8bfe\u7a0b\u76ee\u6807\u3001\u57fa\u7840\u3001\u8584\u5f31\u70b9\u548c\u504f\u597d\u7684\u5b66\u4e60\u65b9\u5f0f\u3002";
const LEGACY_WELCOME_MESSAGES = [
  "\u4f60\u597d\uff0c\u6211\u662f\u5927\u6a21\u578b\u753b\u50cf\u52a9\u624b\u3002\u4f60\u53ef\u4ee5\u76f4\u63a5\u7528\u4e00\u6bb5\u81ea\u7136\u8bed\u8a00\u63cf\u8ff0\u5b66\u4e60\u60c5\u51b5\uff0c\u6211\u4f1a\u81ea\u52a8\u62bd\u53d6\u4e13\u4e1a\u3001\u76ee\u6807\u3001\u57fa\u7840\u3001\u8584\u5f31\u70b9\u3001\u504f\u597d\u7b49\u753b\u50cf\u7ef4\u5ea6\uff0c\u5e76\u6839\u636e\u7f3a\u5931\u4fe1\u606f\u52a8\u6001\u8ffd\u95ee\u3002",
  "\u4f60\u53ef\u4ee5\u7528\u4e00\u6bb5\u8bdd\u81ea\u7531\u63cf\u8ff0\u4f60\u7684\u4e13\u4e1a\u3001\u8bfe\u7a0b\u76ee\u6807\u3001\u57fa\u7840\u3001\u8584\u5f31\u70b9\u548c\u504f\u597d\u7684\u5b66\u4e60\u65b9\u5f0f\u3002\u6211\u4f1a\u81ea\u52a8\u63d0\u53d6\u753b\u50cf\uff0c\u5e76\u53ea\u8ffd\u95ee\u7f3a\u5931\u6216\u6a21\u7cca\u7684\u4fe1\u606f\u3002",
];

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

function sameMessage(a, b) {
  return a?.role === b?.role && normalizeText(a?.content) === normalizeText(b?.content);
}

function isWelcomeContent(content) {
  const normalized = normalizeText(content);
  return normalized === WELCOME_MESSAGE
    || LEGACY_WELCOME_MESSAGES.includes(normalized)
    || (normalized.includes("\u753b\u50cf\u52a9\u624b") && normalized.includes("\u81ea\u7136\u8bed\u8a00\u63cf\u8ff0"));
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

  if (!cleaned.length) return cleaned;
  if (cleaned[0].role !== "assistant" || !isWelcomeContent(cleaned[0].content)) {
    cleaned.unshift(assistantMessage(WELCOME_MESSAGE));
  }
  return cleaned;
}

function pushAssistant(content) {
  const msg = assistantMessage(normalizeText(content));
  if (!sameMessage(messages.value[messages.value.length - 1], msg)) {
    messages.value.push(msg);
  }
}

function userMessage(content) {
  return { role: "user", content, time: timeLabel() };
}

function initConversation() {
  messages.value = [assistantMessage(WELCOME_MESSAGE)];
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

    const restoredMessages = cleanMessages(saved.messages);
    if (!restoredMessages.length) return false;
    messages.value = restoredMessages;
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
  messages.value = Array.isArray(saved.messages) && saved.messages.length ? cleanMessages(saved.messages) : [];
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
      const remoteMessages = cleanMessages(res.data.messages);
      if (remoteMessages.length && remoteMessages.length >= messages.value.length) {
        messages.value = remoteMessages;
        persistState();
      }
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

async function deleteSession(item) {
  if (!item?.id || sending.value || loading.value) return;
  try {
    await ElMessageBox.confirm(
      `确定删除“${item.title || `画像对话 ${item.id}`}”吗？该画像关联的对话、学习资源、路径和答疑记录也会一并删除。`,
      "删除画像会话",
      {
        confirmButtonText: "删除",
        cancelButtonText: "取消",
        type: "warning",
        confirmButtonClass: "el-button--danger",
      }
    );
  } catch {
    return;
  }

  const wasActive = Number(item.id) === Number(activeSessionId.value);
  const res = await profileApi.deleteSession(item.id);
  if (res.code !== 200) {
    ElMessage.error(res.msg || "删除画像会话失败");
    return;
  }

  localStorage.removeItem(storageKey(item.id));
  const nextId = res.data?.active_session_id;
  if (nextId) {
    activeSessionId.value = Number(nextId);
    setActiveProfileSessionId(nextId);
  } else {
    activeSessionId.value = "";
    setActiveProfileSessionId("");
  }
  await loadSessions();
  if (wasActive) {
    Object.keys(profile).forEach((key) => delete profile[key]);
    if (!restoreState()) initConversation();
    await loadConversationRemote();
    await loadProfile();
    scrollToBottom();
  }
  ElMessage.success("画像会话已删除");
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

  const latest = messages.value[messages.value.length - 1];
  if (latest?.role === "user" && normalizeText(latest.content) === text) {
    ElMessage.warning("这条回答已经发送过了");
    return;
  }

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
    pushAssistant(nextQuestion.value);
    messages.value = cleanMessages(messages.value);
    persistState();
    await saveConversationRemote();
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
  grid-template-columns: minmax(0, 1fr);
  gap: 18px;
  align-items: start;
  width: 100%;
  min-width: 0;
}

.conversation-workspace {
  display: grid;
  grid-template-columns: 220px minmax(0, 1fr);
  min-width: 0;
}

.session-panel,
.chat-panel,
.profile-side,
.profile-side .panel {
  min-width: 0;
}

.session-panel {
  padding: 24px;
  border-right: 1px solid #eef2f6;
  background: #fbfcff;
}

.chat-panel {
  display: flex;
  flex-direction: column;
  gap: 16px;
  min-width: 0;
  padding: 24px;
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
  margin-bottom: 16px;
}

.session-item {
  display: grid;
  gap: 6px;
  width: 100%;
  padding: 12px;
  text-align: left;
  border: 1px solid #e5eaf3;
  border-radius: 14px;
  background: #ffffff;
  color: #101828;
  cursor: pointer;
  transition: all 0.18s ease;
}

.session-item:hover {
  border-color: #b2ccff;
  transform: translateY(-1px);
  box-shadow: 0 10px 22px rgba(15, 23, 42, 0.06);
}

.session-item strong {
  font-size: 13px;
  font-weight: 500;
  line-height: 1.55;
}


.session-item.active {
  border-color: #84caff;
  background: #eff8ff;
  box-shadow: 0 10px 24px rgba(21, 94, 239, 0.12);
}

.session-title-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.session-delete {
  opacity: 0;
  flex: 0 0 auto;
  padding: 2px 3px;
  font-size: 12px;
  font-weight: 400;
  transition: opacity 0.18s ease;
}

.session-item:hover .session-delete,
.session-item.active .session-delete {
  opacity: 1;
}


.profile-side {
  display: grid;
  grid-template-columns: 1fr;
  gap: 18px;
  align-items: start;
}

.panel-head,
.radar-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
}

.panel-head strong,
.radar-head span {
  color: #101828;
  font-size: 16px;
}

.panel-head p {
  max-width: 560px;
  margin: 6px 0 0;
  color: #667085;
  font-weight: 400;
  line-height: 1.6;
}

.radar-head small {
  color: #667085;
  font-size: 12px;
  font-weight: 400;
}

.messages {
  height: 410px;
  overflow: auto;
  padding: 20px;
  scroll-behavior: smooth;
  border: 1px solid #e5eaf3;
  border-radius: 18px;
  background: linear-gradient(180deg, #f8fafc 0%, #ffffff 100%);
}

.msg {
  max-width: 86%;
  margin-bottom: 14px;
  padding: 13px 15px;
  border: 1px solid #eef2f6;
  border-radius: 16px;
  line-height: 1.72;
  box-shadow: 0 8px 18px rgba(15, 23, 42, 0.04);
}

.msg-role {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  margin-bottom: 6px;
  font-size: 12px;
  color: #667085;
}

.msg-role small {
  color: #98a2b3;
  font-size: 11px;
}

.msg-content {
  color: #344054;
  white-space: pre-wrap;
  word-break: break-word;
}

.msg.assistant {
  background: #ffffff;
  border-top-left-radius: 6px;
}

.msg.user {
  margin-left: auto;
  border-color: #b2ddff;
  color: #1849a9;
  background: #eff8ff;
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
  color: #667085;
}

.typing-dots span {
  width: 7px;
  height: 7px;
  border-radius: 999px;
  background: #2e90fa;
  animation: typingBlink 1.2s infinite ease-in-out;
}

.typing-dots span:nth-child(2) { animation-delay: 0.15s; }
.typing-dots span:nth-child(3) { animation-delay: 0.3s; }

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
  border: 1px solid #e5eaf3;
}

.followup-card {
  background: #ecfdf3;
  border-color: #abefc6;
}

.prompt-label {
  margin-bottom: 6px;
  color: #155eef;
  font-size: 12px;
  font-weight: 700;
}

.prompt-text {
  color: #101828;
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
  color: #667085;
  font-size: 13px;
}

.action-buttons {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
}

.summary-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 14px;
  margin-top: 18px;
}

.summary-item {
  min-height: 100px;
  padding: 16px;
  border-radius: 16px;
  background: linear-gradient(180deg, #ffffff 0%, #f8fafc 100%);
  border: 1px solid #eef2f6;
}

.summary-item span {
  display: block;
  margin-bottom: 7px;
  font-size: 12px;
  color: #667085;
}

.summary-item strong {
  color: #101828;
  line-height: 1.55;
}

.summary-item strong {
  word-break: break-word;
}

.profile-side :deep(.el-descriptions__cell),
.profile-side :deep(.el-descriptions__content) {
  min-width: 0;
  word-break: break-word;
}

.radar {
  height: 240px;
}

@media (max-width: 1320px) {
  .conversation-workspace {
    grid-template-columns: 200px minmax(0, 1fr);
  }

  .summary-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 900px) {
  .profile-grid,
  .conversation-workspace,
  .profile-side {
    grid-template-columns: 1fr;
  }

  .session-panel {
    border-right: none;
    border-bottom: 1px solid #eef2f6;
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
