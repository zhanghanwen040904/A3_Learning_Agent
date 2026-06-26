<template>
  <div class="workspace-shell">
    <header class="topbar aa-panel">
      <div class="brand">
        <div class="brand-mark">
          <span></span>
          <i></i>
        </div>
        <div>
          <p class="aa-kicker">China Software Cup A3</p>
          <h1>AptAdapt 智构学舱</h1>
        </div>
      </div>

      <nav class="nav-tabs" aria-label="主导航">
        <button class="active">学习工作台</button>
        <button>资源工厂</button>
        <button>智能体监控</button>
        <button>学习评估</button>
      </nav>

      <div class="user-pill">
        <span class="pulse-dot"></span>
        <span>徐英博 · 前端演示</span>
      </div>
    </header>

    <main class="dashboard">
      <aside class="left-stack">
        <section class="aa-panel course-panel">
          <div class="section-head">
            <div>
              <p class="aa-kicker">Course</p>
              <h2 class="aa-title">课程选择</h2>
            </div>
          </div>
          <el-select
            v-model="courseStore.currentId"
            placeholder="选择课程"
            @change="handleCourseChange"
            size="large"
            style="width: 100%"
          >
            <el-option
              v-for="course in courseStore.courses"
              :key="course.id"
              :label="course.name"
              :value="course.id"
            >
              <span>{{ course.name }}</span>
              <span class="chapter-count">{{ course.chapters?.length || 0 }} 章</span>
            </el-option>
          </el-select>
          <p class="course-desc">
            {{ courseStore.currentCourse?.description || '围绕计算机组成原理构建个性化资源生成闭环。' }}
          </p>
        </section>

        <section class="aa-panel">
          <ProfileCard />
        </section>

        <section class="aa-panel">
          <PathTree />
        </section>
      </aside>

      <section class="center-stack">
        <section class="hero aa-panel">
          <div class="hero-copy">
            <p class="aa-kicker">Multi-Agent Learning Cockpit</p>
            <h2>面向《计算机组成原理》的个性化资源生成平台</h2>
            <p>
              Supervisor 协调画像、检索、路径规划、资源生成和内容审核智能体，
              将抽象硬件知识转换为可学习、可练习、可追踪的资源闭环。
            </p>
            <div class="hero-actions">
              <el-button type="primary" size="large">生成学习资源</el-button>
              <el-button size="large">查看演示脚本</el-button>
            </div>
          </div>

          <div class="agent-orbit">
            <div class="orbit">
              <div class="chip-core">Supervisor</div>
              <div class="chip-node n1">Profile</div>
              <div class="chip-node n2">RAG</div>
              <div class="chip-node n3">Quiz</div>
              <div class="chip-node n4">Review</div>
            </div>
          </div>
        </section>

        <section class="aa-panel chat-shell">
          <ChatPanel />
        </section>
      </section>

      <aside class="right-stack">
        <section class="aa-panel status-panel">
          <div class="section-head">
            <div>
              <p class="aa-kicker">Agent Status</p>
              <h2 class="aa-title">多智能体状态</h2>
            </div>
          </div>
          <AgentStatusBar />
        </section>

        <section class="aa-panel resource-shell">
          <ResourcePanel />
        </section>

        <section class="aa-panel">
          <EvaluationPanel />
        </section>
      </aside>
    </main>
  </div>
</template>

<script setup>
import { onMounted } from 'vue'
import { useCourseStore } from '../stores/course'
import ChatPanel from '../components/ChatPanel.vue'
import PathTree from '../components/PathTree.vue'
import ResourcePanel from '../components/ResourcePanel.vue'
import ProfileCard from '../components/ProfileCard.vue'
import EvaluationPanel from '../components/EvaluationPanel.vue'
import AgentStatusBar from '../components/AgentStatusBar.vue'

const courseStore = useCourseStore()

function handleCourseChange(courseId) {
  courseStore.switchCourse(courseId)
}

onMounted(() => {
  courseStore.loadCourses()
})
</script>

<style scoped>
.workspace-shell {
  position: relative;
  z-index: 1;
  width: min(1880px, calc(100% - 40px));
  height: 100vh;
  margin: 0 auto;
  padding: 20px 0 28px;
  display: grid;
  grid-template-rows: auto 1fr;
  gap: 18px;
}

.topbar {
  display: grid;
  grid-template-columns: minmax(260px, 1fr) auto minmax(220px, 1fr);
  align-items: center;
  gap: 18px;
  padding: 14px 18px;
}

.brand {
  display: flex;
  align-items: center;
  gap: 14px;
  min-width: 0;
}

.brand-mark {
  position: relative;
  width: 48px;
  height: 48px;
  display: grid;
  place-items: center;
  border-radius: 8px;
  background: linear-gradient(135deg, rgba(97, 215, 255, 0.42), rgba(140, 245, 212, 0.5));
  border: 1px solid rgba(64, 184, 230, 0.34);
  box-shadow: 0 0 35px rgba(64, 215, 255, 0.18);
}

.brand-mark span {
  width: 25px;
  height: 25px;
  border: 2px solid var(--aa-cyan);
  transform: rotate(45deg);
}

.brand-mark i {
  position: absolute;
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--aa-green);
  box-shadow: 0 0 18px var(--aa-green);
}

