<template>
  <div class="page system-page">
    <el-alert
      title="这里用于展示项目是否真正连接了 MySQL 数据库和讯飞 AI 服务"
      description="如果 AI 模式显示为模拟演示模式，说明 backend/.env 中 MOCK_AI=true 或未配置真实讯飞密钥；如需连接真实模型，请填写讯飞密钥并重启后端。"
      type="info"
      show-icon
      :closable="false"
    />

    <el-row :gutter="18">
      <el-col :span="12">
        <el-card class="panel status-card">
          <template #header>
            <div class="header-line">
              <span>数据库连接状态</span>
              <el-button :loading="loading" @click="loadStatus">刷新</el-button>
            </div>
          </template>
          <el-descriptions :column="1" border>
            <el-descriptions-item label="连接状态">
              <el-tag type="success">已连接</el-tag>
            </el-descriptions-item>
            <el-descriptions-item label="数据库名">{{ status.database?.name || '-' }}</el-descriptions-item>
            <el-descriptions-item label="MySQL版本">{{ status.database?.version || '-' }}</el-descriptions-item>
            <el-descriptions-item label="主机端口">{{ status.database?.host }}:{{ status.database?.port }}</el-descriptions-item>
            <el-descriptions-item label="用户">{{ status.database?.user || '-' }}</el-descriptions-item>
          </el-descriptions>
        </el-card>
      </el-col>
      <el-col :span="12">
        <el-card class="panel status-card">
          <template #header>AI 模型连接状态</template>
          <el-descriptions :column="1" border>
            <el-descriptions-item label="当前模式">
              <el-tag :type="status.ai?.mock_ai ? 'warning' : 'success'">{{ status.ai?.mode || '-' }}</el-tag>
            </el-descriptions-item>
            <el-descriptions-item label="讯飞星火">
              <el-tag :type="status.ai?.spark?.configured ? 'success' : 'danger'">
                {{ status.ai?.spark?.configured ? '已配置' : '未配置' }}
              </el-tag>
            </el-descriptions-item>
            <el-descriptions-item label="Spark Domain">{{ status.ai?.spark?.domain || '-' }}</el-descriptions-item>
            <el-descriptions-item label="SeeDance">
              <el-tag :type="status.ai?.seedance?.configured ? 'success' : 'warning'">
                {{ status.ai?.seedance?.configured ? '已配置' : '未配置' }}
              </el-tag>
            </el-descriptions-item>
            <el-descriptions-item label="内容审核">
              <el-tag :type="status.ai?.content_audit?.configured ? 'success' : 'warning'">
                {{ status.ai?.content_audit?.configured ? '已配置' : '未配置' }}
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
          <span>AI 连通性测试</span>
          <el-button type="primary" :loading="testing" @click="testAi">测试星火模型</el-button>
        </div>
      </template>
      <el-input v-model="prompt" type="textarea" :rows="3" />
      <el-card v-if="aiResult" class="result-card" shadow="never">
        <el-descriptions :column="1" border>
          <el-descriptions-item label="测试模式">
            <el-tag :type="aiResult.mock_ai ? 'warning' : 'success'">{{ aiResult.mode }}</el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="内容审核是否通过">{{ aiResult.content_audit_passed ? '通过' : '未通过/未配置' }}</el-descriptions-item>
        </el-descriptions>
        <div class="markdown-body" v-html="renderMarkdown(aiResult.spark_result)"></div>
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
const status = reactive({ database: {}, ai: {} });
const loading = ref(false);
const testing = ref(false);
const prompt = ref("请用一句话说明你正在连接人工智能导论学习系统。");
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
.status-card {
  min-height: 330px;
}
.result-card {
  margin-top: 16px;
}
.markdown-body {
  margin-top: 16px;
  line-height: 1.8;
}
</style>
