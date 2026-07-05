<template>
  <div class="page resource-page">
    <el-card class="panel request-card">
      <template #header>
        <div class="header-line">
          <div>
            <strong>多智能体个性化资源工坊</strong>
            <p>基于学生画像、本地软件工程知识库、知识树和图片资源生成学习材料。</p>
          </div>
          <el-button type="primary" size="large" :loading="loading" @click="generate">
            启动六智能体协作
          </el-button>
        </div>
      </template>

      <el-form :model="requestForm" label-position="top" class="request-form">
        <el-form-item label="专业">
          <el-input v-model="requestForm.major" />
        </el-form-item>
        <el-form-item label="课程">
          <el-input v-model="requestForm.course" />
        </el-form-item>
        <el-form-item label="本次学习需求" class="need-field">
          <el-input
            v-model="requestForm.learning_need"
            type="textarea"
            :rows="2"
            placeholder="例如：请围绕瀑布模型生成讲解、练习题、知识导图和视频脚本，并展示相关教材图片。"
          />
        </el-form-item>
      </el-form>

      <el-alert
        v-if="loading"
        type="info"
        :closable="false"
        show-icon
        title="六个资源智能体正在并行生成，完成后会自动展示图片和知识导图。"
      />
    </el-card>

    <el-card v-if="plan.core_topic" class="panel">
      <template #header>PlannerAgent 资源规划</template>
      <el-descriptions :column="3" border>
        <el-descriptions-item label="核心主题">{{ plan.core_topic }}</el-descriptions-item>
        <el-descriptions-item label="目标水平">{{ plan.target_level }}</el-descriptions-item>
        <el-descriptions-item label="学习偏好">{{ plan.preferred_style }}</el-descriptions-item>
      </el-descriptions>
    </el-card>

    <el-card v-if="trace.length" class="panel">
      <template #header>
        <div class="header-line">
          <span>可审计的智能体协作轨迹</span>
          <el-tag>{{ traceId }}</el-tag>
        </div>
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

    <div class="cards">
      <el-card
        v-for="item in resources"
        :key="`${item.id || item.resource_type}-${item.title}`"
        shadow="hover"
        class="resource-card"
      >
        <template #header>
          <div class="resource-header">
            <div>
              <el-tag effect="dark">{{ typeLabel(item.resource_type) }}</el-tag>
              <strong>{{ item.title }}</strong>
            </div>
            <el-progress type="circle" :width="58" :stroke-width="6" :percentage="qualityScore(item)" />
          </div>
        </template>

        <el-alert class="personalization" type="success" :closable="false" show-icon>
          <template #title><strong>为什么为我这样生成</strong></template>
          {{ item.personalization || "依据当前学生画像与知识短板生成。" }}
        </el-alert>

        <div v-if="item.resource_type === 'mindmap'" class="mindmap-shell">
          <div class="mindmap-toolbar">
            <span>白蓝详细知识导图</span>
            <el-tag type="info" size="small">Mermaid</el-tag>
          </div>
          <div class="mindmap" v-html="mindmapSvgs[itemKey(item)]"></div>
        </div>

        <template v-else-if="item.resource_type === 'video'">
          <video v-if="playableVideo(item)" controls :src="videoUrl(item)" class="video"></video>
          <div class="markdown-body" v-html="renderMarkdown(item.content)"></div>
        </template>

        <div v-else class="markdown-body" v-html="renderMarkdown(item.content)"></div>

        <div v-if="resourceImages(item).length" class="image-gallery">
          <div class="image-title">知识库配图</div>
          <a
            v-for="path in resourceImages(item)"
            :key="path"
            :href="imageUrl(path)"
            target="_blank"
            class="image-card"
          >
            <img :src="imageUrl(path)" alt="知识库图片" loading="lazy" />
            <span>{{ shortImageName(path) }}</span>
          </a>
        </div>

        <el-divider />
        <div class="evidence">
          <div><strong>生成智能体：</strong>{{ agentName(item) }}</div>
          <div><strong>知识点：</strong>{{ knowledgePoints(item).join("、") || "软件工程核心知识" }}</div>
          <div class="source-row">
            <strong>课程依据：</strong>
            <el-tag v-for="source in uniqueSources(item.sources)" :key="source" size="small" type="info">
              {{ source }}
            </el-tag>
          </div>
        </div>
      </el-card>
    </div>
  </div>
