<template>
  <div class="page evaluation-page">
    <el-card class="panel">
      <template #header>
        <div class="header-line">
          <span>学习检测与掌握度更新</span>
          <div class="header-actions">
            <el-button :loading="summaryLoading" @click="loadSummary">刷新评估</el-button>
            <el-button :loading="bankLoading" @click="rebuildBank">重建题库</el-button>
          </div>
        </div>
      </template>

      <el-row :gutter="18">
        <el-col :span="6"><el-statistic title="平均得分" :value="summary.avg_score || 0" suffix="分" /></el-col>
        <el-col :span="6"><el-statistic title="已完成题数" :value="summary.quiz_count || 0" /></el-col>
        <el-col :span="6"><el-statistic title="当前薄弱点" :value="liveWeakPoints.length" /></el-col>
        <el-col :span="6"><el-statistic title="题库题目数" :value="summary.bank_status?.question_count || 0" /></el-col>
      </el-row>

      <div class="profile-box">
        <div class="section-title">画像摘要</div>
        <el-space wrap>
          <el-tag v-if="summary.profile?.weak_points" type="danger">薄弱点：{{ summary.profile.weak_points }}</el-tag>
          <el-tag v-if="summary.profile?.study_goal" type="success">目标：{{ summary.profile.study_goal }}</el-tag>
          <el-tag v-if="summary.profile?.course_progress">进度：{{ summary.profile.course_progress }}</el-tag>
        </el-space>
      </div>
    </el-card>

    <el-card v-if="stageContext.active" class="panel stage-assessment-card">
      <div>
        <el-tag type="success">第 {{ stageContext.stageIndex + 1 }} 阶段测评</el-tag>
        <h3>{{ stageContext.title }}</h3>
        <p>本次测试围绕学习路径当前阶段知识点出题，答题结果会作为用户画像的掌握度与薄弱点反馈依据。</p>
        <el-space wrap><el-tag v-for="p in stageContext.points" :key="p" type="info">{{ p }}</el-tag></el-space>
      </div>
      <el-button v-if="stageContext.fromPath" @click="router.push('/path')">返回学习路径</el-button>
    </el-card>

    <el-card class="panel">
      <template #header>按画像生成检测题</template>

      <div class="generator-grid">
        <el-form label-position="top" class="generator-form">
          <el-form-item label="出题模式">
            <el-radio-group v-model="generator.mode">
              <el-radio-button label="batch">一次展示全部</el-radio-button>
              <el-radio-button label="single">逐题作答</el-radio-button>
            </el-radio-group>
          </el-form-item>

          <el-form-item label="题目数量">
            <el-input-number v-model="generator.count" :min="3" :max="10" />
          </el-form-item>

          <el-form-item label="指定知识点（可选）">
            <el-input v-model="generator.knowledgePoint" placeholder="如：需求分析 / 总体设计 / 测试" clearable />
          </el-form-item>

          <el-button type="primary" :loading="questionLoading" @click="generateQuestions">生成检测题</el-button>
        </el-form>

        <div class="generator-info">
          <div class="section-title">推荐知识点</div>
          <el-empty v-if="!recommendedPoints.length" description="点击左侧按钮后，系统会根据画像与薄弱点推荐题目。" />
          <el-space v-else wrap>
            <el-tag v-for="item in recommendedPoints" :key="item" effect="light">{{ item }}</el-tag>
          </el-space>
        </div>
      </div>
    </el-card>

    <div v-if="questions.length" class="workspace-grid">
      <el-card class="panel main-panel">
        <template #header>
          <div class="header-line">
            <span>个性化检测题</span>
            <span class="subtle">
              {{ generator.mode === "single" ? `第 ${activeQuestionIndex + 1} / ${questions.length} 题` : `共 ${questions.length} 题` }}
            </span>
          </div>
        </template>

        <div v-if="generator.mode === 'single'">
          <div class="focus-strip">
            <el-progress :percentage="progressPercent" :stroke-width="10" />
            <div class="focus-strip-text">
              <span>已完成 {{ answeredCount }} / {{ questions.length }} 题</span>
              <span v-if="currentQuestion?.result" :class="scoreClass(currentQuestion.result.score)">
                本题得分：{{ currentQuestion.result.score }}
              </span>
            </div>
          </div>

          <div class="question-card question-card--focus">
            <div class="question-meta">
              <el-tag>{{ currentQuestion.question_type }}</el-tag>
              <el-tag type="success">{{ currentQuestion.knowledge_path }}</el-tag>
              <el-tag type="info">{{ currentQuestion.difficulty }}</el-tag>
            </div>

            <div class="question-title-line">
              <h3>{{ currentQuestion.order }}. {{ currentQuestion.prompt }}</h3>
              <el-button size="small" type="warning" plain @click="addQuestionToWrongBook(currentQuestion)">加入错题本</el-button>
            </div>

            <div v-if="currentQuestion.options?.length" class="option-list">
              <div v-for="option in currentQuestion.options" :key="option.label" class="option-item">
                <strong>{{ option.label }}.</strong> {{ option.text }}
              </div>
            </div>

            <el-input
              v-model="currentQuestion.userAnswer"
              type="textarea"
              :rows="5"
              :placeholder="currentQuestion.options?.length ? '请输入选项字母或选项内容' : '请输入你的答案'"
            />

            <div class="question-actions">
              <el-button type="primary" :loading="submitting" @click="submitQuestion(currentQuestion)">提交并判题</el-button>
              <el-button type="success" plain @click="currentQuestion.showAnswer = !currentQuestion.showAnswer">
                {{ currentQuestion.showAnswer ? '收起答案与解析' : '查看答案与解析' }}
              </el-button>
              <el-button v-if="activeQuestionIndex > 0" @click="activeQuestionIndex -= 1">上一题</el-button>
              <el-button v-if="activeQuestionIndex < questions.length - 1" @click="activeQuestionIndex += 1">下一题</el-button>
            </div>

            <div v-if="currentQuestion.showAnswer" class="answer-box">
              <div class="answer-title">知识库对应答案</div>
              <p><strong>题目：</strong>{{ currentQuestion.prompt }}</p>
              <p><strong>参考答案：</strong>{{ answerText(currentQuestion) }}</p>
              <p><strong>答案解析：</strong>{{ explanationText(currentQuestion) }}</p>
              <p v-if="answerSourceText(currentQuestion)" class="answer-source"><strong>答案来源：</strong>{{ answerSourceText(currentQuestion) }}</p>
            </div>

            <div v-if="currentQuestion.result" class="result-box">
              <el-alert
                :title="currentQuestion.result.is_correct ? '回答较好，继续保持' : '需要继续巩固'"
                :type="currentQuestion.result.is_correct ? 'success' : 'warning'"
                :closable="false"
                show-icon
              />
              <p><strong>得分：</strong><span :class="scoreClass(currentQuestion.result.score)">{{ currentQuestion.result.score }}</span></p>
              <p><strong>反馈：</strong>{{ currentQuestion.result.feedback }}</p>
              <p><strong>参考答案：</strong>{{ currentQuestion.result.reference_answer }}</p>
              <p><strong>解析：</strong>{{ currentQuestion.result.explanation }}</p>
              <p><strong>易错点：</strong>{{ currentQuestion.result.common_mistake }}</p>
              <div v-if="currentQuestion.result.scoring_points?.length">
                <strong>得分点：</strong>
                <ul class="score-list">
                  <li v-for="(point, index) in currentQuestion.result.scoring_points" :key="index">{{ point }}</li>
                </ul>
              </div>
              <p v-if="currentQuestion.result.missed_keywords?.length">
                <strong>遗漏关键点：</strong>{{ currentQuestion.result.missed_keywords.join("、") }}
              </p>
            </div>
          </div>
        </div>

        <div v-else class="question-list">
          <div v-for="question in questions" :key="question.id" class="question-card">
            <div class="question-meta">
              <el-tag>{{ question.question_type }}</el-tag>
              <el-tag type="success">{{ question.knowledge_path }}</el-tag>
              <el-tag type="info">{{ question.difficulty }}</el-tag>
              <el-tag v-if="question.result" :type="question.result.score >= 75 ? 'success' : 'warning'">
                {{ question.result.score }} 分
              </el-tag>
            </div>

            <div class="question-title-line">
              <h3>{{ question.order }}. {{ question.prompt }}</h3>
              <el-button size="small" type="warning" plain @click="addQuestionToWrongBook(question)">加入错题本</el-button>
            </div>

            <div v-if="question.options?.length" class="option-list">
              <div v-for="option in question.options" :key="option.label" class="option-item">
                <strong>{{ option.label }}.</strong> {{ option.text }}
              </div>
            </div>

            <el-input
              v-model="question.userAnswer"
              type="textarea"
              :rows="4"
              :placeholder="question.options?.length ? '请输入选项字母或选项内容' : '请输入你的答案'"
            />

            <div class="question-actions">
              <el-button type="primary" :loading="submittingId === question.id" @click="submitQuestion(question)">提交并判题</el-button>
              <el-button type="success" plain @click="question.showAnswer = !question.showAnswer">
                {{ question.showAnswer ? '收起答案与解析' : '查看答案与解析' }}
              </el-button>
            </div>

            <div v-if="question.showAnswer" class="answer-box">
              <div class="answer-title">知识库对应答案</div>
              <p><strong>题目：</strong>{{ question.prompt }}</p>
              <p><strong>参考答案：</strong>{{ answerText(question) }}</p>
              <p><strong>答案解析：</strong>{{ explanationText(question) }}</p>
              <p v-if="answerSourceText(question)" class="answer-source"><strong>答案来源：</strong>{{ answerSourceText(question) }}</p>
            </div>

            <div v-if="question.result" class="result-box">
              <el-alert
                :title="question.result.is_correct ? '回答较好，继续保持' : '需要继续巩固'"
                :type="question.result.is_correct ? 'success' : 'warning'"
                :closable="false"
                show-icon
              />
              <p><strong>得分：</strong><span :class="scoreClass(question.result.score)">{{ question.result.score }}</span></p>
              <p><strong>反馈：</strong>{{ question.result.feedback }}</p>
              <p><strong>参考答案：</strong>{{ question.result.reference_answer }}</p>
              <p><strong>解析：</strong>{{ question.result.explanation }}</p>
              <p><strong>易错点：</strong>{{ question.result.common_mistake }}</p>
              <div v-if="question.result.scoring_points?.length">
                <strong>得分点：</strong>
                <ul class="score-list">
                  <li v-for="(point, index) in question.result.scoring_points" :key="index">{{ point }}</li>
                </ul>
              </div>
              <p v-if="question.result.missed_keywords?.length">
                <strong>遗漏关键点：</strong>{{ question.result.missed_keywords.join("、") }}
              </p>
            </div>
          </div>
        </div>
      </el-card>

      <div class="side-panel-stack">
        <el-card class="panel">
          <template #header>实时学习画像</template>

          <div class="side-section">
            <div class="mini-title">当前进度</div>
            <el-progress :percentage="progressPercent" />
          </div>

          <div class="side-section">
            <div class="mini-title">最近得分</div>
            <div v-if="recentScores.length" class="score-chip-list">
              <el-tag
                v-for="(item, index) in recentScores"
                :key="index"
                :type="item >= 85 ? 'success' : item >= 70 ? 'primary' : 'danger'"
              >
                {{ item }} 分
              </el-tag>
            </div>
            <el-empty v-else description="提交题目后会在这里显示最近得分" />
          </div>

          <div class="side-section">
            <div class="mini-title">当前薄弱知识点</div>
            <div v-if="liveWeakPoints.length" class="weak-list">
              <div v-for="item in liveWeakPoints" :key="item.name" class="weak-item">
                <div class="weak-name">{{ item.name }}</div>
                <el-progress :percentage="item.score" :status="item.score < 60 ? 'exception' : undefined" />
              </div>
            </div>
            <el-empty v-else description="当前没有明显薄弱点" />
          </div>
        </el-card>

        <el-card class="panel">
          <template #header>下一步学习任务</template>
          <el-timeline>
            <el-timeline-item v-for="(item, index) in summary.next_tasks || []" :key="index">
              {{ item }}
            </el-timeline-item>
          </el-timeline>
        </el-card>
      </div>
    </div>

    <el-row :gutter="18">
      <el-col :span="24">
        <el-card class="panel">
          <template #header>知识点掌握度</template>
          <el-table :data="summary.mastery || []" border>
            <el-table-column prop="knowledge_point" label="知识点" min-width="180" />
            <el-table-column prop="mastery_score" label="掌握度" width="150">
              <template #default="scope">
                <el-progress :percentage="Number(scope.row.mastery_score || 0)" />
              </template>
            </el-table-column>
            <el-table-column prop="weak_reason" label="薄弱原因/建议" min-width="220" />
          </el-table>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from "vue";
