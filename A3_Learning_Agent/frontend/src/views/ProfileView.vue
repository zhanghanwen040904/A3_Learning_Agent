<template>
  <div class="portrait-page">
    <div class="chat-home" v-if="showHome">
      <div class="home-center">
        <h1>What would you like to learn?</h1>

        <div class="home-composer composer-shell">
          <div class="composer-main">
            <el-input
              ref="inputRef"
              v-model="draft"
              type="textarea"
              :autosize="{ minRows: 1, maxRows: 6 }"
              resize="none"
              :disabled="sending"
              placeholder="可以先说说你在学什么、卡在哪里，或者现在想完成什么任务"
              @keydown.enter.exact.prevent="sendMessage"
              @keydown.ctrl.enter.prevent="sendMessage"
            />

            <div class="composer-tools">
              <button
                class="composer-send-button"
                type="button"
                :disabled="!draft.trim() || sending"
                @click="sendMessage"
              >
                <el-icon v-if="!sending"><Top /></el-icon>
                <span v-else class="send-stop-dot"></span>
              </button>
            </div>
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
          <div :class="['message-bubble', item.role]">
            <div class="message-meta">
              <span>{{ item.role === "assistant" ? "MultiTutor" : "我" }}</span>
              <small v-if="item.time">{{ item.time }}</small>
            </div>
            <div
              :class="[
                'message-content',
                'markdown-body',
                { 'diagram-text-card': isDiagramLikeMessage(item) }
              ]"
              v-html="renderMarkdown(item.content)"
            ></div>
            <div v-if="item.enhancement_pending" class="enhancement-pending">
              正在补充图解 / 巩固内容...
            </div>
            <div v-if="item.diagram_image" class="enhancement-card">
              <div class="enhancement-title">图解说明</div>
              <img :src="resolvedDiagramImage(item)" alt="图解说明" class="diagram-image" />
            </div>
            <div v-else-if="isDiagramLikeMessage(item)" class="enhancement-card">
              <div class="enhancement-title">图解说明</div>
              <img :src="resolvedDiagramImage(item)" alt="图解说明" class="diagram-image" />
            </div>
            <div v-if="item.quiz_items?.length" class="enhancement-card quiz-card">
              <div class="enhancement-title">顺手巩固一下</div>
              <div v-for="(quiz, quizIndex) in item.quiz_items" :key="quizIndex" class="quiz-item">
                <strong>{{ quizIndex + 1 }}. {{ quiz.question }}</strong>
                <p v-if="quiz.answer_hint">{{ quiz.answer_hint }}</p>
              </div>
            </div>
          </div>
        </div>

        <div v-if="sending" class="message-row assistant">
          <div class="message-bubble assistant thinking-bubble">
            <div class="thinking-title">Thinking</div>
            <div class="typing-dots">
              <span></span>
              <span></span>
              <span></span>
            </div>
            <p>{{ profileSyncing ? "回答已返回，正在后台同步更新画像..." : "正在理解你的问题..." }}</p>
          </div>
        </div>
      </div>

      <div class="stage-actions">
        <el-button :disabled="sending" @click="resetConversation">重置当前会话</el-button>
      </div>

      <div class="composer-card composer-shell">
        <div class="composer-main">
          <el-input
            ref="inputRef"
            v-model="draft"
            type="textarea"
            :autosize="{ minRows: 1, maxRows: 6 }"
            resize="none"
            :disabled="sending"
            placeholder="继续输入你的问题、学习进展或当前任务"
            @keydown.enter.exact.prevent="sendMessage"
            @keydown.ctrl.enter.prevent="sendMessage"
          />

          <div class="composer-tools">
            <div class="composer-status">
              <el-icon v-if="sending" class="is-loading"><Loading /></el-icon>
              <span>{{ sending ? "Thinking" : "Ready" }}</span>
            </div>
            <button
              class="composer-send-button"
              type="button"
              :disabled="!draft.trim() || sending"
              @click="sendMessage"
            >
              <el-icon v-if="!sending"><Top /></el-icon>
              <span v-else class="send-stop-dot"></span>
            </button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref, watch } from "vue";
import { Loading, Top } from "@element-plus/icons-vue";
import { ElMessage, ElMessageBox } from "element-plus";
import MarkdownIt from "markdown-it";
import { ACTIVE_PROFILE_SESSION_KEY, profileApi, setActiveProfileSessionId } from "../api";

