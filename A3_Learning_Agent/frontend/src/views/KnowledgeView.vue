<template>
  <div class="page knowledge-page">
    <el-card class="panel knowledge-status-panel">
      <template #header>
        <div class="panel-head">
          <div>
            <h2>课程知识库管理</h2>
            <p>导入教材 JSON，浏览教材资源目录，并单独查看习题与答案。</p>
          </div>
          <div class="actions">
            <el-button :loading="refreshing" @click="refreshAll">刷新状态</el-button>
            <el-button type="primary" :loading="rebuilding" @click="rebuildKnowledge">重建知识库</el-button>
          </div>
        </div>
      </template>

      <div class="status-grid">
        <div class="status-card">
          <span>课程文档数</span>
          <strong>{{ status.document_count }}</strong>
        </div>
        <div class="status-card">
          <span>检索片段数</span>
          <strong>{{ status.chunk_count }}</strong>
        </div>
        <div class="status-card">
          <span>课程名称</span>
          <strong class="course-name">{{ status.course_name || "尚未导入" }}</strong>
        </div>
        <div class="status-card">
          <span>检索模式</span>
          <strong>{{ status.search_mode || "关键词" }}</strong>
        </div>
      </div>

      <el-alert
        :type="status.built ? 'success' : 'warning'"
        :closable="false"
        :title="status.status_text || '知识库尚未构建'"
        show-icon
      />

      <div class="import-bar">
        <el-input
          v-model="importJsonPath"
          placeholder="教材 JSON 路径，例如 rag_data/pdf_json/软件工程导论学习辅导.json"
        />
        <el-upload :auto-upload="false" :show-file-list="false" accept=".json,application/json" @change="handleFileChange">
          <el-button>选择 JSON 文件</el-button>
        </el-upload>
        <el-button type="primary" :loading="importing" @click="importKnowledge">导入 JSON</el-button>
      </div>
    </el-card>

    <el-alert
      v-if="evidenceLocation.title"
      class="evidence-location-alert"
      type="success"
      :closable="false"
      show-icon
      :title="`已定位生成证据：${evidenceLocation.title}`"
      :description="evidenceLocation.description"
    />

    <div class="knowledge-browser">
      <el-card class="panel tree-panel">
        <template #header><strong>教材资源目录</strong></template>
        <el-scrollbar height="760px" v-loading="treeLoading">
          <el-tree
            v-if="chapterTree.length"
            ref="treeRef"
            :data="chapterTree"
            node-key="node_id"
            :props="{ label: 'title', children: 'children' }"
            :highlight-current="true"
            :expand-on-click-node="false"
            :default-expanded-keys="defaultExpandedKeys"
            @node-click="handleTreeClick"
          />
          <el-empty v-else description="暂无目录，请先导入教材 JSON" />
        </el-scrollbar>
      </el-card>

      <el-card class="panel content-panel">
        <template #header>
          <div class="panel-head small">
            <strong>{{ sectionDetail.title || "章节内容" }}</strong>
          </div>
        </template>

        <el-scrollbar height="760px" v-loading="sectionLoading">
          <template v-if="isExerciseNode">
            <div v-if="exerciseQuestions.length" class="exercise-list">
              <article v-for="question in exerciseQuestions" :key="question.id" class="exercise-card">
                <div class="exercise-head">
                  <el-space wrap>
                    <el-tag type="primary">{{ exerciseQuestionLabel(question) }}</el-tag>
                    <el-tag :type="question.has_answer ? 'success' : 'warning'">{{ question.answer_status }}</el-tag>
                  </el-space>
                  <el-button size="small" type="success" plain @click="toggleExerciseAnswer(question)">
                    {{ question.showAnswer ? "收起答案" : "查看答案" }}
                  </el-button>
                </div>

                <p class="exercise-stem">{{ question.stem }}</p>
                <div v-if="questionKnowledgeTitles(question).length" class="exercise-kp-list">
                  <span class="exercise-kp-label">所属知识点</span>
                  <el-tag
                    v-for="title in questionKnowledgeTitles(question)"
                    :key="`${question.id}-${title}`"
                    size="small"
                    effect="plain"
                    class="exercise-kp-tag"
                  >
                    {{ title }}
                  </el-tag>
                </div>

                <div v-if="question.question_images?.length" class="exercise-image-list">
                  <figure v-for="image in question.question_images" :key="image.image_id || image.path" class="exercise-image-card">
                    <img :src="knowledgeImageUrl(image)" :alt="image.caption || image.figure_label || '题目图片'" loading="lazy" />
                    <figcaption>{{ image.caption || image.figure_label || `第 ${image.page || ""} 页题图` }}</figcaption>
                  </figure>
                </div>

                <div v-if="question.showAnswer" class="exercise-answer">
                  <p><strong>对应答案：</strong>{{ question.reference_answer || question.answer || "知识库中暂未匹配到本题答案" }}</p>
                  <div v-if="question.answer_images?.length" class="exercise-image-list answer-image-list">
                    <figure v-for="image in question.answer_images" :key="`answer-${image.image_id || image.path}`" class="exercise-image-card">
                      <img :src="knowledgeImageUrl(image)" :alt="image.caption || image.figure_label || '答案图片'" loading="lazy" />
                      <figcaption>{{ image.caption || image.figure_label || `第 ${image.page || ""} 页答案图` }}</figcaption>
                    </figure>
                  </div>
                  <p v-if="showExerciseAnalysis(question)"><strong>解析：</strong>{{ question.analysis || question.explanation }}</p>
                  <p v-if="exerciseAnswerSource(question)" class="exercise-source"><strong>来源：</strong>{{ exerciseAnswerSource(question) }}</p>
                </div>
              </article>
            </div>
            <el-empty v-else description="当前节点暂无习题内容" />
          </template>

          <template v-else-if="hasTextbookContent">
            <article v-for="section in sectionDetail.sections" :key="section.node_id" class="section-block">
              <div v-if="section.paragraphs?.length" class="paragraph-list">
                <div v-for="(paragraph, index) in section.paragraphs" :key="`${section.node_id}-${index}`" class="paragraph-item">
                  <div
                    v-if="paragraphHasHtml(paragraph.text)"
                    class="paragraph-rich"
                    v-html="renderParagraphHtml(paragraph.text)"
                  />
                  <p v-else>{{ paragraph.text }}</p>
                </div>
              </div>

              <div v-if="section.images?.length" class="knowledge-image-list">
                <figure v-for="image in section.images" :key="image.image_id || image.path" class="knowledge-image-card">
                  <img :src="knowledgeImageUrl(image)" :alt="image.caption || image.figure_label || '知识图片'" loading="lazy" />
                  <figcaption>
                    <strong>{{ [image.figure_label, image.caption].filter(Boolean).join(" ") }}</strong>
                    <span v-if="image.image_summary">{{ image.image_summary }}</span>
                    <em v-if="image.page">第 {{ image.page }} 页</em>
                  </figcaption>
                </figure>
              </div>
            </article>
          </template>

          <el-empty v-else-if="activeNodeId && !sectionLoading" description="当前节点暂无内容" />
          <el-empty v-else description="请在左侧选择目录节点" />
        </el-scrollbar>
      </el-card>
    </div>
  </div>
