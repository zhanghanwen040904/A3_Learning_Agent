<template>
  <div class="page wrong-book-page">
    <section class="wrong-book-top">
      <div class="header-line">
        <div>
          <span class="page-eyebrow">WRONG QUESTION BOOK</span>
          <strong>错题本</strong>
          <p>按章节和知识点整理学习评估中加入的错题，可重复作答并查看大模型解析。</p>
        </div>
        <el-button type="primary" :loading="wrongBookLoading" @click="loadWrongBook">刷新错题本</el-button>
      </div>
    </section>

    <el-card class="panel">
      <div class="wrong-book-content">
        <el-empty v-if="!wrongBookTree.length" description="暂无错题，请先在学习评估中点击题目右侧“加入错题本”。" />
        <el-collapse v-else v-model="activeWrongChapters" class="wrong-chapter-list">
          <el-collapse-item v-for="chapter in wrongBookTree" :key="chapter.chapter" :name="chapter.chapter">
            <template #title>{{ chapter.chapter }}（{{ chapter.count }}题）</template>
            <el-collapse v-model="activeWrongPoints" class="wrong-point-list">
              <el-collapse-item v-for="point in chapter.points" :key="`${chapter.chapter}-${point.knowledge_point}`" :name="`${chapter.chapter}-${point.knowledge_point}`">
                <template #title>{{ point.knowledge_point }}（{{ point.count }}题）</template>
                <div v-for="item in point.items" :key="item.id" class="wrong-question-card">
                  <div class="question-title-line">
                    <div>
                      <el-space wrap>
                        <el-tag>{{ item.question_type || '练习题' }}</el-tag>
                        <el-tag type="success">{{ item.knowledge_path || item.knowledge_point }}</el-tag>
                        <el-tag v-if="item.difficulty" type="info">{{ item.difficulty }}</el-tag>
                      </el-space>
                      <h3>{{ item.question }}</h3>
                    </div>
                    <el-button size="small" type="danger" plain @click="removeWrongBookItem(item)">移除</el-button>
                  </div>

                  <div v-if="item.options?.length" class="option-list">
                    <div v-for="option in item.options" :key="option.label" class="option-item">
                      <strong>{{ option.label }}.</strong> {{ option.text }}
                    </div>
                  </div>

                  <el-input v-model="item.reviewAnswer" type="textarea" :rows="4" placeholder="重新作答后提交，可再次查看解析和答案" />
                  <div class="question-actions">
                    <el-button type="primary" :loading="wrongSubmittingId === item.id" @click="submitWrongBookItem(item)">提交复做</el-button>
                    <el-tag :type="Number(item.score) >= 75 ? 'success' : 'warning'">最近 {{ item.score || 0 }} 分</el-tag>
                    <el-tag type="info">复做 {{ item.review_count || 0 }} 次</el-tag>
                  </div>

                  <div class="result-box">
                    <p><strong>参考答案：</strong>{{ item.reference_answer }}</p>
                    <p><strong>解析：</strong>{{ item.last_result?.explanation || item.explanation }}</p>
                    <p><strong>易错点：</strong>{{ item.last_result?.common_mistake || item.common_mistake }}</p>
                    <p v-if="item.last_result?.feedback"><strong>反馈：</strong>{{ item.last_result.feedback }}</p>
                    <p v-if="item.last_result?.missed_keywords?.length"><strong>遗漏关键点：</strong>{{ item.last_result.missed_keywords.join('、') }}</p>
                  </div>
                </div>
              </el-collapse-item>
            </el-collapse>
          </el-collapse-item>
        </el-collapse>
      </div>
    </el-card>
  </div>
</template>

<script setup>
import { onMounted, ref } from "vue";
import { ElMessage } from "element-plus";
import { evaluationApi } from "../api";

const wrongBookLoading = ref(false);
const wrongSubmittingId = ref("");
const wrongBookTree = ref([]);
const activeWrongChapters = ref([]);
const activeWrongPoints = ref([]);

async function loadWrongBook() {
  wrongBookLoading.value = true;
  try {
    const res = await evaluationApi.wrongBook();
    if (res.code === 200) {
      wrongBookTree.value = res.data?.tree || [];
      activeWrongChapters.value = wrongBookTree.value.map((item) => item.chapter);
      activeWrongPoints.value = wrongBookTree.value.flatMap((chapter) =>
        (chapter.points || []).map((point) => `${chapter.chapter}-${point.knowledge_point}`)
      );
    } else {
      ElMessage.error(res.msg || "错题本加载失败");
    }
  } finally {
    wrongBookLoading.value = false;
  }
}

async function submitWrongBookItem(item) {
  if (!item.reviewAnswer?.trim()) {
    ElMessage.warning("请先填写复做答案");
    return;
  }
  wrongSubmittingId.value = item.id;
  try {
    const res = await evaluationApi.submitWrongBook(item.id, { answer: item.reviewAnswer });
    if (res.code === 200) {
      item.last_result = res.data;
      item.score = res.data.score;
      item.feedback = res.data.feedback;
      item.review_count = Number(item.review_count || 0) + 1;
      ElMessage.success(`复做判题完成，得到 ${res.data.score} 分`);
    } else {
      ElMessage.error(res.msg || "复做判题失败");
    }
  } finally {
    wrongSubmittingId.value = "";
  }
}

