<template>
  <div class="auth-shell">
    <main class="auth-main">
      <section class="illustration-panel">
        <div class="product-brand">
          <div class="brand-badge" aria-hidden="true">
            <span class="book-icon">
              <span class="book-page left"></span>
              <span class="book-page right"></span>
              <span class="book-spine"></span>
            </span>
            <span class="badge-corner"></span>
          </div>
          <div>
            <strong>MultiTutor</strong>
            <span>智伴学堂</span>
          </div>
        </div>
        <div class="illustration-copy">
          <h1>以智能体协同，重塑个性化学习体验。</h1>
          <p>基于知识图谱、学习画像与智能问答，为每位学习者组织更清晰、更贴合自己的学习路径。</p>
        </div>

        <svg class="learning-illustration" viewBox="0 0 760 560" role="img" aria-label="学生与 AI 学习助手协作的原创插画">
          <defs>
            <filter id="softShadow" x="-20%" y="-20%" width="140%" height="150%">
              <feDropShadow dx="0" dy="14" stdDeviation="14" flood-color="#1c1d1f" flood-opacity=".10" />
            </filter>
          </defs>
          <circle class="decor decor-one" cx="104" cy="92" r="24" />
          <circle class="decor decor-two" cx="662" cy="92" r="18" />
          <rect class="decor decor-three" x="614" y="438" width="44" height="44" rx="12" />
          <path class="line-art" d="M126 430 C192 382 254 384 322 430 S472 484 584 414" />
          <g filter="url(#softShadow)">
            <rect class="screen" x="210" y="116" width="342" height="236" rx="24" />
            <rect class="screen-top" x="210" y="116" width="342" height="54" rx="24" />
            <circle class="dot dark" cx="244" cy="143" r="7" />
            <circle class="dot purple" cx="268" cy="143" r="7" />
            <circle class="dot orange" cx="292" cy="143" r="7" />
            <rect class="code-line purple-fill" x="252" y="204" width="126" height="12" rx="6" />
            <rect class="code-line" x="252" y="236" width="204" height="12" rx="6" />
            <rect class="code-line" x="252" y="268" width="150" height="12" rx="6" />
            <rect class="course-card" x="422" y="198" width="82" height="92" rx="14" />
            <path class="play" d="M454 226 L454 264 L484 245 Z" />
          </g>
          <g class="knowledge-graph">
            <path d="M426 126 L496 72 L590 128" />
            <path d="M496 72 L522 170" />
            <path d="M590 128 L522 170" />
            <circle cx="426" cy="126" r="12" />
            <circle cx="496" cy="72" r="12" />
            <circle cx="590" cy="128" r="12" />
            <circle cx="522" cy="170" r="12" />
          </g>
          <g class="student student-left">
            <circle class="skin" cx="164" cy="294" r="30" />
            <path class="hair" d="M132 290 C138 250 198 250 201 288 C184 274 160 274 132 290" />
            <path class="body purple-fill" d="M104 424 C112 354 132 324 166 324 C202 324 224 354 232 424 Z" />
            <path class="arm" d="M214 360 C244 352 264 334 284 304" />
          </g>
          <g class="student student-right">
            <circle class="skin" cx="596" cy="306" r="28" />
            <path class="hair" d="M568 306 C570 270 620 264 630 300 C610 288 590 290 568 306" />
            <path class="body blue-fill" d="M532 426 C540 362 560 334 594 334 C628 334 648 362 656 426 Z" />
            <path class="arm" d="M548 370 C516 356 492 334 474 304" />
          </g>
          <g class="assistant-bubble">
            <rect x="92" y="122" width="142" height="74" rx="22" />
            <circle cx="128" cy="159" r="8" />
            <circle cx="162" cy="159" r="8" />
            <circle cx="196" cy="159" r="8" />
          </g>
          <g class="book-stack">
            <rect x="320" y="406" width="148" height="28" rx="8" />
            <rect x="300" y="434" width="188" height="30" rx="9" />
            <rect x="338" y="464" width="120" height="24" rx="8" />
          </g>
        </svg>
      </section>

      <section class="login-panel">
        <div class="login-card">
          <div class="card-header">
            <span class="card-kicker">智伴学堂</span>
            <h2>登录</h2>
            <p>进入 MultiTutor 个性化学习空间</p>
          </div>

          <el-form :model="form" label-position="top" class="login-form" @keyup.enter="login">
            <el-form-item label="用户名">
              <el-input v-model="form.username" size="large" placeholder="请输入用户名" :prefix-icon="User" />
            </el-form-item>
            <el-form-item label="密码">
              <el-input v-model="form.password" size="large" type="password" show-password placeholder="请输入密码" :prefix-icon="Lock" />
            </el-form-item>
            <el-button class="login-button" type="primary" size="large" :loading="loading" @click="login">登录系统</el-button>
          </el-form>

          <div class="register-line">
            <span>还没有账号？</span>
            <el-button link type="primary" @click="registerVisible = true">立即注册</el-button>
          </div>
        </div>
      </section>
    </main>

    <el-dialog v-model="registerVisible" title="创建新账号" width="420px" align-center>
      <el-form :model="registerForm" label-position="top">
        <el-form-item label="用户名">
          <el-input v-model="registerForm.username" size="large" placeholder="至少2位字符" :prefix-icon="User" />
        </el-form-item>
        <el-form-item label="密码">
          <el-input v-model="registerForm.password" size="large" type="password" show-password placeholder="至少6位字符" :prefix-icon="Lock" />
        </el-form-item>
        <el-form-item label="确认密码">
          <el-input v-model="registerForm.confirmPassword" size="large" type="password" show-password placeholder="请再次输入密码" :prefix-icon="Lock" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="registerVisible = false">取消</el-button>
        <el-button type="primary" :loading="registerLoading" @click="register">注册并登录</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { reactive, ref } from "vue";
