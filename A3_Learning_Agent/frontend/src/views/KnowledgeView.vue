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

                <div v-if="question.question_images?.length" class="exercise-image-list">
                  <figure v-for="image in question.question_images" :key="image.image_id || image.path" class="exercise-image-card">
                    <img :src="knowledgeImageUrl(image)" :alt="image.caption || image.figure_label || '题目图片'" loading="lazy" />
                    <figcaption>{{ image.caption || image.figure_label || `第 ${image.page || ""} 页题图` }}</figcaption>
                  </figure>
                </div>

                <div v-if="question.showAnswer" class="exercise-answer">
                  <p><strong>对应答案：</strong>{{ question.reference_answer || question.answer || "知识库中暂未匹配到本题答案" }}</p>
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
                  <p>{{ paragraph.text }}</p>
                  <div v-if="paragraph.images?.length" class="knowledge-image-list inline">
                    <figure v-for="image in paragraph.images" :key="image.image_id" class="knowledge-image-card">
                      <img :src="knowledgeImageUrl(image)" :alt="image.caption || image.figure_label || '知识图片'" loading="lazy" />
                      <figcaption>
                        <strong>{{ [image.figure_label, image.caption].filter(Boolean).join(" ") }}</strong>
                        <span v-if="image.image_summary">{{ image.image_summary }}</span>
                        <em v-if="image.page">第 {{ image.page }} 页</em>
                      </figcaption>
                    </figure>
                  </div>
                </div>
              </div>

              <div v-if="!section.paragraphs?.length && section.images?.length" class="knowledge-image-list">
                <figure v-for="image in section.images" :key="image.image_id" class="knowledge-image-card">
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
import { computed, nextTick, onMounted, ref } from "vue";
import { ElMessage } from "element-plus";
import { knowledgeApi } from "../api";

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

function knowledgeImageUrl(image) {
  const baseUrl = (import.meta.env.VITE_API_BASE_URL || "http://localhost:5000/api").replace(/\/$/, "");
  return `${baseUrl}/knowledge/image?path=${encodeURIComponent(image?.path || "")}`;
}

function findDefaultNode(nodes) {
  for (const node of nodes || []) {
    if (node?.node_id !== "exercise_root") return node;
    const child = findDefaultNode(node.children || []);
    if (child) return child;
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
    await Promise.all([loadStatus(), loadTree(!activeNodeId.value)]);
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
});
</script>

<style scoped>
.knowledge-page {
  display: flex;
  flex-direction: column;
  gap: 16px;
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

.exercise-image-list {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 12px;
  margin-top: 12px;
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