</template>

<script setup>
import { computed, nextTick, onMounted, ref, watch } from "vue";
import { useRoute } from "vue-router";
import { ElMessage } from "element-plus";
import { knowledgeApi } from "../api";

const route = useRoute();

const refreshing = ref(false);
const rebuilding = ref(false);
const importing = ref(false);
const sectionLoading = ref(false);
const treeLoading = ref(false);

const status = ref({
  course_name: "",
  document_count: 0,
  section_count: 0,
  chunk_count: 0,
  search_mode: "关键词",
  built: false,
  status_text: "知识库尚未构建",
});
const chapterTree = ref([]);
const activeNodeId = ref("");
const sectionDetail = ref({ sections: [], exercise_questions: [], content_mode: "" });

const importJsonPath = ref("");
const selectedFile = ref(null);
const treeRef = ref(null);
const defaultExpandedKeys = ref([]);
const evidenceLocation = ref({ title: "", description: "" });

const hasTextbookContent = computed(() =>
  (sectionDetail.value.sections || []).some(
    (section) => (section.paragraphs || []).length > 0 || (section.images || []).length > 0
  )
);
const exerciseQuestions = computed(() => sectionDetail.value.exercise_questions || []);
const isExerciseNode = computed(() => String(sectionDetail.value.content_mode || "").startsWith("exercise"));

