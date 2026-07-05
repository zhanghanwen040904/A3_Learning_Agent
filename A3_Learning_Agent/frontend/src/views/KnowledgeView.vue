<template>
  <div class="page knowledge-page">
    <el-card class="panel knowledge-status-panel">
      <template #header>
        <div class="panel-head">
          <div>
            <h2>课程知识库管理</h2>
            <p>导入教材 JSON，浏览章节内容，并测试知识库检索。</p>
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
          placeholder="教材 JSON 路径，例如 rag_data/pdf_json/软件工程导论_第6版.json"
        />
        <el-upload :auto-upload="false" :show-file-list="false" accept=".json,application/json" @change="handleFileChange">
          <el-button>选择 JSON 文件</el-button>
        </el-upload>
        <el-button type="primary" :loading="importing" @click="importKnowledge">导入 JSON</el-button>
      </div>
    </el-card>

    <el-card class="panel">
      <template #header><strong>课程文档集</strong></template>
      <el-table v-if="documents.length" :data="documents" stripe>
        <el-table-column prop="file_name" label="文件名" min-width="220" show-overflow-tooltip />
        <el-table-column prop="course" label="课程" min-width="120" />
        <el-table-column prop="type" label="类型" width="80" />
        <el-table-column prop="section_count" label="章节数" width="90" />
        <el-table-column prop="chunk_count" label="检索片段数" width="110" />
        <el-table-column prop="status" label="状态" width="100" />
        <el-table-column prop="created_at" label="导入时间" min-width="170" />
      </el-table>
      <el-empty v-else description="No Data" />
    </el-card>

    <div class="knowledge-browser">
      <el-card class="panel tree-panel">
        <template #header><strong>教材章节目录</strong></template>
        <el-scrollbar height="640px" v-loading="treeLoading">
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
          <el-empty v-else description="暂无章节目录，请先导入教材 JSON" />
        </el-scrollbar>
      </el-card>

      <el-card class="panel content-panel">
        <template #header>
          <div class="panel-head small">
            <div>
              <strong>{{ sectionDetail.title || "章节正文" }}</strong>
            </div>
          </div>
        </template>

        <el-scrollbar height="640px" v-loading="sectionLoading">
          <template v-if="hasSectionContent">
            <article v-for="section in sectionDetail.sections" :key="section.node_id" class="section-block">
              <div v-if="section.paragraphs?.length" class="paragraph-list">
                <div
                  v-for="(paragraph, index) in section.paragraphs"
                  :key="`${section.node_id}-${index}`"
                  class="paragraph-item"
                >
                  <p>{{ paragraph.text }}</p>
                </div>
              </div>
            </article>
          </template>
          <el-empty
            v-else-if="activeNodeId && !sectionLoading"
            description="该章节暂无正文内容"
          />
          <el-empty v-else description="请在左侧选择章节查看正文" />
        </el-scrollbar>
      </el-card>
    </div>

    <el-card class="panel">
      <template #header><strong>知识库检索测试</strong></template>
      <div class="search-bar">
        <el-input
          v-model="searchQuery"
          placeholder="输入问题，例如：软件危机产生的原因是什么？"
          @keyup.enter="runSearch"
        />
        <el-button type="primary" :loading="searching" @click="runSearch">检索</el-button>
      </div>

      <div v-if="searchResults.length" class="search-result-list">
        <article v-for="(item, index) in searchResults" :key="`${item.section_title}-${index}`" class="result-card">
          <div class="result-score">【{{ item.score }}】{{ item.section_title }}</div>
          <div class="result-meta">路径：{{ item.path || "N/A" }}</div>
          <div class="result-meta">页码：{{ item.page || "N/A" }}</div>
          <p>{{ item.content }}</p>
        </article>
      </div>
      <el-empty v-else-if="searchTouched && !searching" :description="searchEmptyText" />
    </el-card>
  </div>
</template>

<script setup>
import { computed, nextTick, onMounted, ref } from "vue";
import { ElMessage } from "element-plus";
import { knowledgeApi } from "../api";

const refreshing = ref(false);
const rebuilding = ref(false);
const importing = ref(false);
const searching = ref(false);
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
const documents = ref([]);
const chapterTree = ref([]);
const activeNodeId = ref("");
const sectionDetail = ref({ sections: [] });
const searchResults = ref([]);
const searchTouched = ref(false);
const searchEmptyText = ref("未检索到相关内容");