const DEFAULT_VALUE = "待进一步观察";
const STORAGE_PREFIX = "a3_learning_agent_profile_conversation_v6";
const md = new MarkdownIt({ html: false, linkify: true, breaks: true });
const LEGACY_WELCOME_MESSAGES = [
  "你好，我是学习画像助手。你可以直接用自然语言告诉我你的专业、学习目标、学习历史、课程进度、易错点和资源偏好；我会自动抽取八维动态学习画像，并在后续学习中随学随新。",
  "你好，我是大模型画像助手。你可以直接用一段自然语言描述学习情况，我会自动抽取专业、目标、基础、薄弱点、偏好等画像维度，并根据缺失信息动态追问。",
  "你可以自由描述你的专业、课程目标、基础、薄弱点和偏好的学习方式。我会自动提取画像，并只追问缺失或模糊的信息。",
];

const corePrompts = [
  { id: "current_topic", label: "当前学习主题" },
  { id: "mastery_level", label: "掌握程度" },
  { id: "current_difficulty", label: "当前困难点" },
  { id: "task_goal", label: "当前任务目标" },
  { id: "support_preference", label: "适配支持方式" },
  { id: "engagement_level", label: "学习投入状态" },
];

const supportPrompts = [
  { id: "learning_background", label: "学习背景" },
  { id: "recent_progress", label: "最近进展" },
  { id: "schedule_pattern", label: "学习节奏" },
  { id: "preferred_resource", label: "资源偏好" },
  { id: "weak_knowledge_points", label: "薄弱知识点" },
  { id: "recommended_next_step", label: "下一步建议" },
];

const profileSyncing = ref(false);
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
let profileSyncToken = 0;
let sessionLoadToken = 0;

const showHome = computed(() => {
  const meaningfulMessages = messages.value.filter((item) => item.role === "user");
  return meaningfulMessages.length === 0;
});

const completedCount = computed(() =>
  corePrompts.filter((item) => previewProfile.value[item.id] && previewProfile.value[item.id] !== DEFAULT_VALUE).length
);

const statusText = computed(() => {
  if (profileSyncing.value) return "回答已返回，画像正在后台静默更新...";
  if (sending.value) return "正在理解你的问题...";
  if (isComplete.value) return "当前核心学习状态已经较完整，后续对话仍会持续自动补充。";
  return `已识别 ${completedCount.value}/${corePrompts.length} 个核心状态维度，后续会随对话自动更新`;
});

const valueOfProfile = (primary, legacy) =>
  aggregateProfile[primary]
  || profile[primary]
  || (legacy ? aggregateProfile[legacy] || profile[legacy] : "")
  || DEFAULT_VALUE;

const previewProfile = computed(() => {
  const merged = {};
  for (const prompt of corePrompts) {
    merged[prompt.id] = valueOfProfile(prompt.id);
  }
  for (const prompt of supportPrompts) {
    merged[prompt.id] = valueOfProfile(prompt.id);
  }
  merged.major = valueOfProfile("major");
  merged.target_course = valueOfProfile("target_course");
  merged.current_topic = valueOfProfile("current_topic", "course_progress");
  merged.mastery_level = valueOfProfile("mastery_level", "knowledge_base");
  merged.current_difficulty = valueOfProfile("current_difficulty", "error_prone_points");
  merged.task_goal = valueOfProfile("task_goal", "study_goal");
  merged.support_preference = valueOfProfile("support_preference", "cognitive_style");
  merged.engagement_level = valueOfProfile("engagement_level");
  merged.learning_background = valueOfProfile("learning_background", "learning_history");
  merged.recent_progress = valueOfProfile("recent_progress", "course_progress");
  merged.schedule_pattern = valueOfProfile("schedule_pattern", "study_time_prefer");
  merged.preferred_resource = valueOfProfile("preferred_resource");
  merged.weak_knowledge_points = valueOfProfile("weak_knowledge_points", "weak_points");
  merged.recommended_next_step = valueOfProfile("recommended_next_step");
  merged.portrait_confidence = valueOfProfile("portrait_confidence");
  merged.profile_summary = aggregateProfile.profile_summary || profile.profile_summary || DEFAULT_VALUE;
  return merged;
});