</template>

<script setup>
import MarkdownIt from "markdown-it";
import mermaid from "mermaid";
import { nextTick, onMounted, reactive, ref } from "vue";
import { ElMessage } from "element-plus";
import { profileApi, resourceApi } from "../api";

const md = new MarkdownIt({ html: false, linkify: true, breaks: true });
const apiBase = import.meta.env.VITE_API_BASE_URL || "http://localhost:5000/api";
const absoluteImagePattern = /([A-Za-z]:\\[\s\S]*?\.(?:png|jpg|jpeg|webp|gif))/gi;
const relativeImagePattern = /(images\/[^\s）)\],，；;]+?\.(?:png|jpg|jpeg|webp|gif))/gi;

mermaid.initialize({
  startOnLoad: false,
  theme: "base",
  securityLevel: "strict",
  themeVariables: {
    background: "#ffffff",
    primaryColor: "#eff6ff",
    primaryTextColor: "#0f172a",
    primaryBorderColor: "#3b82f6",
    lineColor: "#60a5fa",
    secondaryColor: "#dbeafe",
    tertiaryColor: "#f8fafc",
    fontFamily: "Inter, Microsoft YaHei, PingFang SC, sans-serif",
  },
});

const loading = ref(false);
const resources = ref([]);
const trace = ref([]);
const traceId = ref("");
const plan = reactive({});
const mindmapSvgs = reactive({});
const requestForm = reactive({
  major: "软件工程",
  course: "软件工程",
  learning_need: "请围绕软件工程中的瀑布模型生成课程讲解、练习题、白蓝详细知识导图、实操案例和视频脚本，并展示相关教材图片。",
});

function itemKey(item) {
  return item.id || item.resource_type || item.title;
}

function imageUrl(path) {
  return `${apiBase}/knowledge/image?path=${encodeURIComponent(String(path || "").trim())}`;
}

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

function resourceImages(item) {
  return extractImagePaths([item.content, item.personalization, JSON.stringify(item.metadata || {})].join("\n"));
}