function unwrap(response) {
  if (response?.code === 200 || response?.success === true) return response.data;
  throw new Error(response?.msg || response?.message || "请求失败");
}

function toggleExerciseAnswer(question) {
  question.showAnswer = !question.showAnswer;
}

function exerciseQuestionLabel(question) {
  return question?.question_no ? `第 ${question.question_no} 题` : "练习题";
}

function exerciseAnswerSource(question) {
  const pages = question.answer_pages || question.answer_links?.[0]?.answer_pages || [];
  const pageText = Array.isArray(pages) && pages.length ? `答案页：${pages.join("、")}` : "";
  const method = question.answer_link_method ? `匹配方式：${question.answer_link_method}` : "";
  return [pageText, method].filter(Boolean).join("；");
}

function showExerciseAnalysis(question) {
  const answer = String(question.reference_answer || question.answer || "").trim();
  const analysis = String(question.analysis || question.explanation || "").trim();
  return Boolean(analysis && analysis !== answer);
}

function questionKnowledgeTitles(question) {
  const values = [
    ...(Array.isArray(question?.related_knowledge_titles) ? question.related_knowledge_titles : []),
    ...(Array.isArray(question?.knowledge_points) ? question.knowledge_points : []),
    question?.knowledge_point,
  ];
  const seen = new Set();
  return values
    .map((value) => String(value || "").trim())
    .filter((value) => {
      if (!value) return false;
      const key = value.toLowerCase();
      if (seen.has(key)) return false;
      seen.add(key);
      return true;
    });
}

function paragraphHasHtml(text) {
  const value = String(text || "").trim();
  return /<(table|tr|td|th|p|div|span|img|figure|figcaption|ul|ol|li|br)\b/i.test(value);
}

function renderParagraphHtml(text) {
  const value = String(text || "").trim();
  if (!value) return "";
  return value
    .replace(/<script[\s\S]*?>[\s\S]*?<\/script>/gi, "")
    .replace(/<style[\s\S]*?>[\s\S]*?<\/style>/gi, "")
    .replace(/\sstyle="[^"]*"/gi, "")
    .replace(/\son\w+="[^"]*"/gi, "");
}

function knowledgeImageUrl(image) {
  const baseUrl = (import.meta.env.VITE_API_BASE_URL || "http://localhost:5000/api").replace(/\/$/, "");
  return `${baseUrl}/knowledge/image?path=${encodeURIComponent(image?.path || "")}`;
}

function findDefaultNode(nodes) {
  for (const node of nodes || []) {
    if (node?.node_id === "exercise_root") {
      const child = findDefaultNode(node.children || []);
      if (child) return child;
      continue;
    }
    const children = node?.children || [];
    if (children.length) {
      const child = findDefaultNode(children);
      if (child) return child;
    }
    if (node?.node_id && node.node_id !== "textbook_root") return node;
  }
  return (nodes || [])[0] || null;
}

function collectExpandedKeys(nodes, keys = []) {
  for (const node of nodes || []) {
    if (!node?.node_id) continue;
    if (Number(node.level) <= 1 || node.node_id === "exercise_root") {
      keys.push(node.node_id);
    }
    collectExpandedKeys(node.children || [], keys);
  }
  return keys;
}

function findTreeNode(nodes, matcher) {
  for (const node of nodes || []) {
    if (matcher(node)) return node;
    const child = findTreeNode(node.children || [], matcher);
    if (child) return child;
  }
  return null;
}

function normalizeEvidenceText(value) {
  return String(value || "")
    .toLowerCase()
    .replace(/[\s_\-—:：·、，。()（）\[\]【】]/g, "");
}