function timeLabel() {
  const now = new Date();
  const month = String(now.getMonth() + 1).padStart(2, "0");
  const day = String(now.getDate()).padStart(2, "0");
  const hour = String(now.getHours()).padStart(2, "0");
  const minute = String(now.getMinutes()).padStart(2, "0");
  return `${month}-${day} ${hour}:${minute}`;
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

    const next = {
      ...item,
      content,
      quiz_items: Array.isArray(item.quiz_items) ? item.quiz_items : [],
      sources: Array.isArray(item.sources) ? item.sources : [],
      diagram_image: item.diagram_image || "",
    };
    if (!sameMessage(cleaned[cleaned.length - 1], next)) cleaned.push(next);
  }

  return cleaned;
}

function initConversation() {
  messages.value = [];
}

function pushAssistant(content) {
  const msg = typeof content === "string"
    ? assistantMessage(normalizeText(content))
    : {
        ...assistantMessage(normalizeText(content?.content || "")),
        diagram_image: content?.diagram_image || "",
        quiz_items: Array.isArray(content?.quiz_items) ? content.quiz_items : [],
        sources: Array.isArray(content?.sources) ? content.sources : [],
        need_diagram: Boolean(content?.need_diagram),
        need_quiz: Boolean(content?.need_quiz),
        enhancement_pending: Boolean(content?.enhancement_pending),
      };
  if (!sameMessage(messages.value[messages.value.length - 1], msg)) {
    messages.value.push(msg);
    return messages.value.length - 1;
  }
  return messages.value.length - 1;
}

function renderMarkdown(content) {
  const compact = normalizeText(content)
    .replace(/\r/g, "")
    .replace(/[ \t]+\n/g, "\n")
    .replace(/\n[ \t]+\n/g, "\n\n")
    .replace(/\n{3,}/g, "\n\n")
    .replace(/(?:\n\s*){2,}(?=[•○\-]\s)/g, "\n")
    .replace(/(?:\n\s*){2,}(?=\d+\.\s)/g, "\n")
    .replace(/([：:。！？；])\n(?=[一二三四五六七八九十\d]+\s*[、.])/g, "$1\n")
    .replace(/\n(?=[•○\-]\s)/g, "\n")
    .replace(/\n(?=\d+\.\s)/g, "\n");
  return md.render(compact);
}

function isDiagramLikeMessage(item) {
  if (!item || item.role !== "assistant") return false;
  if (item.diagram_image) return true;
  const text = normalizeText(item.content);
  if (!text) return false;
  return /图解|结构梳理|流程梳理|核心要素|知识点拆解|对照来看|可以照着看/.test(text)
    && /1\.|2\.|3\.|4\.|•|○|\- /.test(text);
}

function extractDiagramTitle(text) {
  const normalized = normalizeText(text)
    .replace(/\*\*/g, "")
    .replace(/「|」|“|”/g, "");

  const patterns = [
    /关于(.{1,24}?)(?:的图解|图解|核心内容|核心要点|知识梳理)/,
    /(.{2,20}?)(?:框架|模型|方法|流程|概念|章节|知识点).{0,8}(?:图解|梳理)/,
    /请解释知识点[“"]?(.{2,20}?)[”"]?/,
  ];

  for (const pattern of patterns) {
    const match = normalized.match(pattern);
    if (match?.[1]) {
      return `${match[1].trim()} 图解`;
    }
  }

  const firstMeaningfulLine = normalized
    .split("\n")
    .map((line) => line.trim())
    .find((line) => line && !/^(当然可以|没问题|以下是|你可以对照来看|可以照着看)/.test(line)) || "";

  const cleaned = firstMeaningfulLine
    .replace(/^(当然可以|没问题|以下是|这里是|下面是)[！!：:\s]*/, "")
    .replace(/图解核心内容梳理.*/, "")
    .replace(/教材中明确提到了.*/, "")
    .trim();

  return cleaned.slice(0, 20) || "知识点图解";
}