async function removeWrongBookItem(item) {
  const res = await evaluationApi.deleteWrongBook(item.id);
  if (res.code === 200) {
    ElMessage.success("已移除错题");
    await loadWrongBook();
  } else {
    ElMessage.error(res.msg || "移除失败");
  }
}

onMounted(loadWrongBook);
</script>

<style scoped>
.wrong-book-page {
  display: grid;
  grid-template-rows: max-content minmax(0, 1fr);
  gap: 26px;
  min-height: 100vh;
  padding: 24px 16px 28px;
  box-sizing: border-box;
  background: linear-gradient(180deg, #f4f7fb 0%, #f7f9fc 100%);
  overflow-x: hidden;
}

.wrong-book-page .panel {
  display: flex;
  flex-direction: column;
  min-height: 0;
  border: 1px solid #e7ecf3;
  border-radius: 20px;
  background: #ffffff;
  box-shadow:
    0 1px 2px rgba(20, 34, 55, 0.02),
    0 8px 28px rgba(31, 47, 70, 0.035);
}

.wrong-book-page .panel :deep(.el-card__header) {
  padding: 20px 24px 16px;
  border-bottom: 1px solid #edf1f6;
}

.wrong-book-page .panel :deep(.el-card__body) {
  display: flex;
  flex: 1;
  min-height: 0;
  padding: 22px 24px 24px;
  box-sizing: border-box;
}

.wrong-book-top {
  padding: 0 0 2px;
}

.wrong-book-top strong {
  display: block;
  color: #0f172a;
  font-size: 38px;
  line-height: 1.25;
  font-weight: 800;
  letter-spacing: -0.04em;
}

.page-eyebrow {
  display: block;
  color: #4386d8;
  font-size: 12px;
  font-weight: 800;
  letter-spacing: .1em;
  text-transform: uppercase;
}

.wrong-book-content {
  display: flex;
  flex: 1;
  flex-direction: column;
  min-width: 0;
  min-height: 0;
  padding: 14px;
  border: 1px solid #e4eaf2;
  border-radius: 16px;
  background: #f8fafc;
}

.wrong-book-content :deep(.el-empty) {
  flex: 1;
  min-height: 180px;
  border: 1px solid #e5ebf4;
  border-radius: 16px;
  background: #fbfcff;
}

.header-line {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 24px;
  padding: 0 24px;
  box-sizing: border-box;
}

.header-line > div {
  display: flex;
  min-width: 0;
  flex-direction: column;
  gap: 6px;
}

.header-line p {
  max-width: 50em;
  margin: 0;
  color: #64748b;
  font-size: 16px;
  line-height: 1.7;
}

.wrong-chapter-list,
.wrong-point-list {
  display: grid;
  gap: 12px;
}

.wrong-chapter-list {
  border: 0;
  background: transparent;
}

.wrong-chapter-list :deep(.el-collapse-item),
.wrong-point-list :deep(.el-collapse-item) {
  overflow: hidden;
  border: 1px solid #e5ebf4;
  border-radius: 16px;
  background: #ffffff;
}

.wrong-chapter-list :deep(.el-collapse-item__header),
.wrong-point-list :deep(.el-collapse-item__header) {
  padding: 0 16px;
  border-bottom: 1px solid #edf1f6;
  background: #ffffff;
}

.wrong-chapter-list :deep(.el-collapse-item__wrap),
.wrong-point-list :deep(.el-collapse-item__wrap) {
  border-bottom: 0;
  background: #ffffff;
}

.wrong-chapter-list :deep(.el-collapse-item__content),
.wrong-point-list :deep(.el-collapse-item__content) {
  padding: 14px;
}

.wrong-point-list {
  border: 0;
  background: transparent;
}

.wrong-question-card {
  margin: 12px 0;
  padding: 18px;
  border: 1px solid #e4eaf2;
  border-radius: 16px;
  background: #f8fafc;
}

.question-title-line {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}

.question-title-line h3 {
  margin: 12px 0;
  color: #0f172a;
  line-height: 1.6;
}

.option-list {
  margin: 12px 0;
  padding: 12px 14px;
  background: #ffffff;
  border: 1px solid #e4eaf2;
  border-radius: 12px;
  display: grid;
  gap: 8px;
}

.option-item {
  line-height: 1.7;
  color: #334155;
}

.question-actions {
  margin-top: 14px;
  display: flex;
  gap: 12px;
  align-items: center;
  flex-wrap: wrap;
}

.result-box {
  margin-top: 16px;
  padding: 12px 14px;
  border-radius: 10px;
  background: #ffffff;
  border: 1px solid #e4eaf2;
  display: grid;
  gap: 8px;
}

.result-box p {
  margin: 0;
  line-height: 1.7;
}

@media (max-width: 640px) {
  .header-line {
    align-items: flex-start;
    flex-direction: column;
  }

  .header-line > .el-button {
    width: 100%;
  }
}
</style>
