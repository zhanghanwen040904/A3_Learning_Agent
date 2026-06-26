<template>
  <div class="auth-shell">
    <section class="hero-panel">
      <div class="brand-block">
        <div class="hero-logo">A3</div>
        <div>
          <h1>Learning Agent</h1>
          <p>面向课程学习的智能画像、资源生成与学习评估平台</p>
        </div>
      </div>

      <div class="hero-content">
        <span class="hero-kicker">Intelligent Learning Workspace</span>
        <h2>让学习画像、课程资源与答疑服务形成闭环</h2>
        <p>
          系统基于学习画像理解学生目标、基础与薄弱点，自动生成个性化学习资源，并结合知识库提供可追溯的智能答疑体验。
        </p>
      </div>

      <div class="feature-list">
        <div v-for="item in features" :key="item.title" class="feature-item">
          <span>{{ item.index }}</span>
          <div>
            <strong>{{ item.title }}</strong>
            <p>{{ item.desc }}</p>
          </div>
        </div>
      </div>
    </section>

    <section class="login-panel">
      <div class="login-card">
        <div class="card-title">
          <div>
            <span>欢迎回来</span>
            <p>登录后继续使用你的个性化学习空间</p>
          </div>
          <span class="login-badge">AI 学习助手</span>
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

const features = [
  { index: "01", title: "对话式画像", desc: "通过自然语言收集目标、基础与偏好" },
  { index: "02", title: "个性化资源", desc: "生成讲解、练习、导图、代码和阅读材料" },
  { index: "03", title: "智能答疑", desc: "结合课程知识库提供可追溯回答" },
];

function saveSession(data) {
  localStorage.setItem("token", data.token);
  localStorage.setItem("user", JSON.stringify({ id: data.id, username: data.username }));
}

function validateLoginForm(target) {
  if (!target.username.trim()) {
    ElMessage.warning("请输入用户名");
    return false;
  }
  if (!target.password) {
    ElMessage.warning("请输入密码");
    return false;
  }
  return true;
}

async function login() {
  if (!validateLoginForm(form)) return;
  loading.value = true;
  try {
    const res = await authApi.login(form);
    if (res.code === 200) {
      saveSession(res.data);
      ElMessage.success("登录成功");
      router.push(route.query.redirect || "/profile");
    } else {
      ElMessage.error(res.msg || "用户名或密码错误");
    }
  } finally {
    loading.value = false;
  }
}

async function register() {
  if (!validateLoginForm(registerForm)) return;
  if (registerForm.password.length < 6) {
    ElMessage.warning("密码至少6位");
    return;
  }
  if (registerForm.password !== registerForm.confirmPassword) {
    ElMessage.warning("两次密码不一致");
    return;
  }
  registerLoading.value = true;
  try {
    const res = await authApi.register({ username: registerForm.username, password: registerForm.password });
    if (res.code === 200) {
      saveSession(res.data);
      ElMessage.success("注册成功，已自动登录");
      registerVisible.value = false;
      router.push("/profile");
    } else {
      ElMessage.error(res.msg || "注册失败");
    }
  } finally {
    registerLoading.value = false;
  }
}
</script>

<style scoped>
.auth-shell {
  display: grid;
  grid-template-columns: minmax(0, 1.05fr) minmax(420px, 0.95fr);
  width: 100%;
  height: 100vh;
  min-height: 0;
  overflow: hidden;
  background: #f5f7fb;
}

.hero-panel {
  position: relative;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  overflow: hidden;
  padding: 56px 64px;
  color: #ffffff;
  background:
    radial-gradient(circle at 16% 18%, rgba(125, 211, 252, 0.5), transparent 28%),
    radial-gradient(circle at 82% 14%, rgba(129, 140, 248, 0.58), transparent 30%),
    radial-gradient(circle at 86% 78%, rgba(20, 184, 166, 0.38), transparent 30%),
    linear-gradient(135deg, #0f172a 0%, #1e40af 55%, #0891b2 100%);
}

.hero-panel::after {
  position: absolute;
  right: -120px;
  bottom: -130px;
  width: 360px;
  height: 360px;
  content: "";
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.1);
}

.brand-block {
  position: relative;
  z-index: 1;
  display: flex;
  align-items: center;
  gap: 18px;
}