function extractDiagramBlocks(text) {
  const normalized = normalizeText(text)
    .replace(/\*\*/g, "")
    .replace(/\r/g, "")
    .replace(/\n{2,}/g, "\n");

  const lines = normalized
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean);

  const blocks = [];
  let current = null;

  const titleLinePattern = /^(\d+)[\.、]\s*(.+)$/;

  for (const line of lines) {
    const titleMatch = line.match(titleLinePattern);
    if (titleMatch) {
      if (current?.title) blocks.push(current);

      const raw = titleMatch[2].trim();
      const segments = raw.split(/[：:]/);
      const title = (segments[0] || raw)
        .replace(/^[\-•○]\s*/, "")
        .replace(/（.*?）/g, "")
        .trim();
      const body = segments.slice(1).join("：").trim();

      current = {
        title,
        body: body ? [body] : [],
      };
      continue;
    }

    if (current) {
      const cleaned = line
        .replace(/^[\-•○]\s*/, "")
        .replace(/^\d+[\.、]\s*/, "")
        .trim();
      if (cleaned && cleaned.length >= 3) current.body.push(cleaned);
    }
  }

  if (current?.title) blocks.push(current);

  const result = blocks
    .map((block) => ({
      title: String(block.title || "").slice(0, 14),
      body: (block.body || []).join("；").replace(/\s+/g, " ").trim(),
    }))
    .filter((block) => block.title)
    .slice(0, 4);

  if (result.length) {
    return result.map((block) => ({
      ...block,
      body: block.body || `${block.title}是这个知识点图解中的关键部分。`,
    }));
  }

  const fallbackPoints = normalized
    .split(/\n|。|；/)
    .map((item) => item.replace(/^[•○\-]\s*/, "").trim())
    .filter((item) => item.length >= 6)
    .slice(0, 4);

  return fallbackPoints.map((item) => {
    const parts = item.split(/[：:]/);
    return {
      title: (parts[0] || item).slice(0, 12),
      body: (parts.slice(1).join("：") || item).slice(0, 42),
    };
  });
}

function wrapSvgText(text, maxChars = 10, maxLines = 3) {
  const compact = String(text || "").replace(/\s+/g, "");
  const lines = [];
  for (let i = 0; i < compact.length; i += maxChars) {
    lines.push(compact.slice(i, i + maxChars));
    if (lines.length >= maxLines) break;
  }
  return lines.length ? lines : [""];
}