import { useRoute, useRouter } from "vue-router";
import { ElMessage } from "element-plus";
import { Lock, User } from "@element-plus/icons-vue";
import { authApi } from "../api";
const router = useRouter();
const route = useRoute();
const loading = ref(false);
const registerLoading = ref(false);
const registerVisible = ref(false);
const form = reactive({ username: "", password: "" });
const registerForm = reactive({ username: "", password: "", confirmPassword: "" });
function saveSession(data) { localStorage.setItem("token", data.token); localStorage.setItem("user", JSON.stringify({ id: data.id, username: data.username, profile_completed: data.profile_completed })); }
function validateLoginForm(target) { if (!target.username.trim()) { ElMessage.warning("请输入用户名"); return false; } if (!target.password) { ElMessage.warning("请输入密码"); return false; } return true; }
async function login() { if (!validateLoginForm(form)) return; loading.value = true; try { const res = await authApi.login(form); if (res.code === 200) { saveSession(res.data); if (res.data.profile_completed) localStorage.removeItem("a3_need_complete_user_info"); ElMessage.success("登录成功"); router.push(route.query.redirect || "/profile"); } else { ElMessage.error(res.msg || "用户名或密码错误"); } } finally { loading.value = false; } }
async function register() { if (!validateLoginForm(registerForm)) return; if (registerForm.password.length < 6) { ElMessage.warning("密码至少6位"); return; } if (registerForm.password !== registerForm.confirmPassword) { ElMessage.warning("两次密码不一致"); return; } registerLoading.value = true; try { const res = await authApi.register({ username: registerForm.username, password: registerForm.password }); if (res.code === 200) { saveSession(res.data); localStorage.setItem("a3_need_complete_user_info", "1"); ElMessage.success("注册成功，请完善个人信息"); registerVisible.value = false; router.push("/profile"); } else { ElMessage.error(res.msg || "注册失败"); } } finally { registerLoading.value = false; } }
</script>

<style scoped>
.auth-shell {
  --purple: #38bdf8;
  --purple-dark: #0ea5e9;
  --ink: #1c1d1f;
  --muted: #6a6f73;
  --border: #d1d7dc;
  --soft-border: #edf0f2;
  --orange: #f59e0b;
  --blue: #2563eb;
  min-height: 100vh;
  overflow-x: hidden;
  background: #fff;
  color: var(--ink);
}

.auth-main {
  display: grid;
  grid-template-columns: minmax(0, 1.1fr) minmax(420px, .9fr);
  align-items: center;
  gap: clamp(44px, 5vw, 70px);
  width: min(1500px, 100%);
  min-height: 100vh;
  margin: 0 auto;
  padding: 42px clamp(32px, 4vw, 60px);
  background: #fff;
}

.illustration-panel {
  display: grid;
  gap: 24px;
  align-items: center;
  animation: fadeUp .42s ease both;
}

.product-brand {
  display: inline-flex;
  align-items: center;
  gap: 13px;
  justify-self: start;
}

