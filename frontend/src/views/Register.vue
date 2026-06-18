<template>
  <div class="register-page">
    <!-- 背景装饰 -->
    <div class="bg-shapes">
      <div class="shape shape-1"></div>
      <div class="shape shape-2"></div>
      <div class="shape shape-3"></div>
    </div>

    <!-- 主卡片 -->
    <div class="register-wrapper">
      <!-- 左侧：品牌区域（复用登录页设计） -->
      <div class="brand-panel">
        <div class="brand-content">
          <div class="brand-icon">
            <svg viewBox="0 0 80 80" fill="none" xmlns="http://www.w3.org/2000/svg">
              <rect width="80" height="80" rx="20" fill="url(#g1)" />
              <path d="M22 50c0-10 8-18 18-18s18 8 18 18" stroke="#fff" stroke-width="5" stroke-linecap="round" />
              <circle cx="40" cy="28" r="8" fill="#fff" />
              <defs><linearGradient id="g1" x1="0" y1="0" x2="80" y2="80"><stop stop-color="#1d4ed8"/><stop offset="1" stop-color="#7c3aed"/></linearGradient></defs>
            </svg>
          </div>
          <h1 class="brand-title">汇智海洋</h1>
          <p class="brand-subtitle">创建您的账号</p>
          <div class="brand-features">
            <div class="feature-item">
              <span class="feature-dot"></span>
              <span>注册后等待管理员审核</span>
            </div>
            <div class="feature-item">
              <span class="feature-dot"></span>
              <span>审核通过即可登录使用</span>
            </div>
          </div>
        </div>
      </div>

      <!-- 右侧：注册表单 -->
      <div class="form-panel">
        <div class="form-content">
          <h2 class="form-title">用户注册</h2>
          <p class="form-desc">填写信息提交注册申请</p>

          <el-form :model="form" @submit.prevent="handleRegister" class="login-form">
            <div class="input-row">
              <div class="input-group" style="flex:1">
                <label class="input-label">用户名</label>
                <el-input v-model="form.username" placeholder="请输入用户名" size="large" />
              </div>
              <div class="input-group" style="flex:1">
                <label class="input-label">姓名</label>
                <el-input v-model="form.name" placeholder="请输入真实姓名" size="large" />
              </div>
            </div>
            <div class="input-group">
              <label class="input-label">密码</label>
              <el-input v-model="form.password" type="password" placeholder="请输入密码" size="large" show-password />
            </div>
            <div class="input-row">
              <div class="input-group" style="flex:1">
                <label class="input-label">工号</label>
                <el-input v-model="form.employee_id" placeholder="请输入工号" size="large" />
              </div>
              <div class="input-group" style="flex:1">
                <label class="input-label">所属班组</label>
                <el-input v-model="form.team" placeholder="如：维修一组" size="large" />
              </div>
            </div>
            <el-button type="primary" size="large" @click="handleRegister" :loading="loading" class="login-btn">
              注 册
            </el-button>
          </el-form>

          <p class="register-link">
            已有账号？<router-link to="/login">去登录</router-link>
          </p>
        </div>
      </div>
    </div>

    <!-- 底部版权 -->
    <div class="login-footer">
      <span>&copy; 2026 汇智海洋 · 设备检修知识检索与作业系统</span>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useAuthStore } from '@/stores/auth'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'

const authStore = useAuthStore()
const router = useRouter()
const loading = ref(false)
const form = ref({ username: '', password: '', name: '', employee_id: '', team: '' })

async function handleRegister() {
  loading.value = true
  try {
    await authStore.register(form.value)
    ElMessage.success('注册成功，请等待管理员审核')
    router.push('/login')
  } catch {}
  finally { loading.value = false }
}
</script>

