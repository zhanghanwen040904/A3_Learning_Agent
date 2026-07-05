<template>
  <div class="page knowledge-page">
    <el-card class="panel">
      <template #header>
        <div class="header-line">
          <span>课程知识库管理</span>
          <div>
            <el-button :loading="loading" @click="loadStatus">刷新状态</el-button>
            <el-button type="primary" :loading="rebuilding" @click="rebuild">重建知识库</el-button>
          </div>
        </div>
      </template>

      <el-row :gutter="18">
        <el-col :span="6">
          <el-statistic title="课程文档数" :value="status.document_count || 0" />
        </el-col>
        <el-col :span="6">
          <el-statistic title="知识片段数" :value="status.chunk_count || 0" />
        </el-col>
        <el-col :span="6">
          <el-statistic title="课程名称" value="人工智能导论" />
        </el-col>
        <el-col :span="6">
          <el-statistic title="检索模式" :value="status.retrieval_mode === 'keyword' ? '关键词' : '向量'" />
        </el-col>
      </el-row>
      <el-alert
        v-if="status.last_build?.message"
        class="status-alert"
        :title="status.last_build.message"
        :description="status.last_build.warning"
        :type="status.retrieval_mode === 'keyword' ? 'warning' : 'success'"
        show-icon
        :closable="false"
      />

      <el-divider />
      <h3>课程文档集</h3>
      <el-table :data="status.documents || []" border>
        <el-table-column prop="name" label="文件名" />
        <el-table-column prop="suffix" label="类型" width="100" />
        <el-table-column prop="size" label="大小" width="120" />
      </el-table>
    </el-card>

    <el-card class="panel">
      <template #header>知识库检索测试</template>
      <div class="search-line">
        <el-input v-model="query" placeholder="输入知识点，例如：监督学习和无监督学习有什么区别" />
        <el-button type="primary" :loading="searching" @click="search">检索</el-button>
      </div>
      <el-card v-for="(item, index) in results" :key="index" class="source-card" shadow="never">
        <template #header>
          <div class="header-line">
            <span>{{ item.source }}｜片段 {{ item.chunk_index }}</span>
            <el-tag>课程依据</el-tag>
          </div>
        </template>
        <p>{{ item.content }}</p>
      </el-card>
    </el-card>
  </div>
</template>

<script setup>
import { onMounted, reactive, ref } from "vue";
import { ElMessage } from "element-plus";
import { knowledgeApi } from "../api";

const status = reactive({ documents: [] });
const query = ref("监督学习和无监督学习有什么区别？");
const results = ref([]);
const loading = ref(false);
const rebuilding = ref(false);
const searching = ref(false);

async function loadStatus() {
  loading.value = true;
  try {
    const res = await knowledgeApi.status();
    if (res.code === 200) Object.assign(status, res.data);
  } finally {
    loading.value = false;
  }
}

async function rebuild() {
  rebuilding.value = true;
  try {
    const res = await knowledgeApi.rebuild({ force: true });
    if (res.code === 200) {
      const mode = res.data.retrieval_mode === "keyword" ? "关键词降级检索" : "向量检索";
      ElMessage.success(`${res.data.message || "知识库重建完成"}（${mode}）`);
      await loadStatus();
    } else {
      ElMessage.error(res.msg);
    }
  } finally {
    rebuilding.value = false;
  }
}

async function search() {
  searching.value = true;
  try {
    const res = await knowledgeApi.search({ query: query.value, top_k: 5 });
    if (res.code === 200) results.value = res.data.items || [];
  } finally {
    searching.value = false;
  }
}

onMounted(loadStatus);
</script>

<style scoped>
.knowledge-page {
  display: grid;
  gap: 18px;
}
.header-line,
.search-line {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}
.status-alert {
  margin-top: 18px;
}
.source-card {
  margin-top: 14px;
}
.source-card p {
  line-height: 1.8;
  color: #334155;
}
</style>