.brand h1 {
  margin: 4px 0 0;
  font-size: 24px;
  line-height: 1;
  color: var(--aa-text);
}

.nav-tabs {
  display: inline-flex;
  gap: 8px;
  padding: 6px;
  border-radius: 8px;
  background: rgba(237, 246, 255, 0.8);
  border: 1px solid rgba(99, 145, 190, 0.12);
}

.nav-tabs button {
  min-width: 92px;
  padding: 10px 14px;
  border: 0;
  border-radius: 7px;
  color: var(--aa-muted);
  background: transparent;
  cursor: pointer;
  white-space: nowrap;
}

.nav-tabs button.active {
  color: #0f4e72;
  background: linear-gradient(135deg, rgba(122, 225, 255, 0.55), rgba(220, 232, 255, 0.8));
  box-shadow: inset 0 0 0 1px rgba(64, 184, 230, 0.22);
}

.user-pill {
  justify-self: end;
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 14px;
  border-radius: 8px;
  border: 1px solid rgba(39, 201, 148, 0.22);
  background: rgba(226, 255, 245, 0.76);
  color: #14664d;
  font-weight: 700;
}

.pulse-dot {
  width: 9px;
  height: 9px;
  border-radius: 50%;
  background: var(--aa-green);
  box-shadow: 0 0 0 7px rgba(39, 201, 148, 0.12);
}

.dashboard {
  min-height: 0;
  min-width: 0;
  display: grid;
  grid-template-columns: 300px minmax(520px, 1fr) 360px;
  gap: 18px;
  align-items: start;
  overflow: hidden;
}

.left-stack,
.center-stack,
.right-stack {
  min-height: 0;
  min-width: 0;
  display: grid;
  gap: 18px;
}

.left-stack,
.right-stack {
  max-height: 100%;
  overflow: auto;
  padding-bottom: 4px;
}

.center-stack {
  grid-template-rows: auto minmax(0, 1fr);
  height: 100%;
}

.course-panel,
.status-panel,
.resource-shell {
  padding: 18px;
}

.section-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 14px;
  margin-bottom: 14px;
}

.chapter-count {
  float: right;
  color: #8a9aac;
  font-size: 13px;
}

.course-desc {
  margin: 12px 0 0;
  color: var(--aa-muted);
  font-size: 13px;
  line-height: 1.7;
}

.hero {
  min-height: 250px;
  display: grid;
  grid-template-columns: minmax(0, 1.15fr) 300px;
  gap: 22px;
  align-items: center;
  padding: 26px 28px;
}

.hero-copy h2 {
  max-width: 720px;
  margin: 10px 0 14px;
  color: var(--aa-text);
  font-size: clamp(30px, 3.1vw, 46px);
  line-height: 1.12;
  letter-spacing: 0;
}

.hero-copy p:last-of-type {
  max-width: 720px;
  color: #60788e;
  font-size: 16px;
  line-height: 1.85;
}

.hero-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  margin-top: 22px;
}

.agent-orbit {
  min-height: 220px;
  display: grid;
  place-items: center;
}

.orbit {
  position: relative;
  width: 230px;
  height: 230px;
  border-radius: 50%;
  border: 1px dashed rgba(25, 191, 234, 0.34);
}

.orbit::before,
.orbit::after {
  content: "";
  position: absolute;
  inset: 32px;
  border-radius: 50%;
  border: 1px solid rgba(39, 201, 148, 0.16);
}

.orbit::after {
  inset: 70px;
  border-color: rgba(255, 124, 172, 0.18);
}

.chip-core,
.chip-node {
  position: absolute;
  display: grid;
  place-items: center;
  border-radius: 8px;
  border: 1px solid rgba(89, 128, 176, 0.14);
  background: rgba(255, 255, 255, 0.92);
  box-shadow: 0 0 28px rgba(25, 191, 234, 0.14);
}

.chip-core {
  inset: 82px 54px;
  color: var(--aa-cyan);
  font-weight: 900;
}

.chip-node {
  width: 82px;
  height: 34px;
  color: #31516c;
  font-size: 12px;
  font-weight: 800;
}

.n1 { left: 84px; top: -17px; }
.n2 { right: -24px; top: 84px; }
.n3 { right: 10px; bottom: 28px; }
.n4 { left: -26px; bottom: 68px; }

.chat-shell {
  min-height: 0;
  padding: 0;
}

@media (max-width: 1360px) {
  .dashboard {
    grid-template-columns: 280px minmax(480px, 1fr);
    overflow: auto;
  }

  .right-stack {
    grid-column: 1 / -1;
    grid-template-columns: repeat(3, 1fr);
  }

  .hero {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 900px) {
  .workspace-shell {
    width: min(calc(100vw - 24px), 1880px);
    height: auto;
    overflow: hidden;
  }

  .topbar,
  .dashboard,
  .right-stack {
    grid-template-columns: 1fr;
  }

  .topbar {
    min-width: 0;
    overflow: hidden;
  }

  .brand h1 {
    font-size: 22px;
  }

  .nav-tabs {
    width: 100%;
    min-width: 0;
    overflow-x: auto;
  }

  .nav-tabs button {
    min-width: 74px;
    padding: 10px 8px;
  }

  .user-pill {
    justify-self: start;
  }

  .hero-copy h2 {
    font-size: 34px;
  }
}
</style>
