<script setup lang="ts">
import { useWorkspaceContext } from '../composables/workspaceContext'
import UiIcon from '../components/ui/UiIcon.vue'
import UiInput from '../components/ui/UiInput.vue'

const { sessionChecked, username, password, busy, error, bootstrap, login } =
  useWorkspaceContext()
</script>

<template>
  <div class="login-layout">
    <span class="brand login-brand"><UiIcon name="circles-relation" />geo-monitor</span>
    <section class="panel login-panel">
      <span class="eyebrow">官网 AI 爬虫监测</span>
      <h1>欢迎回来</h1>
      <p class="login-intro">登录管理后台，查看官网的 AI 爬虫访问。</p>
      <p v-if="error" class="notice danger" role="alert">{{ error }}</p>
      <form v-if="sessionChecked" novalidate class="stack-form" @submit.prevent="login">
        <label
          >用户名<UiInput
            v-model="username"
            aria-label="用户名"
            autocomplete="username"
            required
            :disabled="busy"
        /></label>
        <label
          >密码<UiInput
            v-model="password"
            aria-label="密码"
            type="password"
            autocomplete="current-password"
            required
            :disabled="busy"
        /></label>
        <button class="primary-button" :disabled="busy">
          {{ busy ? '正在登录…' : '登录管理后台' }}<UiIcon name="arrow-right" />
        </button>
      </form>
      <button v-else class="primary-button" :disabled="busy" @click="bootstrap">重新连接</button>
      <p class="login-foot"><UiIcon name="shield-check" />单管理员 · 源站日志 · 隐私优先</p>
    </section>
    <p class="login-copyright">看见 AI 对你的网站的访问。</p>
  </div>
</template>
