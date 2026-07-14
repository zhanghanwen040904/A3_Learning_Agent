<template>
  <div class="architecture-page">
    <section class="hero-shell">
      <div class="hero-panel">
        <div class="hero-copy">
          <span class="eyebrow">Agent-Native Learning OS</span>
          <h1>学习协同架构</h1>
          <p class="hero-desc">
            以学习目标为入口，围绕软件工程课程场景，将学生画像、知识检索、资源生成、路径规划、答疑辅导与学习评估组织成一套可协同、可追踪、可解释的学习系统。
          </p>
          <div class="hero-actions">
            <el-button type="primary" @click="focusSection('roles')">浏览能力编组</el-button>
            <el-button @click="focusSection('workflow')">查看协同工作流</el-button>
          </div>
        </div>

        <div class="hero-brief">
          <div class="command-card">
            <strong>What would you like to learn?</strong>
            <p>
              告诉我你的学习目标，系统会结合学生画像、课程知识库、资源生成、学习路径和评估反馈，自动组织对应模块协同完成。
            </p>
            <div class="role-tags compact-tags">
              <span v-for="item in heroPoints" :key="item.title" class="tag-chip">{{ item.title }}</span>
            </div>
          </div>
        </div>
      </div>
    </section>

    <section class="overview-grid">
      <article v-for="item in overviewCards" :key="item.title" class="overview-card">
        <span class="overview-index">{{ item.index }}</span>
        <h3>{{ item.title }}</h3>
        <p>{{ item.desc }}</p>
      </article>
    </section>

    <section ref="rolesRef" class="content-panel">
      <div class="panel-head">
        <div>
          <span class="panel-kicker">Capability Groups</span>
          <h2>能力编组</h2>
          <p>围绕本项目的学习过程重新梳理功能分工，让各模块职责更清晰，页面表达也更贴近日常教学场景。</p>
        </div>
        <el-input v-model="keyword" clearable placeholder="搜索能力、职责或关键词" class="search-input" />
      </div>

      <div class="category-tabs">
        <button
          v-for="item in categories"
          :key="item"
          :class="{ active: activeCategory === item }"
          @click="activeCategory = item"
        >
          {{ item }}
          <span>{{ countByCategory(item) }}</span>
        </button>
      </div>

      <div class="role-grid">
        <article v-for="role in filteredRoles" :key="role.name" class="role-card">
          <div class="role-top">
            <div class="role-badge">{{ role.short }}</div>
            <div class="role-meta">
              <h3>{{ role.name }}</h3>
              <p>{{ role.role }}</p>
            </div>
            <span class="role-state">{{ role.state }}</span>
          </div>

          <p class="role-desc">{{ role.desc }}</p>

          <div class="role-io">
            <div>
              <small>接收内容</small>
              <span>{{ role.input }}</span>
            </div>
            <div>
              <small>产出结果</small>
              <span>{{ role.output }}</span>
            </div>
          </div>

          <div class="role-tags">
            <span v-for="tool in role.tools" :key="tool" class="tag-chip">{{ tool }}</span>
          </div>

          <div class="role-foot">
            <span>{{ role.category }}</span>
            <el-button link type="primary" @click="selectedRole = role">查看职责</el-button>
          </div>
        </article>
      </div>

      <el-empty v-if="!filteredRoles.length" description="没有找到匹配能力" />
    </section>

    <section ref="workflowRef" class="content-panel dark-panel">
      <div class="panel-head inverted">
        <div>
          <span class="panel-kicker">Execution Flow</span>
          <h2>运行链路</h2>
          <p>把一次学习任务拆成可解释、可追踪的处理阶段，突出本项目的闭环能力，而不是泛化的 agent 概念堆叠。</p>
        </div>
        <div class="trace-pill">全链路可回看</div>
      </div>

      <div class="flow-grid">
        <article v-for="item in workflows" :key="item.step" class="flow-card">
          <span class="flow-step">{{ item.step }}</span>
          <h3>{{ item.title }}</h3>
          <p>{{ item.desc }}</p>
          <div class="role-tags">
            <span v-for="tag in item.tags" :key="tag" class="tag-chip dark">{{ tag }}</span>
          </div>
        </article>
      </div>
    </section>

    <section class="content-panel map-panel">
      <div class="panel-head">
        <div>
          <span class="panel-kicker">Project Mapping</span>
          <h2>项目落地对应关系</h2>
          <p>把页面能力和项目目标一一对应，方便展示“为什么需要这套架构”。</p>
        </div>
      </div>

      <div class="map-list">
        <article v-for="item in projectMappings" :key="item.title" class="map-item">
          <div class="map-line"></div>
          <div class="map-dot"></div>
          <div class="map-body">
            <h3>{{ item.title }}</h3>
            <p>{{ item.desc }}</p>
            <div class="role-tags">
              <span v-for="tag in item.tags" :key="tag" class="tag-chip green">{{ tag }}</span>
            </div>
          </div>
        </article>
      </div>
    </section>

    <el-dialog v-model="showDialog" width="720px" destroy-on-close>
      <template #header>
        <div v-if="selectedRole" class="dialog-head">
          <div class="role-badge large">{{ selectedRole.short }}</div>
          <div>
            <h3>{{ selectedRole.name }}</h3>
            <p>{{ selectedRole.role }}</p>
          </div>
        </div>
      </template>

      <template v-if="selectedRole">
        <p class="dialog-desc">{{ selectedRole.desc }}</p>
        <el-descriptions :column="1" border>
          <el-descriptions-item label="所属编组">{{ selectedRole.category }}</el-descriptions-item>
          <el-descriptions-item label="接收内容">{{ selectedRole.input }}</el-descriptions-item>
          <el-descriptions-item label="产出结果">{{ selectedRole.output }}</el-descriptions-item>
          <el-descriptions-item label="依赖能力">{{ selectedRole.tools.join("、") }}</el-descriptions-item>
          <el-descriptions-item label="项目价值">{{ selectedRole.value }}</el-descriptions-item>
        </el-descriptions>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, ref } from "vue";