const importJsonPath = ref("");
const selectedFile = ref(null);
const searchQuery = ref("");
const treeRef = ref(null);
const defaultExpandedKeys = ref([]);

const hasSectionContent = computed(() =>
  (sectionDetail.value.sections || []).some((section) => (section.paragraphs || []).length > 0)
);

function unwrap(response) {
  if (response?.code === 200 || response?.success === true) return response.data;
  throw new Error(response?.msg || response?.message || "请求失败");
}

function findDefaultNode(nodes) {
  for (const node of nodes || []) {
    if (Number(node.level) === 1) return node;
    const child = findDefaultNode(node.children || []);
    if (child) return child;
  }
  return (nodes || [])[0] || null;
}

function collectExpandedKeys(node, keys = []) {
  if (!node) return keys;
  keys.push(node.node_id);
  for (const child of node.children || []) {
    if (Number(child.level) <= 1) collectExpandedKeys(child, keys);
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

async function loadDocuments() {
  documents.value = unwrap(await knowledgeApi.documents());
}

async function loadTree(selectDefault = false) {
  treeLoading.value = true;
  try {
    chapterTree.value = unwrap(await knowledgeApi.tree());
    if (selectDefault && chapterTree.value.length) {
      const node = findDefaultNode(chapterTree.value);
      if (node) {
        activeNodeId.value = node.node_id;
        defaultExpandedKeys.value = collectExpandedKeys(chapterTree.value[0], []);
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
    sectionDetail.value = unwrap(await knowledgeApi.section(nodeId, { include_children: false }));
  } catch (error) {
    sectionDetail.value = { sections: [] };
    ElMessage.error(error.message || "章节内容加载失败");
  } finally {
    sectionLoading.value = false;
  }
}

async function refreshAll() {
  refreshing.value = true;
  try {
    await Promise.all([loadStatus(), loadDocuments(), loadTree(!activeNodeId.value)]);
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

async function runSearch() {
  if (!searchQuery.value.trim()) {
    ElMessage.warning("请输入检索内容");
    return;
  }
  searching.value = true;
  searchTouched.value = true;
  try {
    const response = await knowledgeApi.search({ query: searchQuery.value.trim(), top_k: 5 });
    if (response?.code === 200 || response?.success === true) {
      searchResults.value = Array.isArray(response.data) ? response.data : [];
      searchEmptyText.value = response.message || response.msg || "未检索到相关内容";
      if (!searchResults.value.length) {
        ElMessage.info(searchEmptyText.value);
      }
    } else {
      searchResults.value = [];
      throw new Error(response?.msg || response?.message || "检索失败");
    }
  } catch (error) {
    searchResults.value = [];
    ElMessage.error(error.message || "检索失败");
  } finally {
    searching.value = false;
  }
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
  max-width: 100%;
  overflow-x: hidden;
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
  flex-shrink: 0;
}

.status-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
  gap: 12px;
  margin-bottom: 12px;
}

.status-card,
.result-card,
.section-block,
.import-bar,
.search-bar {
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

.import-bar,
.search-bar {
  margin-top: 14px;
  padding: 12px;
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
}

.import-bar .el-input,
.search-bar .el-input {
  flex: 1;
  min-width: 220px;
}

.knowledge-browser {
  display: grid;
  grid-template-columns: 320px minmax(0, 1fr);
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

.section-title {
  margin: 0 0 8px;
  word-break: break-word;
}

.section-meta,
.result-meta {
  color: #6b7280;
  font-size: 13px;
  margin: 0 0 10px;
  display: flex;
  gap: 16px;
  flex-wrap: wrap;
}

.paragraph-list {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.page-label {
  display: none;
}

.paragraph-item p {
  margin: 0;
  line-height: 1.9;
  white-space: pre-wrap;
  word-break: break-word;
  text-align: justify;
  font-size: 15px;
}

.search-result-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
  margin-top: 14px;
}

.result-card {
  padding: 14px;
}

.result-score {
  font-weight: 700;
  margin-bottom: 8px;
}

.result-card p {
  margin: 0;
  line-height: 1.7;
  word-break: break-word;
}

@media (max-width: 960px) {
  .knowledge-browser {
    grid-template-columns: 1fr;
  }
}
</style>