function escapeSvgText(text) {
  return String(text || "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}

function buildFallbackDiagramImage(text) {
  const title = extractDiagramTitle(text);
  const blocks = extractDiagramBlocks(text);
  const width = 1120;
  const height = 680;
  const flowTerms = blocks.map((item) => item.title.slice(0, 8));
  const cardW = 210;
  const cardH = 86;
  const startX = 90;
  const gap = 250;
  const flowY = 180;

  const svg = [
    `<svg xmlns="http://www.w3.org/2000/svg" width="${width}" height="${height}" viewBox="0 0 ${width} ${height}">`,
    `<defs>
      <linearGradient id="pageBg" x1="0" x2="1" y1="0" y2="1">
        <stop offset="0%" stop-color="#f8fbff"/>
        <stop offset="100%" stop-color="#eef4ff"/>
      </linearGradient>
      <linearGradient id="titleBg" x1="0" x2="1" y1="0" y2="0">
        <stop offset="0%" stop-color="#2563eb"/>
        <stop offset="100%" stop-color="#60a5fa"/>
      </linearGradient>
      <marker id="arrow" markerWidth="12" markerHeight="12" refX="10" refY="6" orient="auto">
        <path d="M2,2 L10,6 L2,10 Z" fill="#60a5fa"/>
      </marker>
    </defs>`,
    `<rect width="${width}" height="${height}" rx="28" fill="url(#pageBg)"/>`,
    `<rect x="24" y="24" width="${width - 48}" height="${height - 48}" rx="24" fill="#ffffff" stroke="#dbeafe" stroke-width="2"/>`,
    `<rect x="54" y="54" width="${width - 108}" height="92" rx="22" fill="url(#titleBg)"/>`,
    `<text x="${width / 2}" y="97" text-anchor="middle" font-family="Microsoft YaHei, PingFang SC, sans-serif" font-size="30" font-weight="800" fill="#ffffff">${escapeSvgText(title)}</text>`,
    `<text x="${width / 2}" y="127" text-anchor="middle" font-family="Microsoft YaHei, PingFang SC, sans-serif" font-size="15" fill="rgba(255,255,255,0.88)">根据当前回答自动整理出的知识图解</text>`,
    `<text x="70" y="170" font-family="Microsoft YaHei, PingFang SC, sans-serif" font-size="18" font-weight="700" fill="#0f172a">核心主线</text>`,
  ];

  flowTerms.forEach((term, idx) => {
    const x = startX + idx * gap;
    svg.push(`<rect x="${x}" y="${flowY}" width="${cardW}" height="${cardH}" rx="22" fill="#eff6ff" stroke="#60a5fa" stroke-width="2"/>`);
    wrapSvgText(term, 8, 2).forEach((line, lineIndex) => {
      svg.push(`<text x="${x + cardW / 2}" y="${flowY + 38 + lineIndex * 22}" text-anchor="middle" font-family="Microsoft YaHei, PingFang SC, sans-serif" font-size="18" font-weight="700" fill="#0f172a">${escapeSvgText(line)}</text>`);
    });
    if (idx < flowTerms.length - 1) {
      svg.push(`<line x1="${x + cardW + 10}" y1="${flowY + cardH / 2}" x2="${startX + (idx + 1) * gap - 12}" y2="${flowY + cardH / 2}" stroke="#93c5fd" stroke-width="4" marker-end="url(#arrow)"/>`);
    }
  });

  svg.push(`<text x="70" y="316" font-family="Microsoft YaHei, PingFang SC, sans-serif" font-size="18" font-weight="700" fill="#0f172a">图解要点</text>`);

  const positions = [
    [70, 338],
    [575, 338],
    [70, 500],
    [575, 500],
  ];
  blocks.slice(0, 4).forEach((point, idx) => {
    const [x, y] = positions[idx];
    svg.push(`<rect x="${x}" y="${y}" width="475" height="132" rx="20" fill="#ffffff" stroke="#dbeafe" stroke-width="2"/>`);
    svg.push(`<circle cx="${x + 28}" cy="${y + 28}" r="14" fill="#2563eb"/>`);
    svg.push(`<text x="${x + 28}" y="${y + 34}" text-anchor="middle" font-family="Microsoft YaHei, PingFang SC, sans-serif" font-size="14" font-weight="700" fill="#ffffff">${idx + 1}</text>`);
    svg.push(`<text x="${x + 58}" y="${y + 34}" font-family="Microsoft YaHei, PingFang SC, sans-serif" font-size="18" font-weight="700" fill="#1e3a8a">${escapeSvgText(point.title)}</text>`);
    wrapSvgText(point.body, 22, 3).forEach((line, lineIndex) => {
      svg.push(`<text x="${x + 58}" y="${y + 66 + lineIndex * 22}" font-family="Microsoft YaHei, PingFang SC, sans-serif" font-size="15" fill="#334155">${escapeSvgText(line)}</text>`);
    });
  });

  svg.push(`<rect x="70" y="636" width="980" height="24" rx="12" fill="#eff6ff"/>`);
  svg.push(`<text x="560" y="653" text-anchor="middle" font-family="Microsoft YaHei, PingFang SC, sans-serif" font-size="13" fill="#64748b">如果你愿意，我还可以继续把某一个环节单独展开成更细的流程图。</text>`);
  svg.push(`</svg>`);

  return `data:image/svg+xml;charset=utf-8,${encodeURIComponent(svg.join(""))}`;
}

function resolvedDiagramImage(item) {
  if (item?.diagram_image) return item.diagram_image;
  if (isDiagramLikeMessage(item)) return buildFallbackDiagramImage(item.content);
  return "";
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
  if (!activeSessionId.value || !messages.value.length) return;
  try {
    await profileApi.saveConversation({ ...snapshotState(), answer_map: {}, extra_notes: [], current_index: 0 });
  } catch {
    // 本地兜底
  }
}

async function loadConversationRemote(expectedToken = sessionLoadToken) {
  if (!activeSessionId.value) {
    messages.value = [];
    return;
  }
  try {
    const res = await profileApi.getConversation();
    if (expectedToken !== sessionLoadToken) return;
    if (res.code === 200 && Array.isArray(res.data?.messages) && res.data.messages.length) {
      messages.value = cleanMessages(res.data.messages);
      persistState();
    }
  } catch {
    // ignore
  }
}

async function loadSessionState(targetSessionId = "") {
  const token = ++sessionLoadToken;
  const savedId = targetSessionId || localStorage.getItem(ACTIVE_PROFILE_SESSION_KEY) || "";
  activeSessionId.value = savedId ? Number(savedId) : "";
  Object.keys(profile).forEach((key) => delete profile[key]);
  if (!restoreState()) initConversation();
  await loadConversationRemote(token);
  if (token !== sessionLoadToken) return;
  await loadAggregateProfile(token);
  if (token !== sessionLoadToken) return;
  scrollToBottom();
  focusInput();
}

async function loadSessions() {
  const res = await profileApi.sessions();
  if (res.code !== 200) return;
  sessions.value = res.data.sessions || [];
  const id = res.data.active_session_id || sessions.value[0]?.id;
  if (id) {
    activeSessionId.value = Number(id);
    setActiveProfileSessionId(id);
  } else if (!activeSessionId.value && !localStorage.getItem(ACTIVE_PROFILE_SESSION_KEY)) {
    activeSessionId.value = "";
    setActiveProfileSessionId("");
  }
}

async function loadAggregateProfile(expectedToken = sessionLoadToken) {
  try {
    const res = await profileApi.getAggregate();
    if (expectedToken !== sessionLoadToken) return;
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
  if (!id || id === activeSessionId.value || sending.value) return;
  const res = await profileApi.activateSession(id);
  if (res.code !== 200) return;
  activeSessionId.value = Number(id);
  setActiveProfileSessionId(id);
  await loadSessionState(String(id));
}

async function reloadFromActiveSession() {
  await loadSessionState();
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

async function syncProfileInBackground(payloadMessages, targetSessionId) {
  const token = ++profileSyncToken;
  profileSyncing.value = true;
  try {
    const res = await profileApi.chatProfileSync({
      messages: payloadMessages,
      current_profile: { ...profile },
      profile_session_id: targetSessionId || activeSessionId.value || "",
    });
    if (res.code !== 200) return;

    if (targetSessionId && Number(activeSessionId.value) !== Number(targetSessionId)) {
      return;
    }

    Object.keys(profile).forEach((key) => delete profile[key]);
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

    persistState();
    await saveConversationRemote();
    await loadSessions();
    window.dispatchEvent(new CustomEvent("a3-profile-session-refresh"));
  } catch {
    // 静默失败，不打断主对话
  } finally {
    if (token === profileSyncToken) {
      profileSyncing.value = false;
    }
  }
}

async function syncEnhancementInBackground(payloadMessages, assistantReply, assistantIndex, options = {}) {
  const targetSessionId = Number(options.profile_session_id || activeSessionId.value || 0);
  const needDiagram = Boolean(options.need_diagram);
  const needQuiz = Boolean(options.need_quiz);

  if ((!needDiagram && !needQuiz) || !assistantReply) {
    return;
  }

  try {
    const res = await profileApi.chatEnhance({
      messages: payloadMessages,
      current_profile: { ...profile },
      assistant_reply: assistantReply,
      need_diagram: needDiagram,
      need_quiz: needQuiz,
      profile_session_id: targetSessionId || "",
    });
    if (res.code !== 200) return;
    if (targetSessionId && Number(activeSessionId.value) !== Number(targetSessionId)) return;

    const targetMessage = messages.value[assistantIndex];
    if (!targetMessage || targetMessage.role !== "assistant") return;

    targetMessage.diagram_image = res.data.diagram_image || "";
    targetMessage.quiz_items = Array.isArray(res.data.quiz_items) ? res.data.quiz_items : [];
    targetMessage.enhancement_pending = false;

    persistState();
    await saveConversationRemote();
  } catch {
    const targetMessage = messages.value[assistantIndex];
    if (targetMessage?.role === "assistant") {
      targetMessage.enhancement_pending = false;
      persistState();
    }
  }
}

async function sendMessage() {
  const text = normalizeText(draft.value);
  if (!text) {
    ElMessage.warning("请输入当前回答");
    return;
  }
  if (sending.value) return;

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

    if (res.data.profile_session_id) {
      activeSessionId.value = Number(res.data.profile_session_id);
      setActiveProfileSessionId(res.data.profile_session_id);
    }
    const assistantReply = (res.data.assistant_reply || res.data.next_question || "我已经记录了这条信息，并在后台更新学习画像。").trim();
    const assistantIndex = pushAssistant({
      content: assistantReply,
      diagram_image: res.data.diagram_image,
      quiz_items: res.data.quiz_items,
      sources: res.data.sources,
      need_diagram: res.data.need_diagram,
      need_quiz: res.data.need_quiz,
      enhancement_pending: Boolean(res.data.need_diagram || res.data.need_quiz),
    });
    messages.value = cleanMessages(messages.value);
    persistState();
    await saveConversationRemote();
    await loadSessions();
    window.dispatchEvent(new CustomEvent("a3-profile-session-refresh"));
    const syncSessionId = Number(res.data.profile_session_id || activeSessionId.value || 0);
    const syncedMessages = messages.value.map((item) => ({ role: item.role, content: item.content }));
    syncEnhancementInBackground(payloadMessages, assistantReply, assistantIndex, {
      profile_session_id: syncSessionId,
      need_diagram: res.data.need_diagram,
      need_quiz: res.data.need_quiz,
    });
    syncProfileInBackground(syncedMessages, syncSessionId);
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
  await loadSessionState();
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
  await loadSessionState();
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
  padding: 10px 14px;
  border: 1px solid #e6e7eb;
  border-radius: 999px;
  background: #ffffff;
  box-shadow: 0 2px 12px rgba(15, 23, 42, 0.05);
}

.home-composer :deep(.el-textarea__inner),
.composer-card :deep(.el-textarea__inner) {
  padding: 0;
  border: none;
  box-shadow: none;
  background: transparent;
  color: #111827;
  font-size: 16px;
  line-height: 1.7;
  min-height: 28px !important;
}

.home-composer :deep(.el-textarea__inner::placeholder),
.composer-card :deep(.el-textarea__inner::placeholder) {
  color: #9ca3af;
}

.home-composer :deep(.el-textarea__wrapper),
.composer-card :deep(.el-textarea__wrapper) {
  box-shadow: none !important;
  padding: 0 !important;
  background: transparent !important;
}

.composer-shell {
  overflow: hidden;
}

.composer-main {
  display: flex;
  align-items: center;
  gap: 14px;
  min-height: 44px;
}

.composer-main :deep(.el-textarea) {
  flex: 1;
}

.composer-tools {
  display: flex;
  align-items: center;
  gap: 10px;
  flex: 0 0 auto;
}

.composer-icon-button,
.composer-send-button,
.composer-text-button {
  border: none;
  background: transparent;
  padding: 0;
  cursor: pointer;
}

.composer-icon-button {
  width: 34px;
  height: 34px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: 999px;
  color: #111827;
  transition: background 0.18s ease, color 0.18s ease;
}

.composer-icon-button.ghost:hover {
  background: #f3f4f6;
}

.composer-icon-button :deep(svg) {
  width: 18px;
  height: 18px;
}

.composer-text-button {
  display: inline-flex;
  align-items: center;
  color: #737373;
  font-size: 15px;
  font-weight: 500;
}

.composer-text-button::after {
  content: "⌄";
  margin-left: 6px;
  font-size: 13px;
  color: #9ca3af;
}

.composer-send-button {
  width: 42px;
  height: 42px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: 999px;
  background: #111111;
  color: #ffffff;
  box-shadow: 0 2px 10px rgba(17, 17, 17, 0.18);
  transition: transform 0.18s ease, opacity 0.18s ease;
}

.composer-send-button:hover:not(:disabled) {
  transform: translateY(-1px);
}

.composer-send-button:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}

.composer-send-button :deep(svg) {
  width: 17px;
  height: 17px;
}

.send-stop-dot {
  width: 12px;
  height: 12px;
  border-radius: 3px;
  background: #ffffff;
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
  width: 100%;
  max-width: 1040px;
  margin: 0 auto 24px;
  padding: 0 24px;
}

.message-row.user {
  justify-content: flex-end;
}

.message-bubble {
  max-width: min(780px, 78%);
  padding: 0;
  border-radius: 0;
  box-shadow: none;
}

.message-bubble.assistant {
  padding: 16px 18px 18px;
  border-radius: 28px;
  border: 1px solid #e6ddff;
  background: linear-gradient(180deg, #faf7ff 0%, #f5f0ff 100%);
  box-shadow: 0 12px 28px rgba(124, 58, 237, 0.08);
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
  gap: 8px;
  margin-bottom: 8px;
  color: #6b7280;
  font-size: 12px;
}

.message-bubble.user .message-meta {
  margin-bottom: 6px;
}

.message-meta small {
  color: #94a3b8;
  font-size: 11px;
  line-height: 1;
}

.message-content {
  color: inherit;
  white-space: normal;
  word-break: break-word;
  line-height: 1.72;
  font-size: 17px;
}

.message-content:deep(p) {
  margin: 0 0 2px;
}

.message-content:deep(ul),
.message-content:deep(ol) {
  margin: 4px 0 4px 18px;
  padding: 0;
}

.message-content:deep(li) {
  margin: 0;
  line-height: 1.68;
}

.message-content:deep(li + li) {
  margin-top: 0;
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

.message-bubble.assistant .message-content:not(.diagram-text-card) {
  margin-top: 2px;
}


.diagram-text-card {
  position: relative;
  margin-top: 6px;
  padding: 18px 20px 18px 22px;
  border: 1px solid #dbeafe;
  border-radius: 24px;
  background: linear-gradient(180deg, #f8fbff 0%, #ffffff 100%);
  box-shadow: 0 12px 32px rgba(59, 130, 246, 0.08);
}

.diagram-text-card::before {
  content: "图解梳理";
  position: absolute;
  top: -12px;
  left: 18px;
  padding: 4px 10px;
  border: 1px solid #bfdbfe;
  border-radius: 999px;
  background: #ffffff;
  color: #2563eb;
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.02em;
  box-shadow: 0 4px 12px rgba(37, 99, 235, 0.08);
}

.diagram-text-card:deep(h1),
.diagram-text-card:deep(h2),
.diagram-text-card:deep(h3),
.diagram-text-card:deep(h4) {
  margin: 8px 0 14px;
  color: #0f172a;
  font-size: 22px;
  line-height: 1.4;
}

.diagram-text-card:deep(p) {
  margin: 0 0 12px;
}

.diagram-text-card:deep(ul),
.diagram-text-card:deep(ol) {
  margin: 12px 0 12px 22px;
}

.diagram-text-card:deep(li) {
  margin-bottom: 8px;
  line-height: 1.8;
}

.enhancement-card {
  margin-top: 16px;
  padding: 16px;
  border: 1px solid #dbeafe;
  border-radius: 20px;
  background: linear-gradient(180deg, #f8fbff 0%, #fdfefe 100%);
  box-shadow: 0 10px 28px rgba(37, 99, 235, 0.08);
}

.enhancement-pending {
  margin-top: 12px;
  display: inline-flex;
  align-items: center;
  padding: 6px 12px;
  border-radius: 999px;
  background: rgba(124, 58, 237, 0.08);
  color: #7c3aed;
  font-size: 12px;
  font-weight: 600;
}

.enhancement-title {
  margin-bottom: 12px;
  color: #1d4ed8;
  font-size: 13px;
  font-weight: 700;
  letter-spacing: 0.02em;
}

.diagram-image {
  display: block;
  width: 100%;
  max-width: 860px;
  margin: 0 auto;
  border-radius: 16px;
  background: #ffffff;
  box-shadow: 0 8px 24px rgba(15, 23, 42, 0.08);
}

.quiz-card {
  background: #fafafa;
  border-color: #ececec;
}

.quiz-item + .quiz-item {
  margin-top: 12px;
  padding-top: 12px;
  border-top: 1px dashed #dbe2ea;
}

.quiz-item strong {
  display: block;
  color: #111827;
  font-size: 14px;
  line-height: 1.7;
}

.quiz-item p {
  margin: 6px 0 0;
  color: #6b7280;
  font-size: 13px;
  line-height: 1.6;
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
  width: min(1040px, calc(100% - 64px));
  padding: 10px 14px;
  border: 1px solid #e6e7eb;
  border-radius: 999px;
  background: #ffffff;
  box-shadow: 0 2px 14px rgba(15, 23, 42, 0.06);
  z-index: 5;
}

.composer-card :deep(.el-textarea__inner) {
  font-size: 15px;
  line-height: 1.7;
}

.composer-status {
  display: flex;
  align-items: center;
  gap: 8px;
  color: #737373;
  font-size: 15px;
  font-weight: 500;
}

.stage-actions {
  position: absolute;
  right: 32px;
  bottom: 102px;
  z-index: 4;
}

.stage-actions :deep(.el-button) {
  height: 36px;
  padding: 0 16px;
  border-radius: 999px;
  border-color: #e5e7eb;
  color: #4b5563;
  background: rgba(255, 255, 255, 0.96);
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
  .summary-strip {
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

  .stage-actions {
    right: 12px;
    bottom: 88px;
  }

  .composer-main {
    gap: 10px;
  }
}
</style>