const rolesRef = ref(null);
const workflowRef = ref(null);
const activeCategory = ref("全部");
const keyword = ref("");
const selectedRole = ref(null);
const showDialog = computed({
  get: () => Boolean(selectedRole.value),
  set: (value) => {
    if (!value) selectedRole.value = null;
  },
});

const heroPoints = [
  { title: "Profile" },
  { title: "RAG" },
  { title: "Planning" },
  { title: "Resource" },
  { title: "Tutor" },
  { title: "Evaluate" },
  { title: "Trace" },
];

const overviewCards = [
  { index: "01", title: "画像建模", desc: "结合对话、历史记录和基础信息，形成当前学习状态与薄弱点画像。" },
  { index: "02", title: "知识召回", desc: "按课程主题与问题上下文检索教材、题库和知识点依据。" },
  { index: "03", title: "资源组织", desc: "围绕软件工程学习场景生成讲解、练习、导图、代码与拓展材料。" },
  { index: "04", title: "路径推进", desc: "根据掌握度和目标课程拆出阶段任务，避免资源堆砌。" },
];

const roles = [
  ["画像分析模块", "PA", "构建学生当前学习画像", "画像理解", "用户对话、历史记录、个人信息", "学习阶段、薄弱点、兴趣偏好、追问线索", ["会话记忆", "画像抽取", "用户信息"], "负责把零散输入转成可持续使用的学习上下文。", "为后续检索、规划和答疑提供统一起点。"],
  ["知识检索模块", "RA", "从课程知识库召回依据", "画像理解", "学习目标、知识点、薄弱项", "教材片段、题库依据、来源引用", ["RAG 检索", "向量库", "来源标注"], "围绕软件工程课程内容提供可引用的知识依据，减少无根据生成。", "让答疑、讲解与评估都能回到真实课程内容。"],
  ["资源规划模块", "PL", "确定本轮学习任务的资源组合", "资源生成", "学生画像、课程依据、学习目标", "讲解重点、难度梯度、资源分工", ["任务拆解", "目标规划"], "在资源生成前先明确本轮到底要学什么、先学什么、用什么形式学。", "避免页面只展示很多功能，却缺少统一学习主线。"],
  ["讲义生成模块", "DA", "生成课程讲解与学习材料", "资源生成", "知识依据、学习目标、计划结果", "概念讲解、案例说明、常见误区、自测引导", ["内容生成", "知识增强"], "把软件工程课程知识整理成更适合当前学生阅读的学习文档。", "提升课程内容的可读性和针对性。"],
  ["练习设计模块", "QA", "生成分层训练内容", "资源生成", "知识点、学习阶段、薄弱项", "基础题、提升题、应用题、参考解析", ["题目生成", "评分规则"], "根据掌握度输出分层练习，不再只给统一题目。", "为评估闭环准备输入材料。"],
  ["阅读拓展模块", "RD", "补充延伸阅读与应用视角", "资源生成", "课程主题、专业目标、知识依据", "导读内容、延伸问题、拓展方向", ["阅读推荐", "知识关联"], "连接软件工程课程知识与真实工程场景、前沿方向。", "让学习资源不止停留在教材本身。"],
  ["知识导图模块", "MM", "输出结构化知识可视图", "资源生成", "教材片段、重点概念、易错点", "知识导图、概念关系、学习结构图", ["Mermaid", "结构整理"], "将抽象概念关系可视化，便于学生快速建立全局理解。", "增强复杂章节的结构感。"],
  ["代码实践模块", "CA", "生成配套编程或实验案例", "资源生成", "知识点、原理说明、课程主题", "Python 示例、实验任务、实践说明", ["代码生成", "示例校验"], "把偏理论内容转成可以动手验证的案例。", "服务本项目中的实践型学习场景。"],
  ["视频脚本模块", "VA", "组织口语化讲解脚本", "资源生成", "知识点讲解、重点步骤", "视频脚本、分镜提示、讲解节奏", ["脚本生成", "多模态策划"], "适配短视频或讲解型资源的生产需求。", "支持更丰富的学习呈现形式。"],
  ["质量校核模块", "QG", "检查资源是否适合当前学生", "质量控制", "生成内容、学生画像、知识依据", "质量评分、问题说明、返工建议", ["内容审核", "格式检查"], "从准确性、完整性、难度匹配度几个方向审查输出。", "形成资源生成后的第一道质量关。"],
  ["安全复核模块", "SA", "检查风险与来源充分性", "质量控制", "输出内容、引用来源", "风险提示、来源核验、可信提醒", ["来源核验", "安全审查"], "识别不充分引用、结论跳跃或不适宜内容。", "让系统更稳妥，也更适合正式展示。"],
  ["学习路径模块", "PG", "形成阶段化学习推进路线", "路径评估", "学生画像、掌握度、已生成资源", "阶段目标、学习节奏、资源建议", ["掌握度计算", "路径推荐"], "把单次资源结果串成可执行的学习计划。", "体现本项目不是一次性问答工具。"],
  ["效果评估模块", "EA", "记录学习结果并更新状态", "路径评估", "作答结果、学习行为、反馈记录", "评分、反馈、掌握度变化、学习事件", ["Rubric", "学习事件"], "将学习过程沉淀成可追踪记录，用于后续再规划。", "构成项目闭环中的关键回路。"],
  ["辅导答疑模块", "TA", "提供基于知识库的即时辅导", "答疑反馈", "学生问题、知识依据、学习画像", "解答、例子、进一步练习建议、来源", ["RAG 检索", "对话生成"], "在学习过程中承担随问随答和解释重构任务。", "提升系统陪伴式学习体验。"],
  ["结果编排模块", "PK", "把多路结果整合为统一输出", "答疑反馈", "合格资源、反馈结果、来源信息", "资源包、展示顺序、可追踪证据", ["元数据整理", "链路追踪"], "将多模块产出汇总成最终可展示页面或学习包。", "支撑页面展示与结果留痕。"],
].map((item) => ({
  name: item[0],
  short: item[1],
  role: item[2],
  category: item[3],
  input: item[4],
  output: item[5],
  tools: item[6],
  desc: item[7],
  value: item[8],
  state: "已接入",
}));

