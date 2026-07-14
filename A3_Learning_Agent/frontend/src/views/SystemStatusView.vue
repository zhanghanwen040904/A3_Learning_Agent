<template>
  <div class="page system-page">
    <el-alert
      title="这里展示数据库与平台服务的当前连接状态"
      description="可用于查看数据库、文本模型、视频接口和内容审核等服务是否已正常接入。"
      type="info"
      show-icon
      :closable="false"
    />

    <el-row class="status-grid" :gutter="18">
      <el-col :span="12" class="status-col">
        <el-card class="panel status-card">
          <template #header>
            <div class="header-line status-header">
              <span>数据库连接状态</span>
              <el-button class="status-refresh" :loading="loading" @click="loadStatus">刷新</el-button>
            </div>
          </template>
          <el-descriptions class="status-descriptions" :column="1" border>
            <el-descriptions-item label="连接状态">
              <el-tag type="success">已连接</el-tag>
            </el-descriptions-item>
            <el-descriptions-item label="数据库名">{{ status.database?.name || "-" }}</el-descriptions-item>
            <el-descriptions-item label="MySQL 版本">{{ status.database?.version || "-" }}</el-descriptions-item>
            <el-descriptions-item label="主机端口">{{ status.database?.host }}:{{ status.database?.port }}</el-descriptions-item>
            <el-descriptions-item label="用户">{{ status.database?.user || "-" }}</el-descriptions-item>
          </el-descriptions>
        </el-card>
      </el-col>

      <el-col :span="12" class="status-col">
        <el-card class="panel status-card">
          <template #header>
            <div class="header-line status-header">
              <span>服务连接状态</span>
              <span class="header-placeholder" aria-hidden="true"></span>
            </div>
          </template>
          <el-descriptions class="status-descriptions" :column="1" border>
            <el-descriptions-item label="运行模式">
              <el-tag :type="status.ai?.mock_ai ? 'warning' : 'success'">{{ status.ai?.mode || "-" }}</el-tag>
            </el-descriptions-item>
            <el-descriptions-item label="文本模型">
              <el-tag :type="status.ai?.primary_model?.configured ? 'success' : 'danger'">
                {{ status.ai?.primary_model?.configured ? "已配置" : "未配置" }}
              </el-tag>
            </el-descriptions-item>
            <el-descriptions-item label="模型名称">
              {{ status.ai?.primary_model?.model || "-" }}
            </el-descriptions-item>
            <el-descriptions-item label="视频接口">
              <el-tag :type="status.ai?.video?.configured ? 'success' : 'warning'">
                {{ status.ai?.video?.configured ? "已接入" : "未接入" }}
              </el-tag>
            </el-descriptions-item>
            <el-descriptions-item label="内容审核">
              <el-tag :type="status.ai?.audit_content?.configured ? 'success' : 'warning'">
                {{ status.ai?.audit_content?.configured ? "已配置" : "本地兜底" }}
              </el-tag>
            </el-descriptions-item>
          </el-descriptions>
        </el-card>
      </el-col>
    </el-row>

    <el-card class="panel">
      <template #header>数据库表应用情况</template>
      <el-table :data="status.database?.tables || []" border>
        <el-table-column prop="name" label="表名" width="180" />
        <el-table-column prop="label" label="业务含义" width="180" />
        <el-table-column prop="count" label="数据量" width="100">
          <template #default="scope">
            <el-tag>{{ scope.row.count }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="usage" label="项目中如何应用" />
      </el-table>
    </el-card>

    <el-card class="panel">
      <template #header>
        <div class="header-line">
          <span>服务连通性测试</span>
          <el-button type="primary" :loading="testing" @click="testAi">测试当前服务</el-button>
        </div>
      </template>

      <el-input v-model="prompt" type="textarea" :rows="3" />

      <el-card v-if="aiResult" class="result-card" shadow="never">
        <el-descriptions :column="1" border>
          <el-descriptions-item label="测试模式">
            <el-tag :type="aiResult.mock_ai ? 'warning' : 'success'">{{ aiResult.mode }}</el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="内容审核是否通过">
            {{ aiResult.content_audit_passed ? "通过" : "未通过 / 未配置" }}
          </el-descriptions-item>
        </el-descriptions>
        <div class="markdown-body" v-html="renderMarkdown(aiResult.llm_result || aiResult.spark_result)"></div>
      </el-card>
    </el-card>
  </div>
</template>

<script setup>
import MarkdownIt from "markdown-it";
import { onMounted, reactive, ref } from "vue";
import { ElMessage } from "element-plus";
import { systemApi } from "../api";

const md = new MarkdownIt({ html: true, linkify: true, breaks: true });
const status = reactive({ database: {}, ai: {}, project_stage: {} });
const loading = ref(false);
const testing = ref(false);
const prompt = ref("请用一句话说明你正在连接 MultiTutor 学习系统。");
const aiResult = ref(null);

function renderMarkdown(text) {
  return md.render(String(text || ""));
}

async function loadStatus() {
  loading.value = true;
  try {
    const res = await systemApi.status();
    if (res.code === 200) {
      Object.assign(status, res.data);
    } else {
      ElMessage.error(res.msg || "系统状态查询失败");
    }
  } finally {
    loading.value = false;
  }
}

async function testAi() {
  testing.value = true;
  try {
    const res = await systemApi.testAi({ prompt: prompt.value });
    if (res.code === 200) {
      aiResult.value = res.data;
      ElMessage.success("AI 测试完成");
    } else {
      ElMessage.error(res.msg || "AI 测试失败");
    }
  } finally {
    testing.value = false;
  }
}

onMounted(loadStatus);
</script>

<style scoped>
.system-page {
  display: grid;
  gap: 18px;
}

.header-line {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.header-placeholder {
  width: 64px;
  height: 32px;
  flex: 0 0 auto;
}

.status-header {
  position: relative;
  width: 100%;
  min-height: 32px;
}

.status-refresh {
  position: absolute;
  top: 50%;
  right: 0;
  transform: translateY(-50%);
}

.status-grid {
  align-items: stretch;
}

.status-col {
  display: flex;
}

.status-card {
  display: flex;
  width: 100%;
  min-height: 286px;
  flex-direction: column;
}

.status-card :deep(.el-card__header) {
  display: flex;
  min-height: 68px;
  align-items: center;
  padding: 18px 22px;
}

.status-card :deep(.el-card__header > div) {
  width: 100%;
}

.status-card :deep(.el-card__body) {
  flex: 1;
  padding: 16px 22px 22px;
}

.status-descriptions {
  height: 100%;
}

.status-descriptions :deep(.el-descriptions__body),
.status-descriptions :deep(.el-descriptions__table) {
  height: 100%;
}

.status-descriptions :deep(.el-descriptions__label) {
  width: 40%;
  min-width: 170px;
  font-weight: 600;
}

.status-descriptions :deep(.el-descriptions__content) {
  width: 60%;
}

.result-card {
  margin-top: 16px;
}

.markdown-body {
  margin-top: 16px;
  line-height: 1.8;
}
</style>
