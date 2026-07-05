<template>
  <div class="auth-shell">
    <section class="hero-panel">
      <div class="hero-badge">第十五届中国软件杯 · A3</div>
      <div class="hero-logo">A3</div>
      <h1>Learning Agent</h1>
      <p class="hero-subtitle">基于讯飞星火 V3.5、SeeDance 与 RAG 的多智能体个性化学习系统</p>
      <div class="feature-list">
        <div v-for="item in features" :key="item.title" class="feature-item">
          <span>{{ item.icon }}</span>
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
          <span>欢迎登录</span>
          <el-tag effect="light">AI 学习助手</el-tag>
        </div>
        <p class="card-desc">登录后解锁对话式画像、多智能体资源生成、个性化路径规划和多模态答疑。</p>

        <el-form :model="form" label-position="top" @keyup.enter="login">
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
  { icon: "01", title: "对话式画像", desc: "免表单抽取 6 维动态学习画像" },
  { icon: "02", title: "多智能体资源", desc: "自动生成文档、练习、导图、代码与视频" },
  { icon: "03", title: "个性化路径", desc: "依据画像与教材构建阶梯式学习计划" },
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
  min-height: calc(100vh - 112px);
  display: grid;
  grid-template-columns: 1.1fr 0.9fr;
  gap: 0;
  overflow: hidden;
  border-radius: 30px;
  background: rgba(255, 255, 255, 0.66);
  box-shadow: 0 24px 80px rgba(15, 23, 42, 0.12);
}

.hero-panel {
  position: relative;
  padding: 58px;
  color: white;
  background:
    radial-gradient(circle at 20% 20%, rgba(125, 211, 252, 0.65), transparent 28%),
    radial-gradient(circle at 80% 16%, rgba(167, 139, 250, 0.7), transparent 30%),
    linear-gradient(135deg, #0f172a 0%, #1d4ed8 52%, #0891b2 100%);
}

.hero-badge {
  display: inline-flex;
  padding: 8px 14px;
  border: 1px solid rgba(255, 255, 255, 0.28);
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.16);
  backdrop-filter: blur(12px);
  font-size: 13px;
}

.hero-logo {
  display: grid;
  width: 74px;
  height: 74px;
  margin-top: 52px;
  place-items: center;
  border-radius: 24px;
  background: rgba(255, 255, 255, 0.18);
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.28);
  font-size: 24px;
  font-weight: 900;
}

.hero-panel h1 {
  margin: 24px 0 12px;
  font-size: 48px;
  letter-spacing: -1px;
}

.hero-subtitle {
  max-width: 560px;
  color: rgba(255, 255, 255, 0.82);
  font-size: 17px;
  line-height: 1.8;
}

.feature-list {
  display: grid;
  gap: 16px;
  margin-top: 54px;
}

.feature-item {
  display: flex;
  gap: 14px;
  padding: 18px;
  border: 1px solid rgba(255, 255, 255, 0.18);
  border-radius: 20px;
  background: rgba(255, 255, 255, 0.12);
  backdrop-filter: blur(16px);
}

.feature-item span {
  display: grid;
  width: 38px;
  height: 38px;
  flex: 0 0 auto;
  place-items: center;
  border-radius: 14px;
  background: rgba(255, 255, 255, 0.18);
  font-weight: 800;
}

.feature-item p {
  margin: 6px 0 0;
  color: rgba(255, 255, 255, 0.72);
}

.login-panel {
  display: grid;
  place-items: center;
  padding: 52px;
  background: linear-gradient(180deg, rgba(248, 250, 252, 0.92), rgba(240, 249, 255, 0.92));
}

.login-card {
  width: min(440px, 100%);
  padding: 36px;
  border: 1px solid rgba(148, 163, 184, 0.18);
  border-radius: 28px;
  background: rgba(255, 255, 255, 0.9);
  box-shadow: 0 20px 60px rgba(15, 23, 42, 0.12);
}

.card-title {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-size: 28px;
  font-weight: 850;
  color: #0f172a;
}

.card-desc {
  margin: 12px 0 30px;
  color: #64748b;
  line-height: 1.7;
}

.login-button {
  width: 100%;
  height: 46px;
  margin-top: 8px;
  border: none;
  background: linear-gradient(135deg, #2563eb, #06b6d4);
  font-weight: 700;
}

.register-line {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 4px;
  margin-top: 24px;
  color: #64748b;
}

@media (max-width: 960px) {
  .auth-shell {
    grid-template-columns: 1fr;
  }

  .hero-panel {
    display: none;
  }
}
</style>