const categories = computed(() => ["全部", ...new Set(roles.map((item) => item.category))]);
const filteredRoles = computed(() =>
  roles.filter((item) => {
    const text = keyword.value.trim().toLowerCase();
    const hit = [item.name, item.role, item.category, item.input, item.output, item.desc, item.tools.join(" ")]
      .join(" ")
      .toLowerCase()
      .includes(text);
    return (activeCategory.value === "全部" || activeCategory.value === item.category) && (!text || hit);
  }),
);

const workflows = [
  { step: "01", title: "形成学习画像", desc: "根据用户对话、课程目标和历史信息识别当前阶段、薄弱点与学习偏好。", tags: ["画像分析模块", "会话记忆"] },
  { step: "02", title: "召回课程依据", desc: "围绕软件工程知识点检索教材、题库与知识库内容，作为后续处理依据。", tags: ["知识检索模块", "RAG 检索"] },
  { step: "03", title: "规划本轮资源", desc: "先明确讲什么、练什么、补什么，再决定讲义、练习、导图、代码等产出组合。", tags: ["资源规划模块", "资源生成编组"] },
  { step: "04", title: "执行质量校核", desc: "对结果进行准确性、个性化程度和来源充分性的审查，必要时触发返工。", tags: ["质量校核模块", "安全复核模块"] },
  { step: "05", title: "生成学习路径", desc: "结合掌握度与当前成果，整理阶段化学习建议和后续推进路线。", tags: ["学习路径模块", "效果评估模块"] },
  { step: "06", title: "进入辅导闭环", desc: "学生继续提问、练习、反馈，系统持续更新掌握度与下轮学习内容。", tags: ["辅导答疑模块", "结果编排模块"] },
];

