<template>
  <div class="login-page">
    <section class="intro aa-panel">
      <p class="aa-kicker">AptAdapt</p>
      <h1>计算机组成原理个性化学习智能体</h1>
      <p>
        对话式画像、多智能体资源生成、学习路径规划和可视化评估，服务中国软件杯 A3 赛题演示。
      </p>
      <div class="feature-grid">
        <span>Profile Agent</span>
        <span>RAG 检索</span>
        <span>资源卡片</span>
        <span>学习评估</span>
      </div>
    </section>

    <section class="login-card aa-panel">
      <div class="card-head">
        <p class="aa-kicker">Welcome</p>
        <h2 class="aa-title">进入学习工作台</h2>
      </div>

      <el-tabs v-model="activeTab" class="tabs">
        <el-tab-pane label="登录" name="login">
          <el-form :model="loginForm" :rules="rules" ref="loginFormRef">
            <el-form-item prop="username">
              <el-input v-model="loginForm.username" placeholder="用户名" size="large" />
            </el-form-item>
            <el-form-item prop="password">
              <el-input v-model="loginForm.password" type="password" placeholder="密码" size="large" />
            </el-form-item>
            <el-form-item>
              <el-button type="primary" size="large" @click="handleLogin" :loading="loading" style="width: 100%">
                登录
              </el-button>
            </el-form-item>
          </el-form>
        </el-tab-pane>
        <el-tab-pane label="注册" name="register">
          <el-form :model="registerForm" :rules="rules" ref="registerFormRef">
            <el-form-item prop="username">
              <el-input v-model="registerForm.username" placeholder="用户名" size="large" />
            </el-form-item>
            <el-form-item prop="password">
              <el-input v-model="registerForm.password" type="password" placeholder="密码" size="large" />
            </el-form-item>
            <el-form-item>
              <el-button type="primary" size="large" @click="handleRegister" :loading="loading" style="width: 100%">
                注册
              </el-button>
            </el-form-item>
          </el-form>
        </el-tab-pane>
      </el-tabs>
    </section>
  </div>
</template>

<script setup>
import { ref, reactive } from 'vue'
import { useRouter } from 'vue-router'
import { useUserStore } from '../stores/user'
import { register as registerApi } from '../api/auth'
import { ElMessage } from 'element-plus'

const router = useRouter()
const userStore = useUserStore()
const activeTab = ref('login')
const loading = ref(false)

const loginForm = reactive({ username: '', password: '' })
const registerForm = reactive({ username: '', password: '' })
const rules = {
  username: [{ required: true, message: '请输入用户名', trigger: 'blur' }],
  password: [{ required: true, message: '请输入密码', trigger: 'blur' }]
}

const loginFormRef = ref(null)
const registerFormRef = ref(null)

async function handleLogin() {
  const valid = await loginFormRef.value.validate().catch(() => false)
  if (!valid) return
  loading.value = true
  try {
    await userStore.login(loginForm.username, loginForm.password)
    ElMessage.success('登录成功')
    router.push('/workspace')
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '登录失败')
  } finally {
    loading.value = false
  }
}

async function handleRegister() {
  const valid = await registerFormRef.value.validate().catch(() => false)
  if (!valid) return
  loading.value = true
  try {
    await registerApi(registerForm.username, registerForm.password)
    ElMessage.success('注册成功，请登录')
    activeTab.value = 'login'
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '注册失败')
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.login-page {
  width: min(1120px, calc(100% - 40px));
  min-height: 100vh;
  margin: 0 auto;
  display: grid;
  grid-template-columns: minmax(0, 1.1fr) 420px;
  align-items: center;
  gap: 22px;
}

.intro,
.login-card {
  padding: 34px;
}

.intro h1 {
  margin: 10px 0 16px;
  color: var(--aa-text);
  font-size: clamp(34px, 5vw, 64px);
  line-height: 1.08;
}

.intro p:last-of-type {
  max-width: 650px;
  color: #60788e;
  font-size: 16px;
  line-height: 1.8;
}

.feature-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 10px;
  margin-top: 24px;
}

.feature-grid span {
  padding: 12px;
  border-radius: 8px;
  color: #1b6c89;
  background: rgba(229, 249, 255, 0.78);
  border: 1px solid rgba(64, 184, 230, 0.18);
  font-weight: 700;
  text-align: center;
}

.card-head {
  margin-bottom: 18px;
}

@media (max-width: 900px) {
  .login-page {
    grid-template-columns: 1fr;
    padding: 20px 0;
  }

  .feature-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}
</style>