import { useRoute, useRouter } from "vue-router";
import { ElMessage } from "element-plus";
import { evaluationApi } from "../api";

const route = useRoute();
const router = useRouter();

const summary = reactive({
  avg_score: 0,
  quiz_count: 0,
  mastery: [],
  weak_points: [],
  next_tasks: [],
  profile: {},
  bank_status: {},
});

const summaryLoading = ref(false);
const bankLoading = ref(false);
const questionLoading = ref(false);
const submitting = ref(false);
const submittingId = ref("");
const activeQuestionIndex = ref(0);
const questions = ref([]);
const recommendedPoints = ref([]);
const recentScores = ref([]);
const stageContext = computed(() => ({
  active: route.query.stage !== undefined,
  fromPath: route.query.from === "path",
  stageIndex: Number(route.query.stage || 0),
  title: String(route.query.title || "阶段测评"),
  points: String(route.query.points || "").split(/[、,，]/).filter(Boolean),
}));

const generator = reactive({
  mode: "single",
  count: 5,
  knowledgePoint: "",
});

const currentQuestion = computed(() => questions.value[activeQuestionIndex.value] || {});
const answeredCount = computed(() => questions.value.filter((item) => item.result).length);
const progressPercent = computed(() => {
  if (!questions.value.length) return 0;
  return Math.round((answeredCount.value / questions.value.length) * 100);
});