function shortImageName(path) {
  return String(path || "").split(/\\|\//).slice(-2).join(" / ");
}

function typeLabel(type) {
  return {
    doc: "讲解文档",
    quiz: "分层练习",
    reading: "拓展阅读",
    mindmap: "知识导图",
    code: "实操案例",
    video: "教学视频",
  }[type] || type;
}

function agentName(item) {
  if (item.agent_name) return item.agent_name;
  return {
    doc: "DocumentAgent",
    quiz: "QuizAgent",
    reading: "ReadingAgent",
    mindmap: "MindMapAgent",
    code: "CodeAgent",
    video: "VideoAgent",
  }[item.resource_type] || "ResourceAgent";
}

function eventType(status) {
  return { completed: "success", warning: "warning", failed: "danger" }[status] || "primary";
}

function qualityScore(item) {
  return Number(item.quality_score || item.quality?.total || item.metadata?.quality?.total || 0);
}

function knowledgePoints(item) {
  if (Array.isArray(item.knowledge_points)) return item.knowledge_points;
  try {
    return JSON.parse(item.knowledge_points || "[]");
  } catch {
    return [];
  }
}

function uniqueSources(sources = []) {
  return [...new Set((sources || []).map((item) => item.source || item.source_name).filter(Boolean))];
}

function videoUrl(item) {
  return item.video_url || item.metadata?.video_url || "";
}

function playableVideo(item) {
  const url = videoUrl(item);
  return /^https?:\/\//.test(url) && !url.includes("example.com") && !url.trim().startsWith("{");
}

function cleanMermaidFence(text) {
  return String(text || "")
    .replace(/^```(?:mermaid)?/i, "")
    .replace(/```$/i, "")
    .trim();
}

function normalizeDiagram(content, title = "软件工程知识导图") {
  const cleaned = cleanMermaidFence(content);
  const diagramIndex = cleaned.search(/\b(flowchart|graph|mindmap)\b/i);
  if (diagramIndex >= 0) return trimDiagram(cleaned.slice(diagramIndex).trim(), title);
  const lines = cleaned
    .split(/\r?\n/)
    .map((line) => line.replace(/^#+\s*/, "").replace(/^[-*]\s*/, "").trim())
    .filter(Boolean)
    .slice(0, 36);
  const root = sanitizeNodeText(title);
  const nodes = lines.length ? lines : ["核心概念", "流程步骤", "关键产物", "测试验证", "易错点", "实践任务"];
  const groups = [
    ["概念定位", nodes.slice(0, 6)],
    ["流程步骤", nodes.slice(6, 12)],
    ["关键产物", nodes.slice(12, 18)],
    ["测试验证", nodes.slice(18, 24)],
    ["易错实践", nodes.slice(24, 36)],
  ].filter(([, items]) => items.length);
  const output = ["flowchart LR", `  A(( ${root} ))`];
  groups.forEach(([groupName, items], groupIndex) => {
    output.push(`  subgraph G${groupIndex + 1}[${groupName}]`);
    items.forEach((item, itemIndex) => {
      const id = `G${groupIndex + 1}_${itemIndex + 1}`;
      output.push(`    ${id}[${sanitizeNodeText(item)}]`);
      if (itemIndex > 0) output.push(`    G${groupIndex + 1}_${itemIndex} --> ${id}`);
    });
    output.push("  end");
    output.push(`  A --> G${groupIndex + 1}_1`);
  });
  return output.join("\n");
}

function simplifyMindmap(source, title) {
  return trimDiagram(source, title);
}

function trimDiagram(source, title) {
  const lines = String(source || "").split(/\r?\n/).filter(Boolean);
  if (!lines.length) return `flowchart LR\n  A(( ${sanitizeNodeText(title)} ))`;
  const first = lines[0].trim().toLowerCase();
  const normalized = /^(flowchart|graph|mindmap)\b/.test(first) ? lines : ["flowchart LR", ...lines];
  return normalized.slice(0, 110).join("\n");
}

function sanitizeNodeText(text) {
  return String(text || "知识点")
    .replace(/[<>{}\[\]()`"]/g, "")
    .replace(/[:：|]/g, " ")
    .slice(0, 32);
}

async function renderMindmaps() {
  await nextTick();
  Object.keys(mindmapSvgs).forEach((key) => delete mindmapSvgs[key]);
  for (const item of resources.value.filter((entry) => entry.resource_type === "mindmap")) {
    const key = itemKey(item);
    try {
      const source = normalizeDiagram(item.content, item.title);
      const id = `mindmap-${key}-${Date.now()}`.replace(/[^a-zA-Z0-9-]/g, "");
      const { svg } = await mermaid.render(id, source);
      mindmapSvgs[key] = svg;
    } catch (error) {
      mindmapSvgs[key] = `<pre>${String(item.content || "知识导图生成失败")}</pre>`;
    }
  }
}

async function loadResources() {
  const [resourceRes, profileRes] = await Promise.all([resourceApi.list(), profileApi.get()]);
  if (resourceRes.code === 200) resources.value = resourceRes.data || [];
  if (profileRes.code === 200 && profileRes.data?.study_goal) requestForm.learning_need = profileRes.data.study_goal;
  await renderMindmaps();
}

async function generate() {
  loading.value = true;
  try {
    const res = await resourceApi.generate({ ...requestForm });
    if (res.code !== 200) {
      ElMessage.error(res.msg || "资源生成失败");
      return;
    }
    resources.value = res.data.resource_list || [];
    trace.value = res.data.trace || [];
    traceId.value = res.data.trace_id || "";
    Object.assign(plan, res.data.plan || {});
    await renderMindmaps();
    ElMessage.success(`六类资源生成完成，共记录 ${trace.value.length} 个协作事件`);
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
.request-form { display: grid; grid-template-columns: 1fr 1fr 2fr; gap: 16px; }
.need-field { grid-column: span 1; }
.cards { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 18px; }
.resource-card { min-width: 0; }
.resource-header > div:first-child { display: flex; align-items: center; gap: 10px; }
.personalization { margin-bottom: 18px; }
.markdown-body { max-height: 650px; overflow: auto; line-height: 1.75; }
.markdown-body :deep(pre) { overflow: auto; padding: 16px; border-radius: 8px; background: #0f172a; color: #e2e8f0; }
.markdown-body :deep(img) { display: block; max-width: 100%; max-height: 360px; object-fit: contain; margin: 14px auto; border-radius: 8px; border: 1px solid #dbeafe; background: #fff; }
.mindmap-shell { min-height: 620px; overflow: auto; border: 1px solid #bfdbfe; border-radius: 8px; background: #ffffff; box-shadow: inset 0 0 0 1px rgba(59, 130, 246, 0.06), 0 14px 36px rgba(30, 64, 175, 0.08); }
.mindmap-toolbar { display: flex; justify-content: space-between; align-items: center; padding: 12px 14px; border-bottom: 1px solid #dbeafe; color: #1d4ed8; font-weight: 700; background: linear-gradient(90deg, #eff6ff 0%, #ffffff 100%); }
.mindmap { min-width: 1360px; min-height: 560px; padding: 42px; display: grid; place-items: center; background-image: linear-gradient(#eff6ff 1px, transparent 1px), linear-gradient(90deg, #eff6ff 1px, transparent 1px); background-size: 28px 28px; }
.mindmap :deep(svg) { max-width: none; height: auto; filter: drop-shadow(0 10px 22px rgba(37, 99, 235, 0.14)); }
.mindmap :deep(.mindmap-node rect),
.mindmap :deep(.mindmap-node circle),
.mindmap :deep(.mindmap-node polygon),
.mindmap :deep(.node rect),
.mindmap :deep(.node circle),
.mindmap :deep(.node polygon),
.mindmap :deep(.node path) { fill: #eff6ff !important; stroke: #60a5fa !important; stroke-width: 1.5px !important; }
.mindmap :deep(.cluster rect) { fill: rgba(239, 246, 255, 0.64) !important; stroke: #bfdbfe !important; stroke-width: 1.4px !important; rx: 8px; }
.mindmap :deep(.mindmap-node text),
.mindmap :deep(text) { fill: #0f172a !important; font-family: "Microsoft YaHei", "PingFang SC", sans-serif !important; font-weight: 600; }
.mindmap :deep(path),
.mindmap :deep(line),
.mindmap :deep(.edgePath path) { stroke: #60a5fa !important; stroke-width: 1.5px !important; }
.mindmap :deep(.arrowheadPath) { fill: #60a5fa !important; stroke: #60a5fa !important; }
.video { width: 100%; max-height: 420px; border-radius: 8px; background: #0f172a; }
.image-gallery { margin-top: 16px; display: grid; grid-template-columns: repeat(auto-fill, minmax(160px, 1fr)); gap: 12px; }
.image-title { grid-column: 1 / -1; font-weight: 700; color: #1d4ed8; }
.image-card { display: grid; gap: 8px; padding: 8px; border: 1px solid #bfdbfe; border-radius: 8px; background: #fff; color: #475569; text-decoration: none; }
.image-card img { width: 100%; aspect-ratio: 4 / 3; object-fit: contain; background: #f8fafc; border-radius: 6px; }
.image-card span { font-size: 12px; word-break: break-all; }
.trace-status { margin-left: 10px; color: #64748b; font-size: 12px; text-transform: uppercase; }
.el-timeline-item p { margin: 6px 0 0; color: #475569; }
.evidence { display: grid; gap: 8px; color: #475569; font-size: 13px; }
.source-row { display: flex; flex-wrap: wrap; align-items: center; gap: 6px; }
@media (max-width: 1000px) { .cards, .request-form { grid-template-columns: 1fr; } }
</style>