<style scoped>
/* ==================== 与登录页共享的样式 ==================== */
.register-page {
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
  min-height: 100vh;
  background: linear-gradient(135deg, #0f172a 0%, #1e3a5f 40%, #1a1a2e 100%);
  position: relative;
  overflow: hidden;
}
.bg-shapes { position: absolute; inset: 0; pointer-events: none; }
.shape {
  position: absolute;
  border-radius: 50%;
  opacity: 0.08;
  filter: blur(60px);
}
.shape-1 { width: 600px; height: 600px; background: #3b82f6; top: -200px; right: -100px; }
.shape-2 { width: 500px; height: 500px; background: #8b5cf6; bottom: -150px; left: -150px; }
.shape-3 { width: 400px; height: 400px; background: #06b6d4; top: 30%; left: 40%; }

.register-wrapper {
  display: flex;
  width: 960px;
  min-height: 540px;
  background: rgba(255,255,255,0.97);
  border-radius: 20px;
  box-shadow: 0 25px 80px rgba(0,0,0,0.35), 0 0 0 1px rgba(255,255,255,0.1) inset;
  overflow: hidden;
  z-index: 1;
  backdrop-filter: blur(10px);
}

/* 左侧品牌面板 */
.brand-panel {
  width: 420px;
  background: linear-gradient(160deg, #1d4ed8 0%, #5b21b6 100%);
  display: flex;
  align-items: center;
  justify-content: center;
  position: relative;
  overflow: hidden;
}
.brand-panel::before {
  content: '';
  position: absolute;
  width: 300px; height: 300px;
  background: rgba(255,255,255,0.05);
  border-radius: 50%;
  top: -60px; right: -60px;
}
.brand-panel::after {
  content: '';
  position: absolute;
  width: 200px; height: 200px;
  background: rgba(255,255,255,0.06);
  border-radius: 50%;
  bottom: -40px; left: -40px;
}
.brand-content {
  text-align: center;
  color: #fff;
  position: relative;
  z-index: 1;
  padding: 40px;
}
.brand-icon { margin: 0 auto 24px; width: 80px; height: 80px; }
.brand-title {
  font-size: 32px; font-weight: 800; letter-spacing: 6px; margin: 0 0 12px;
}
.brand-subtitle {
  font-size: 15px; opacity: 0.85; margin: 0 0 36px; letter-spacing: 2px;
}
.brand-features {
  text-align: left; display: inline-flex; flex-direction: column; gap: 14px;
}
.feature-item {
  display: flex; align-items: center; gap: 10px; font-size: 14px; opacity: 0.9;
}
.feature-dot {
  width: 8px; height: 8px; background: #60a5fa; border-radius: 50%;
  flex-shrink: 0; box-shadow: 0 0 8px #60a5fa;
}

/* 右侧表单 */
.form-panel {
  flex: 1; display: flex; align-items: center; justify-content: center; padding: 40px;
}
.form-content { width: 400px; }
.form-title {
  font-size: 26px; font-weight: 700; color: #1e293b; margin: 0 0 8px;
}
.form-desc {
  font-size: 14px; color: #94a3b8; margin: 0 0 24px;
}

.input-row { display: flex; gap: 12px; }
.input-group { margin-bottom: 16px; }
.input-label {
  display: block; font-size: 13px; font-weight: 600; color: #475569; margin-bottom: 6px;
}
.input-group :deep(.el-input__wrapper) {
  border-radius: 10px;
  box-shadow: 0 0 0 1px #e2e8f0 inset;
  transition: all 0.25s;
  padding: 2px 12px;
}
.input-group :deep(.el-input__wrapper:hover) {
  box-shadow: 0 0 0 1px #93c5fd inset;
}
.input-group :deep(.el-input__wrapper.is-focus) {
  box-shadow: 0 0 0 2px #3b82f6 inset;
}

.login-btn {
  width: 100%; height: 46px; border-radius: 10px; font-size: 16px;
  font-weight: 600; letter-spacing: 6px; margin-top: 8px;
  background: linear-gradient(135deg, #1d4ed8, #5b21b6);
  border: none; transition: all 0.3s;
}
.login-btn:hover {
  transform: translateY(-1px);
  box-shadow: 0 8px 25px rgba(29,78,216,0.4);
}
.login-btn:active { transform: translateY(0); }

.register-link {
  text-align: center; font-size: 14px; color: #94a3b8; margin-top: 24px;
}
.register-link a {
  color: #3b82f6; text-decoration: none; font-weight: 500; transition: color 0.2s;
}
.register-link a:hover { color: #1d4ed8; }

.login-footer {
  position: absolute; bottom: 20px; font-size: 12px;
  color: rgba(255,255,255,0.35); z-index: 1; letter-spacing: 1px;
}

@media (max-width: 768px) {
  .register-wrapper { width: 92vw; flex-direction: column; min-height: auto; }
  .brand-panel { width: 100%; padding: 30px 20px; }
  .brand-title { font-size: 24px; letter-spacing: 4px; }
  .brand-features { display: none; }
  .form-panel { padding: 30px 24px; }
  .form-content { width: 100%; }
}
</style>