const liveWeakPoints = computed(() => {
  const mastery = (summary.mastery || []).map((item) => ({
    name: item.knowledge_point,
    score: Number(item.mastery_score || 0),
  }));
  return mastery
    .filter((item) => item.score < 75)
    .sort((a, b) => a.score - b.score)
    .slice(0, 5);
});

function scoreClass(score) {
  const value = Number(score || 0);
  if (value >= 85) return "score-good";
  if (value >= 70) return "score-mid";
  return "score-low";
}

function answerText(question) {
  return question?.reference_answer || question?.answer || question?.result?.reference_answer || "暂无标准答案";
}

function explanationText(question) {
  return question?.analysis || question?.explanation || question?.result?.explanation || "暂无解析";
}

function answerSourceText(question) {
  const links = Array.isArray(question?.answer_links) ? question.answer_links : [];
  const first = links[0] || {};
  const pages = first.answer_pages || question?.pages || [];
  const pageText = Array.isArray(pages) && pages.length ? `答案页：${pages.join("、")}` : "";
  const method = question?.answer_link_method || first.match_method || "";
  const confidence = question?.answer_link_confidence || first.match_confidence || "";
  return [pageText, method ? `匹配方式：${method}` : "", confidence ? `置信度：${confidence}` : ""].filter(Boolean).join("；");
}