.hero-logo {
  display: grid;
  width: 58px;
  height: 58px;
  place-items: center;
  border-radius: 18px;
  background: rgba(255, 255, 255, 0.18);
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.28);
  font-size: 20px;
  font-weight: 800;
}

.brand-block h1 {
  margin: 0;
  font-size: 30px;
  letter-spacing: -0.02em;
}

.brand-block p {
  margin: 5px 0 0;
  color: rgba(255, 255, 255, 0.72);
}

.hero-content {
  position: relative;
  z-index: 1;
  max-width: 640px;
  margin: 42px 0;
}

.hero-kicker {
  display: inline-flex;
  margin-bottom: 16px;
  padding: 7px 12px;
  border: 1px solid rgba(255, 255, 255, 0.24);
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.12);
  color: rgba(255, 255, 255, 0.82);
  font-size: 12px;
  letter-spacing: 0.04em;
}

.hero-content h2 {
  max-width: 620px;
  margin: 0;
  font-size: 42px;
  line-height: 1.18;
  letter-spacing: -0.04em;
}

.hero-content p {
  max-width: 580px;
  margin: 18px 0 0;
  color: rgba(255, 255, 255, 0.78);
  font-size: 15px;
  line-height: 1.9;
}

.feature-list {
  position: relative;
  z-index: 1;
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 14px;
}

.feature-item {
  min-height: 126px;
  padding: 18px;
  border: 1px solid rgba(255, 255, 255, 0.16);
  border-radius: 22px;
  background: rgba(255, 255, 255, 0.12);
  backdrop-filter: blur(14px);
}

.feature-item span {
  display: inline-grid;
  width: 34px;
  height: 34px;
  margin-bottom: 12px;
  place-items: center;
  border-radius: 12px;
  background: rgba(255, 255, 255, 0.18);
  font-size: 13px;
  font-weight: 800;
}

.feature-item strong {
  display: block;
  font-size: 15px;
}

.feature-item p {
  margin: 7px 0 0;
  color: rgba(255, 255, 255, 0.7);
  font-size: 13px;
  line-height: 1.6;
}

.login-panel {
  display: grid;
  min-width: 0;
  place-items: center;
  padding: 40px;
  background:
    radial-gradient(circle at top right, rgba(219, 234, 254, 0.8), transparent 34%),
    linear-gradient(180deg, #ffffff 0%, #f8fafc 100%);
}

.login-card {
  width: min(420px, 100%);
  padding: 34px;
  border: 1px solid #e5eaf3;
  border-radius: 28px;
  background: rgba(255, 255, 255, 0.96);
  box-shadow: 0 24px 70px rgba(15, 23, 42, 0.12);
}

.card-title {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 14px;
  color: #101828;
}

.card-title span {
  display: block;
  font-size: 26px;
  font-weight: 780;
  letter-spacing: -0.02em;
}

.card-title p {
  margin: 8px 0 0;
  color: #667085;
  font-size: 14px;
  line-height: 1.7;
}

.login-badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  height: 22px;
  padding: 0 8px;
  border: 1px solid #bbf7d0;
  border-radius: 999px;
  background: #f0fdf4;
  color: #16a34a;
  font-size: 11px;
  font-weight: 500;
  line-height: 1;
  white-space: nowrap;
}

.login-form {
  margin-top: 26px;
}

.login-form :deep(.el-form-item) {
  margin-bottom: 18px;
}

.login-form :deep(.el-form-item__label) {
  color: #344054;
  font-weight: 600;
}

.login-form :deep(.el-input__wrapper) {
  border-radius: 12px;
}

.login-button {
  width: 100%;
  height: 46px;
  margin-top: 4px;
  border: none;
  border-radius: 12px;
  background: linear-gradient(135deg, #2563eb, #06b6d4);
  font-weight: 700;
}

.register-line {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 4px;
  margin-top: 22px;
  color: #667085;
}

@media (max-width: 1080px) {
  .auth-shell {
    grid-template-columns: 1fr;
  }

  .hero-panel {
    display: none;
  }

  .login-panel {
    padding: 24px;
  }
}

@media (max-height: 720px) {
  .hero-panel {
    padding: 36px 54px;
  }

  .hero-content h2 {
    font-size: 34px;
  }

  .hero-content p {
    line-height: 1.7;
  }

  .feature-item {
    min-height: 112px;
    padding: 15px;
  }

  .login-card {
    padding: 28px;
  }
}
</style>