function evidenceRouteCandidates(evidenceTitle, result = {}) {
  const routePath = String(route.query.path || "");
  const resultPath = String(result.path || result.path_text || "");
  const pathParts = [...routePath.split(/\s*\/\s*/), ...resultPath.split(/\s*\/\s*/)]
    .map((part) => part.trim())
    .filter(Boolean)
    .reverse();
  return [route.query.section, result.section_title, ...pathParts, evidenceTitle]
    .map(normalizeEvidenceText)
    .filter((item, index, items) => item.length > 2 && items.indexOf(item) === index);
}

function expandTreeNode(nodeId) {
  let current = treeRef.value?.getNode?.(nodeId);
  while (current) {
    current.expanded = true;
    current = current.parent;
  }
}

async function selectEvidenceNode(node, evidenceTitle, result = {}) {
  if (!node?.node_id) return false;
  activeNodeId.value = node.node_id;
  await nextTick();
  expandTreeNode(node.node_id);
  treeRef.value?.setCurrentKey?.(node.node_id);
  await loadSection(node.node_id);
  evidenceLocation.value = {
    title: evidenceTitle || node.title,
    description: [result.path || node.path_text, result.page ? `第 ${result.page} 页` : "", result.chunk_index !== undefined ? `证据片段 ${result.chunk_index}` : ""].filter(Boolean).join(" · ") || "已打开对应知识库章节原文",
  };
  return true;
}

async function locateEvidenceFromRoute() {
  const evidenceTitle = String(route.query.evidence || "").trim();
  const nodeId = String(route.query.nodeId || "").trim();
  if (!evidenceTitle && !nodeId) return;

  if (nodeId) {
    const direct = findTreeNode(chapterTree.value, (node) => String(node.node_id) === nodeId);
    if (direct && await selectEvidenceNode(direct, evidenceTitle)) return;
  }

  let result = {};
  if (evidenceTitle) {
    try {
      const items = unwrap(await knowledgeApi.search({ query: evidenceTitle, top_k: 5 })) || [];
      result = items.find((item) => item.section_node_id) || items[0] || {};
    } catch {
      result = {};
    }
  }
  const resultNodeId = String(result.section_node_id || "").trim();
  const candidates = evidenceRouteCandidates(evidenceTitle, result);
  let target = resultNodeId
    ? findTreeNode(chapterTree.value, (node) => String(node.node_id) === resultNodeId)
    : null;
  // Match candidates one by one so the deepest evidence section wins over
  // generic ancestors such as the course root "软件工程".
  for (const candidate of candidates) {
    if (target) break;
    target = findTreeNode(
      chapterTree.value,
      (node) => normalizeEvidenceText(node.title) === candidate,
    );
  }
  if (!target) {
    for (const candidate of candidates) {
      if (target) break;
      target = findTreeNode(chapterTree.value, (node) => {
        const title = normalizeEvidenceText(node.title);
        return title.length > 3 && (title.includes(candidate) || candidate.includes(title));
      });
    }
  }
  if (target) {
    await selectEvidenceNode(target, evidenceTitle, result);
  } else {
    evidenceLocation.value = { title: evidenceTitle, description: "已进入知识库管理，但暂未匹配到精确章节，请通过左侧目录继续查找。" };
  }
}

async function loadStatus() {
  const data = unwrap(await knowledgeApi.status());
  status.value = data;
  if (!importJsonPath.value && data.default_json_path) {
    importJsonPath.value = data.default_json_path;
  }
}

async function loadTree(selectDefault = false) {
  treeLoading.value = true;
  try {
    chapterTree.value = unwrap(await knowledgeApi.tree());
    defaultExpandedKeys.value = collectExpandedKeys(chapterTree.value, []);
    if (selectDefault && chapterTree.value.length) {
      const node = findDefaultNode(chapterTree.value);
      if (node) {
        activeNodeId.value = node.node_id;
        await nextTick();
        treeRef.value?.setCurrentKey?.(node.node_id);
        await loadSection(node.node_id);
      }
    }
  } finally {
    treeLoading.value = false;
  }
}