function saveStageRecordIfFinished() {
  if (!stageContext.value.active || !questions.value.length || answeredCount.value < questions.value.length) return;
  const scores = questions.value.map((item) => Number(item.result?.score || 0));
  const avgScore = Math.round(scores.reduce((sum, item) => sum + item, 0) / scores.length);
  const weakPoints = questions.value
    .flatMap((item) => [item.result?.common_mistake, ...(item.result?.missed_keywords || [])])
    .filter(Boolean)
    .slice(0, 5);
  const record = {
    stageIndex: stageContext.value.stageIndex,
    stageTitle: stageContext.value.title,
    points: stageContext.value.points,
    avgScore,
    weakPoints,
    completed: true,
    completedAt: new Date().toLocaleString(),
  };
  let records = [];
  try { records = JSON.parse(localStorage.getItem("a3_stage_assessment_records") || "[]"); } catch { records = []; }
  records = [record, ...records.filter((item) => Number(item.stageIndex) !== record.stageIndex)].slice(0, 20);
  localStorage.setItem("a3_stage_assessment_records", JSON.stringify(records));
  ElMessage.success("阶段测评记录已同步到学习路径");
}

async function loadSummary() {
  summaryLoading.value = true;
  try {
    const res = await evaluationApi.summary();
    if (res.code === 200) {
      Object.assign(summary, res.data || {});
    } else {
      ElMessage.error(res.msg || "评估数据加载失败");
    }
  } finally {
    summaryLoading.value = false;
  }
}