const projectMappings = [
  { title: "学生画像驱动学习过程", desc: "系统不是先给答案，而是先判断学生学到哪里、缺什么、适合什么节奏。", tags: ["画像分析模块", "学习路径模块"] },
  { title: "课程知识库支撑可信回答", desc: "无论是答疑还是资源生成，都尽量回到软件工程课程知识库和题库内容。", tags: ["知识检索模块", "辅导答疑模块"] },
  { title: "围绕课程目标组织多样资源", desc: "讲义、练习、阅读、导图、代码和视频脚本都围绕同一学习目标协作生成。", tags: ["资源规划模块", "资源生成编组"] },
  { title: "学习结果可以追踪与复用", desc: "评分反馈、学习事件、来源引用会沉淀下来，为后续规划提供依据。", tags: ["效果评估模块", "结果编排模块"] },
];

function countByCategory(category) {
  return category === "全部" ? roles.length : roles.filter((item) => item.category === category).length;
}

function focusSection(type) {
  const target = type === "roles" ? rolesRef.value : workflowRef.value;
  target?.scrollIntoView({ behavior: "smooth", block: "start" });
}
</script>

<style scoped>
.architecture-page {
  display: grid;
  gap: 12px;
  padding-bottom: 2px;
  color: #172033;
}

.hero-shell {
  position: relative;
  overflow: hidden;
  border-radius: 22px;
  background:
    radial-gradient(circle at top right, rgba(173, 206, 255, 0.9), transparent 30%),
    radial-gradient(circle at left bottom, rgba(226, 232, 240, 0.8), transparent 26%),
    linear-gradient(135deg, #f8fbff 0%, #ffffff 52%, #f1f5f9 100%);
  box-shadow: 0 14px 34px rgba(15, 23, 42, 0.065);
}

.hero-shell::after {
  content: "";
  position: absolute;
  inset: 0;
  background:
    linear-gradient(120deg, rgba(15, 23, 42, 0.04), transparent 40%),
    linear-gradient(transparent, rgba(255, 255, 255, 0.36));
  pointer-events: none;
}

.hero-panel {
  position: relative;
  z-index: 1;
  display: grid;
  grid-template-columns: minmax(0, 1.15fr) minmax(360px, 0.85fr);
  gap: 18px;
  padding: 20px 22px;
  align-items: center;
}

.eyebrow,
.panel-kicker {
  display: inline-flex;
  align-items: center;
  min-height: 28px;
  padding: 0 11px;
  border-radius: 999px;
  background: rgba(29, 78, 216, 0.08);
  color: #2853c7;
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.hero-copy h1 {
  margin: 10px 0 10px;
  font-size: 48px;
  line-height: 1.04;
  letter-spacing: -0.04em;
  max-width: 620px;
}

.hero-desc,
.overview-card p,
.panel-head p,
.role-desc,
.flow-card p,
.map-body p,
.brief-card p,
.brief-point p,
.dialog-desc {
  color: #5f6f86;
  line-height: 1.62;
}

.hero-actions {
  display: flex;
  gap: 8px;
  margin-top: 14px;
}

.hero-brief {
  display: flex;
  justify-content: flex-end;
}

.command-card,
.overview-card,
.role-card,
.flow-card,
.content-panel {
  border: 1px solid rgba(207, 218, 234, 0.88);
  border-radius: 18px;
  background: rgba(255, 255, 255, 0.9);
  backdrop-filter: blur(10px);
}

.command-card {
  width: min(100%, 580px);
  padding: 18px 20px;
  box-shadow: 0 10px 26px rgba(37, 99, 235, 0.08);
}

.command-card strong {
  display: block;
  color: #172033;
  font-size: 24px;
  line-height: 1.16;
  letter-spacing: -0.03em;
}

.command-card p {
  margin: 10px 0 0;
  color: #667892;
  line-height: 1.56;
}

.compact-tags {
  margin-top: 12px;
}

.overview-index,
.flow-step {
  display: inline-block;
  margin-bottom: 10px;
  font-weight: 700;
}

.overview-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 10px;
}

.overview-card {
  min-height: 118px;
  padding: 14px 16px;
}

.overview-index,
.flow-step {
  color: #2b61e2;
  font-size: 20px;
  letter-spacing: -0.04em;
}

.overview-card h3,
.panel-head h2,
.role-meta h3,
.flow-card h3,
.map-body h3 {
  margin: 0 0 6px;
  font-size: 19px;
  line-height: 1.2;
  letter-spacing: -0.03em;
}

.overview-card h3 {
  font-size: 17px;
}

.content-panel {
  padding: 16px;
  box-shadow: 0 8px 22px rgba(15, 23, 42, 0.04);
}

.panel-head {
  display: flex;
  justify-content: space-between;
  align-items: end;
  gap: 12px;
  margin-bottom: 10px;
}

.panel-head h2 {
  margin-top: 6px;
}

.panel-head p {
  margin: 0;
  max-width: 760px;
}

.search-input {
  width: 220px;
}

.category-tabs {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 12px;
}

.category-tabs button {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  min-height: 34px;
  padding: 0 11px;
  border: 1px solid #d7e1ef;
  border-radius: 999px;
  background: #fff;
  color: #3357a8;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.24s ease;
}

.category-tabs button span {
  min-width: 22px;
  padding: 1px 6px;
  border-radius: 999px;
  background: #edf4ff;
  color: #2b61e2;
  font-size: 12px;
}

.category-tabs button.active {
  background: linear-gradient(135deg, #1d4ed8, #1e3a8a);
  border-color: transparent;
  color: #fff;
  box-shadow: 0 12px 30px rgba(29, 78, 216, 0.22);
}

.category-tabs button.active span {
  background: rgba(255, 255, 255, 0.16);
  color: #fff;
}

.role-grid,
.flow-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 10px;
}

.role-card {
  padding: 13px;
  box-shadow: 0 8px 20px rgba(15, 23, 42, 0.04);
}

.role-top,
.role-foot,
.dialog-head {
  display: flex;
  align-items: center;
  gap: 8px;
}

.role-top {
  justify-content: space-between;
}

.role-meta {
  flex: 1;
  min-width: 0;
}

.role-meta h3,
.dialog-head h3 {
  margin: 0;
  font-size: 15px;
}

.role-meta p,
.dialog-head p {
  margin: 3px 0 0;
  color: #708198;
  font-size: 12px;
}

.role-badge {
  display: grid;
  place-items: center;
  width: 36px;
  height: 36px;
  border-radius: 12px;
  background: linear-gradient(135deg, #1d4ed8, #0891b2);
  color: #fff;
  font-size: 14px;
  font-weight: 800;
  flex: 0 0 auto;
}

.role-badge.large {
  width: 46px;
  height: 46px;
  border-radius: 16px;
}

.role-state,
.trace-pill {
  display: inline-flex;
  align-items: center;
  min-height: 26px;
  padding: 0 10px;
  border-radius: 999px;
  background: #edf8ef;
  color: #4f8a3e;
  font-size: 12px;
  font-weight: 700;
}

.role-desc {
  min-height: 44px;
  margin: 8px 0 8px;
}

.role-io {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px;
}

.role-io div {
  min-height: 76px;
  padding: 10px;
  border-radius: 12px;
  background: linear-gradient(180deg, #f8fafc, #f3f7fb);
  border: 1px solid #e1e8f2;
}

.role-io small {
  display: block;
  margin-bottom: 4px;
  color: #2a5fe0;
  font-size: 12px;
  font-weight: 700;
}

.role-io span {
  color: #46566d;
  line-height: 1.48;
  font-size: 12px;
}

.role-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 8px;
}

.tag-chip {
  display: inline-flex;
  align-items: center;
  min-height: 24px;
  padding: 0 8px;
  border-radius: 999px;
  border: 1px solid #d9e4f2;
  background: #fff;
  color: #3d5f8f;
  font-size: 12px;
}

.tag-chip.dark {
  border-color: rgba(255, 255, 255, 0.12);
  background: rgba(255, 255, 255, 0.08);
  color: rgba(248, 250, 252, 0.92);
}

.tag-chip.green {
  border-color: #b8e3bf;
  background: #f2fbf3;
  color: #4f8a3e;
}

.role-foot {
  justify-content: space-between;
  margin-top: 8px;
  padding-top: 8px;
  border-top: 1px solid #e5ebf3;
  color: #71829a;
  font-size: 12px;
}

.dark-panel {
  background: linear-gradient(145deg, #0f172a 0%, #16243d 100%);
  border-color: rgba(255, 255, 255, 0.06);
  color: #f8fafc;
}

.panel-head.inverted p {
  color: rgba(226, 232, 240, 0.72);
}

.flow-card {
  min-height: 146px;
  padding: 14px;
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.06), rgba(255, 255, 255, 0.03));
  border-color: rgba(255, 255, 255, 0.08);
}

.flow-card h3 {
  font-size: 17px;
  color: #fff;
}

.flow-card p {
  color: rgba(226, 232, 240, 0.76);
}

.map-panel {
  overflow: hidden;
}

.map-list {
  display: grid;
  gap: 2px;
}

.map-item {
  position: relative;
  display: grid;
  grid-template-columns: 34px 1fr;
  column-gap: 14px;
  min-height: 86px;
}

.map-line {
  position: absolute;
  left: 13px;
  top: 0;
  bottom: -8px;
  width: 2px;
  background: linear-gradient(180deg, #c6d2e5 0%, #dfe7f2 100%);
}

.map-item:last-child .map-line {
  bottom: 40px;
}

.map-dot {
  position: relative;
  z-index: 1;
  width: 12px;
  height: 12px;
  margin: 7px 0 0 7px;
  border-radius: 50%;
  background: #67c23a;
  box-shadow: 0 0 0 6px rgba(103, 194, 58, 0.12);
}

.map-body {
  padding: 0 0 10px;
}

.dialog-desc {
  margin: 0 0 14px;
}

@media (max-width: 1380px) {
  .role-grid,
  .flow-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .hero-panel {
    grid-template-columns: 1fr;
    align-items: start;
  }

  .overview-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 900px) {
  .hero-panel,
  .role-grid,
  .flow-grid,
  .overview-grid,
  .role-io {
    grid-template-columns: 1fr;
  }

  .panel-head {
    align-items: stretch;
    flex-direction: column;
  }

  .search-input {
    width: 100%;
  }

  .hero-copy h1 {
    font-size: 40px;
  }

  .hero-brief {
    justify-content: stretch;
  }

  .command-card {
    width: 100%;
  }
}

@media (max-width: 640px) {
  .hero-panel,
  .content-panel {
    padding: 16px;
  }

  .hero-copy h1 {
    font-size: 30px;
  }

  .hero-actions {
    flex-direction: column;
  }

  .role-top {
    align-items: start;
    flex-wrap: wrap;
  }
}
</style>