async function loadSection(nodeId) {
  if (!nodeId) return;
  sectionLoading.value = true;
  try {
    sectionDetail.value = unwrap(await knowledgeApi.section(nodeId, { include_children: true }));
  } catch (error) {
    sectionDetail.value = { sections: [], exercise_questions: [], content_mode: "" };
    ElMessage.error(error.message || "章节内容加载失败");
  } finally {
    sectionLoading.value = false;
  }
}

async function refreshAll() {
  refreshing.value = true;
  try {
    const hasEvidenceRoute = Boolean(route.query.evidence || route.query.nodeId || route.query.section || route.query.path);
    await Promise.all([loadStatus(), loadTree(!activeNodeId.value && !hasEvidenceRoute)]);
    if (activeNodeId.value) {
      await nextTick();
      treeRef.value?.setCurrentKey?.(activeNodeId.value);
      await loadSection(activeNodeId.value);
    }
  } catch (error) {
    ElMessage.error(error.message || "刷新失败");
  } finally {
    refreshing.value = false;
  }
}

function handleFileChange(uploadFile) {
  selectedFile.value = uploadFile?.raw || null;
  if (selectedFile.value?.name) {
    importJsonPath.value = selectedFile.value.name;
  }
}

async function importKnowledge() {
  importing.value = true;
  try {
    let result;
    if (selectedFile.value) {
      const formData = new FormData();
      formData.append("file", selectedFile.value);
      result = unwrap(await knowledgeApi.importBookJson(formData));
    } else {
      if (!importJsonPath.value.trim()) {
        ElMessage.warning("请输入教材 JSON 路径或选择 JSON 文件");
        return;
      }
      result = unwrap(await knowledgeApi.importBookJson({ json_path: importJsonPath.value.trim() }));
    }
    ElMessage.success(`导入成功：${result.course}，章节 ${result.section_count}，片段 ${result.chunk_count}`);
    selectedFile.value = null;
    await refreshAll();
  } catch (error) {
    ElMessage.error(error.message || "导入失败");
  } finally {
    importing.value = false;
  }
}

async function rebuildKnowledge() {
  rebuilding.value = true;
  try {
    const payload = importJsonPath.value.trim() ? { json_path: importJsonPath.value.trim() } : {};
    const result = unwrap(await knowledgeApi.rebuild(payload));
    ElMessage.success(`知识库重建完成：章节 ${result.section_count}，片段 ${result.chunk_count}`);
    await refreshAll();
  } catch (error) {
    ElMessage.error(error.message || "重建失败");
  } finally {
    rebuilding.value = false;
  }
}

function handleTreeClick(node) {
  activeNodeId.value = node.node_id;
  loadSection(node.node_id);
}

onMounted(async () => {
  await refreshAll();
  await locateEvidenceFromRoute();
});

watch(
  () => [route.query.evidence, route.query.nodeId, route.query.section, route.query.path],
  () => locateEvidenceFromRoute(),
);
</script>

<style scoped>
.knowledge-page {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.evidence-location-alert {
  border: 1px solid #bbf7d0;
  background: #f0fdf4;
}

.panel-head {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 16px;
}

.panel-head.small {
  align-items: center;
}

.panel-head h2 {
  margin: 0 0 6px;
}

.panel-head p {
  margin: 0;
  color: #6b7280;
  font-size: 13px;
}

.actions {
  display: flex;
  gap: 8px;
}

.status-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
  gap: 12px;
  margin-bottom: 12px;
}

.status-card,
.section-block,
.exercise-card,
.import-bar {
  border: 1px solid #e5e7eb;
  border-radius: 12px;
  background: #fff;
}

.status-card {
  padding: 14px;
}

.status-card span {
  display: block;
  color: #6b7280;
  font-size: 13px;
  margin-bottom: 6px;
}

.status-card strong {
  font-size: 20px;
}

.status-card .course-name {
  font-size: 16px;
  line-height: 1.4;
  word-break: break-all;
}

.import-bar {
  margin-top: 14px;
  padding: 12px;
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
}