async function rebuildBank() {
  bankLoading.value = true;
  try {
    const res = await evaluationApi.rebuildBank({ force: true });
    if (res.code === 200) {
      ElMessage.success("知识点与题库已重建");
      await loadSummary();
      await generateQuestions();
    } else {
      ElMessage.error(res.msg || "题库重建失败");
    }
  } finally {
    bankLoading.value = false;
  }
}

async function generateQuestions() {
  questionLoading.value = true;
  try {
    const res = await evaluationApi.questions({
      count: generator.count,
      knowledge_point: generator.knowledgePoint,
      knowledge_points: stageContext.value.active ? stageContext.value.points : [],
      stage_index: stageContext.value.active ? stageContext.value.stageIndex : null,
      stage_title: stageContext.value.active ? stageContext.value.title : "",
    });
    if (res.code === 200) {
      activeQuestionIndex.value = 0;
      recentScores.value = [];
      recommendedPoints.value = res.data.recommended_knowledge_points || [];
      questions.value = (res.data.questions || []).map((item) => ({
        ...item,
        userAnswer: "",
        result: null,
        showAnswer: false,
      }));
      ElMessage.success(`已生成 ${questions.value.length} 道个性化检测题`);
    } else {
      ElMessage.error(res.msg || "检测题生成失败");
    }
  } finally {
    questionLoading.value = false;
  }
}

async function submitQuestion(question) {
  if (!question.userAnswer?.trim()) {
    ElMessage.warning("请先填写答案");
    return;
  }

  submittingId.value = question.id;
  submitting.value = true;
  try {
      const res = await evaluationApi.submit({
        question: question.prompt,
        answer: question.userAnswer,
        knowledge_point: question.knowledge_path,
        reference_answer: question.reference_answer,
        explanation: question.explanation,
        common_mistake: question.common_mistake,
        scoring_points: question.scoring_points,
        question_type: question.question_type,
        feedback_correct: question.feedback_correct,
        feedback_wrong: question.feedback_wrong,
      });
    if (res.code === 200) {
      question.result = res.data;
      recentScores.value = [res.data.score, ...recentScores.value].slice(0, 6);
      ElMessage.success(`判题完成，得到 ${res.data.score} 分`);
      await loadSummary();
      saveStageRecordIfFinished();

      if (generator.mode === "single" && activeQuestionIndex.value < questions.value.length - 1) {
        setTimeout(() => {
          activeQuestionIndex.value += 1;
        }, 500);
      }
    } else {
      ElMessage.error(res.msg || "判题失败");
    }
  } finally {
    submittingId.value = "";
    submitting.value = false;
  }
}

async function addQuestionToWrongBook(question) {
  try {
    const res = await evaluationApi.addWrongBook({
      question: question.prompt,
      question_type: question.question_type,
      options: question.options || [],
      answer: question.userAnswer || "",
      reference_answer: question.result?.reference_answer || question.reference_answer,
      explanation: question.result?.explanation || question.explanation,
      common_mistake: question.result?.common_mistake || question.common_mistake,
      scoring_points: question.result?.scoring_points || question.scoring_points || [],
      knowledge_point: question.knowledge_path,
      knowledge_path: question.knowledge_path,
      difficulty: question.difficulty,
      score: question.result?.score || 0,
      feedback: question.result?.feedback || "",
      result: question.result || {},
    });
    if (res.code === 200) {
      ElMessage.success("已加入错题本，可在左侧导航栏的错题本中查看");
    } else {
      ElMessage.error(res.msg || "加入错题本失败");
    }
  } catch (error) {
    ElMessage.error(error?.message || "加入错题本失败");
  }
}

onMounted(async () => {
  if (stageContext.value.active) {
    generator.knowledgePoint = stageContext.value.points.join('、') || stageContext.value.title;
  }
  await loadSummary();
  await generateQuestions();
});
</script>

<style scoped>
.evaluation-page {
  display: grid;
  gap: 18px;
}