.brand-badge {
  position: relative;
  width: 48px;
  height: 48px;
  border-radius: 16px;
  background: linear-gradient(135deg, #38bdf8 0%, #60a5fa 100%);
  box-shadow: 0 14px 28px rgba(56, 189, 248, .22);
  overflow: hidden;
}

.brand-badge::before {
  position: absolute;
  right: 8px;
  bottom: 8px;
  width: 12px;
  height: 12px;
  border-right: 3px solid rgba(255, 255, 255, .78);
  border-bottom: 3px solid rgba(255, 255, 255, .78);
  border-radius: 0 0 5px 0;
  content: "";
}

.book-icon {
  position: absolute;
  left: 9px;
  top: 11px;
  z-index: 2;
  width: 25px;
  height: 19px;
}

.book-page {
  position: absolute;
  top: 0;
  width: 12px;
  height: 18px;
  border: 2px solid rgba(255, 255, 255, .94);
  background: rgba(255, 255, 255, .18);
}

.book-page.left {
  left: 0;
  border-right: 0;
  border-radius: 5px 0 0 5px;
  transform: skewY(-5deg);
}

.book-page.right {
  right: 0;
  border-left: 0;
  border-radius: 0 5px 5px 0;
  transform: skewY(5deg);
}

.book-spine {
  position: absolute;
  left: 11px;
  top: 2px;
  width: 3px;
  height: 17px;
  border-radius: 999px;
  background: rgba(255, 255, 255, .96);
}

.badge-corner {
  position: absolute;
  right: 7px;
  top: 7px;
  width: 9px;
  height: 9px;
  border-radius: 50%;
  background: #f59e0b;
  box-shadow: 0 0 0 3px rgba(255, 255, 255, .9);
}

.product-brand strong {
  display: block;
  color: var(--ink);
  font-size: 22px;
  font-weight: 850;
  letter-spacing: 0;
}

.product-brand span {
  display: block;
  margin-top: 3px;
  color: var(--muted);
  font-size: 13px;
  font-weight: 650;
}

.illustration-copy {
  max-width: 560px;
}

.illustration-copy span {
  display: inline-flex;
  margin-bottom: 12px;
  color: var(--purple);
  font-size: 12px;
  font-weight: 800;
  letter-spacing: 1.5px;
  text-transform: uppercase;
}

.illustration-copy h1 {
  margin: 0;
  color: var(--ink);
  font-size: clamp(30px, 3vw, 44px);
  font-weight: 800;
  line-height: 1.18;
  letter-spacing: 0;
}

.illustration-copy p {
  max-width: 520px;
  margin: 14px 0 0;
  color: var(--muted);
  font-size: 16px;
  font-weight: 500;
  line-height: 1.78;
}

.learning-illustration {
  display: block;
  width: 100%;
  max-width: 680px;
  height: auto;
}

.screen,
.assistant-bubble rect,
.book-stack rect {
  fill: #fff;
  stroke: #1c1d1f;
  stroke-width: 3;
}

.screen-top {
  fill: #ecfeff;
}

.line-art,
.knowledge-graph path,
.arm {
  fill: none;
  stroke: #1c1d1f;
  stroke-width: 4;
  stroke-linecap: round;
}

.knowledge-graph path {
  stroke: #38bdf8;
  stroke-width: 3;
}

.knowledge-graph circle,
.purple-fill {
  fill: #38bdf8;
}

.blue-fill {
  fill: #2563eb;
}

.orange {
  fill: var(--orange);
}

.dot.dark,
.hair {
  fill: #1c1d1f;
}

.dot.purple,
.decor-one,
.decor-three {
  fill: #38bdf8;
}

.dot.orange,
.decor-two,
.book-stack rect:nth-child(2) {
  fill: #f59e0b;
}

.code-line {
  fill: #d9dfe7;
}

.course-card {
  fill: #ecfeff;
  stroke: #38bdf8;
  stroke-width: 3;
}

.play {
  fill: #38bdf8;
}

.skin {
  fill: #ffd8bd;
  stroke: #1c1d1f;
  stroke-width: 3;
}

.body {
  stroke: #1c1d1f;
  stroke-width: 3;
}

.assistant-bubble circle {
  fill: #38bdf8;
}

.decor {
  opacity: .14;
}

.login-panel {
  display: grid;
  place-items: center;
}

.login-card {
  width: 100%;
  max-width: 500px;
  margin: 0 auto;
  padding: clamp(28px, 3vw, 38px);
  border: 1px solid var(--soft-border);
  border-radius: 10px;
  background: #fff;
  box-shadow: 0 12px 34px rgba(28, 29, 31, .055);
  animation: fadeUp .48s ease .05s both;
}

.card-header {
  margin-bottom: 28px;
}

.card-kicker {
  display: block;
  margin-bottom: 10px;
  color: var(--purple);
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 1.5px;
  text-transform: uppercase;
}

.card-header h2 {
  margin: 0;
  color: var(--ink);
  font-size: 36px;
  font-weight: 700;
  line-height: 1.2;
  letter-spacing: 0;
}

.card-header p {
  margin: 10px 0 0;
  color: var(--muted);
  font-size: 15px;
  font-weight: 500;
}

.login-form :deep(.el-form-item) {
  margin-bottom: 20px;
}

.login-form :deep(.el-form-item__label) {
  margin-bottom: 8px;
  color: var(--ink);
  font-size: 14px;
  font-weight: 600;
}

.login-form :deep(.el-input__wrapper) {
  min-height: 60px;
  padding: 0 18px;
  border-radius: 6px;
  background: #fff;
  box-shadow: 0 0 0 1px #b7b9bd inset;
  transition: box-shadow .2s ease, border-color .2s ease;
}

.login-form :deep(.el-input__inner) {
  color: var(--ink);
  font-size: 15px;
}

.login-form :deep(.el-input__inner::placeholder) {
  color: #9ca3af;
}

.login-form :deep(.el-input__prefix) {
  color: var(--muted);
}

.login-form :deep(.el-input__wrapper:hover) {
  box-shadow: 0 0 0 1px #8f9399 inset;
}

.login-form :deep(.el-input__wrapper.is-focus) {
  box-shadow: 0 0 0 1px var(--purple) inset, 0 0 0 3px rgba(56, 189, 248, .18);
}

.login-button {
  width: 100%;
  height: 56px;
  margin-top: 4px;
  border: 0;
  border-radius: 6px;
  background: var(--purple);
  color: #fff;
  font-size: 16px;
  font-weight: 700;
  box-shadow: none;
  cursor: pointer;
  transition: background .2s ease, transform .12s ease, opacity .2s ease;
}

.login-button:hover {
  background: var(--purple-dark);
}

.login-button:active {
  transform: translateY(1px);
}

.login-button.is-disabled,
.login-button:disabled {
  cursor: not-allowed;
  opacity: .62;
}

.register-line {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 5px;
  margin-top: 22px;
  color: var(--muted);
  font-size: 13px;
  font-weight: 500;
}

.register-line :deep(.el-button) {
  color: var(--purple);
  font-weight: 700;
}

.register-line :deep(.el-button:hover) {
  color: var(--purple-dark);
  text-decoration: underline;
}

@keyframes fadeUp {
  from {
    opacity: 0;
    transform: translateY(14px);
  }

  to {
    opacity: 1;
    transform: translateY(0);
  }
}

@media (max-width: 1200px) {
  .auth-main {
    grid-template-columns: minmax(0, 1fr) minmax(380px, 1fr);
    gap: 38px;
    padding-right: 36px;
    padding-left: 36px;
  }

  .illustration-copy h1 {
    font-size: 34px;
  }

  .login-card {
    max-width: 440px;
  }
}

@media (max-width: 768px) {
  .auth-main {
    grid-template-columns: 1fr;
    min-height: 100vh;
    gap: 22px;
    padding: 26px 20px 36px;
  }

  .illustration-panel {
    justify-items: center;
    gap: 12px;
  }

  .product-brand {
    justify-self: center;
  }

  .illustration-copy {
    text-align: center;
  }

  .illustration-copy h1 {
    font-size: 28px;
  }

  .illustration-copy p {
    font-size: 14px;
  }

  .learning-illustration {
    max-height: 250px;
  }

  .login-card {
    max-width: 100%;
    padding: 24px 0 0;
    border: 0;
    box-shadow: none;
  }

  .card-header h2 {
    font-size: 28px;
  }

  .login-form :deep(.el-input__wrapper) {
    min-height: 56px;
  }

  .login-button {
    height: 54px;
  }
}

@media (max-width: 480px) {
  .auth-main {
    padding-right: 16px;
    padding-left: 16px;
  }

  .decor,
  .knowledge-graph {
    display: none;
  }

  .card-header {
    margin-bottom: 28px;
  }

  .card-header h2 {
    font-size: 26px;
  }
}

@media (prefers-reduced-motion: reduce) {
  *,
  *::before,
  *::after {
    animation-duration: .01ms !important;
    animation-iteration-count: 1 !important;
    scroll-behavior: auto !important;
    transition-duration: .01ms !important;
  }
}
</style>