.import-bar .el-input {
  flex: 1;
  min-width: 220px;
}

.knowledge-browser {
  display: grid;
  grid-template-columns: 360px minmax(0, 1fr);
  gap: 16px;
}

.tree-panel,
.content-panel {
  min-width: 0;
}

.section-block {
  padding: 16px;
  margin-bottom: 12px;
}

.paragraph-list {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.paragraph-item p {
  margin: 0;
  line-height: 1.9;
  white-space: pre-wrap;
  word-break: break-word;
  text-align: justify;
  font-size: 15px;
}

.paragraph-rich {
  color: #0f172a;
  line-height: 1.9;
  font-size: 15px;
  word-break: break-word;
}

.paragraph-rich :deep(p) {
  margin: 0 0 12px;
  line-height: 1.9;
}

.paragraph-rich :deep(table) {
  width: 100%;
  border-collapse: collapse;
  margin: 12px 0;
  overflow: hidden;
  border-radius: 10px;
  border: 1px solid #dbe2ea;
}

.paragraph-rich :deep(td),
.paragraph-rich :deep(th) {
  border: 1px solid #dbe2ea;
  padding: 10px 12px;
  vertical-align: top;
  text-align: left;
}

.paragraph-rich :deep(img) {
  display: block;
  max-width: 100%;
  max-height: 520px;
  margin: 12px auto;
  object-fit: contain;
}

.knowledge-image-list {
  display: grid;
  gap: 16px;
  margin-top: 18px;
}

.knowledge-image-list.inline {
  margin: 16px 0 4px;
}

.knowledge-image-card {
  margin: 0;
  padding: 16px;
  border: 1px solid #dbeafe;
  border-radius: 14px;
  background: linear-gradient(135deg, #f8fbff, #ffffff);
}

.knowledge-image-card img {
  display: block;
  max-width: 100%;
  max-height: 520px;
  margin: 0 auto;
  object-fit: contain;
  border-radius: 10px;
}

.knowledge-image-card figcaption {
  display: grid;
  gap: 6px;
  margin-top: 12px;
  color: #475569;
  line-height: 1.7;
}

.knowledge-image-card figcaption em {
  color: #64748b;
  font-style: normal;
  font-size: 13px;
}

.exercise-list {
  display: grid;
  gap: 14px;
}

.exercise-card {
  padding: 16px;
  background: linear-gradient(135deg, #ffffff, #f8fbff);
}

.exercise-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.exercise-stem {
  margin: 12px 0 0;
  color: #0f172a;
  line-height: 1.9;
  white-space: pre-wrap;
  word-break: break-word;
}

.exercise-kp-list {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
  margin-top: 10px;
}

.exercise-kp-label {
  color: #64748b;
  font-size: 13px;
}

.exercise-kp-tag {
  border-radius: 999px;
}

.exercise-image-list {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 12px;
  margin-top: 12px;
}

.answer-image-list {
  margin-top: 4px;
}

.exercise-image-card {
  margin: 0;
  padding: 10px;
  border: 1px solid #dbeafe;
  border-radius: 12px;
  background: #fff;
}

.exercise-image-card img {
  display: block;
  max-width: 100%;
  max-height: 360px;
  margin: 0 auto;
  object-fit: contain;
  border-radius: 8px;
}

.exercise-image-card figcaption {
  margin-top: 8px;
  color: #64748b;
  font-size: 12px;
  text-align: center;
}

.exercise-answer {
  margin-top: 14px;
  padding: 14px 16px;
  border: 1px solid #bbf7d0;
  border-radius: 12px;
  background: linear-gradient(135deg, #f0fdf4, #ffffff);
  display: grid;
  gap: 8px;
}

.exercise-answer p {
  margin: 0;
  color: #334155;
  line-height: 1.85;
  white-space: pre-wrap;
  word-break: break-word;
}

.exercise-source {
  color: #64748b !important;
  font-size: 13px;
}

@media (max-width: 960px) {
  .knowledge-browser {
    grid-template-columns: 1fr;
  }
}
</style>