.header-line {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.stage-assessment-card :deep(.el-card__body) {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 18px;
}

.stage-assessment-card h3 {
  margin: 10px 0 8px;
  color: #0f172a;
}

.stage-assessment-card p {
  margin: 0 0 10px;
  color: #475569;
  line-height: 1.7;
}

.option-list {
  margin: 12px 0;
  padding: 12px 14px;
  background: #f8fbff;
  border: 1px solid #e3eefc;
  border-radius: 10px;
  display: grid;
  gap: 8px;
}

.option-item {
  line-height: 1.7;
  color: #334155;
}

.header-actions {
  display: flex;
  gap: 10px;
}

.subtle {
  color: #909399;
  font-size: 13px;
}

.profile-box {
  margin-top: 18px;
}

.section-title {
  margin-bottom: 10px;
  font-size: 14px;
  font-weight: 600;
}

.generator-grid {
  display: grid;
  grid-template-columns: 360px 1fr;
  gap: 18px;
}

.workspace-grid {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 360px;
  gap: 18px;
}

.main-panel {
  min-width: 0;
}

.side-panel-stack {
  display: grid;
  gap: 18px;
}

.question-list {
  display: grid;
  gap: 16px;
}

.question-card {
  border: 1px solid #ebeef5;
  border-radius: 12px;
  padding: 18px;
  background: #fafcff;
}

.question-card--focus {
  background: linear-gradient(180deg, #fcfdff 0%, #f7faff 100%);
}

.question-meta {
  display: flex;
  gap: 10px;
  margin-bottom: 12px;
  flex-wrap: wrap;
}

.question-actions {
  margin-top: 14px;
  display: flex;
  gap: 12px;
  align-items: center;
  flex-wrap: wrap;
}

.question-title-line {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}

.question-title-line h3 {
  margin: 0 0 12px;
  color: #0f172a;
  line-height: 1.6;
}

.wrong-question-card {
  margin: 12px 0;
  padding: 16px;
  border: 1px solid #ebeef5;
  border-radius: 12px;
  background: #fffaf2;
}

.wrong-question-card .result-box {
  padding: 12px 14px;
  border-radius: 10px;
  background: #ffffff;
  border: 1px solid #f3e5c8;
}

.result-box,
.answer-box {
  margin-top: 16px;
  padding: 14px 16px;
  border-radius: 12px;
  display: grid;
  gap: 8px;
}

.result-box {
  background: #f8fbff;
  border: 1px solid #dbeafe;
}

.answer-box {
  background: linear-gradient(135deg, #f0fdf4, #ffffff);
  border: 1px solid #bbf7d0;
}

.answer-title {
  color: #15803d;
  font-weight: 700;
}

.answer-box p {
  margin: 0;
  color: #334155;
  line-height: 1.8;
}

.answer-source {
  color: #64748b !important;
  font-size: 13px;
}

.score-list {
  margin: 6px 0 0 18px;
  padding: 0;
}

.focus-strip {
  margin-bottom: 16px;
  padding: 12px 14px;
  border-radius: 12px;
  background: #f5f9ff;
  border: 1px solid #e4eefc;
}

.focus-strip-text {
  margin-top: 8px;
  display: flex;
  justify-content: space-between;
  color: #606266;
  font-size: 13px;
}

.side-section {
  display: grid;
  gap: 10px;
  margin-bottom: 18px;
}

.side-section:last-child {
  margin-bottom: 0;
}

.mini-title {
  font-size: 13px;
  color: #606266;
  font-weight: 600;
}

.score-chip-list {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.weak-list {
  display: grid;
  gap: 12px;
}

.weak-item {
  display: grid;
  gap: 6px;
}

.weak-name {
  font-size: 13px;
  color: #303133;
}

.score-good {
  color: #67c23a;
  font-weight: 600;
}

.score-mid {
  color: #409eff;
  font-weight: 600;
}

.score-low {
  color: #f56c6c;
  font-weight: 600;
}

@media (max-width: 1200px) {
  .workspace-grid {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 960px) {
  .generator-grid {
    grid-template-columns: 1fr;
  }

  .focus-strip-text {
    flex-direction: column;
    gap: 6px;
  }
}
</style>
