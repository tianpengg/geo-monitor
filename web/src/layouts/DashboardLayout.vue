<script setup lang="ts">
import { useWorkspaceContext } from '../composables/workspaceContext'
import { originNote, time } from '../utils/presentation'
import UiIcon from '../components/ui/UiIcon.vue'
import DashboardFilters from '../components/dashboard/DashboardFilters.vue'

const { currentUser, busy, loading, error, dataError, success, site, updatedAt, applied, analyticalTab, mainContent, navigation, current, zone, dateRange, logout, navigate, refresh, selectDays, tab } = useWorkspaceContext()
function setMainContent(element: unknown) {
  mainContent.value = element instanceof HTMLElement ? element : null
}
</script>

<template>
  <div class="app-layout">
    <aside class="sidebar" aria-label="后台导航">
      <a class="brand" href="#" @click.prevent="navigate(site ? 'overview' : 'site')"
        ><UiIcon name="circles-relation" />geo-monitor</a
      >
      <button class="workspace" @click="navigate('site')">
        <UiIcon name="world" /><span
          ><small>当前官网</small
          ><strong :title="site?.domain">{{ site?.domain ?? '尚未配置' }}</strong></span
        >
      </button>
      <p class="nav-caption">工作空间</p>
      <nav class="nav">
        <button
          v-for="item in navigation"
          :key="item.id"
          class="nav-button"
          :class="{ active: tab === item.id }"
          :aria-current="tab === item.id ? 'page' : undefined"
          :disabled="!site && !['site', 'rules'].includes(item.id)"
          @click="navigate(item.id)"
        >
          <UiIcon :name="item.icon" /><span>{{ item.name }}</span>
        </button>
      </nav>
      <div class="sidebar-bottom">
        <div class="source-note">
          <strong>源站日志观测</strong>Nginx Combined · 只读采集<br />每 30 秒更新访问数据
        </div>
        <div class="administrator">
          <UiIcon name="shield-check" /><span>{{ currentUser }}<small>管理员</small></span
          ><button
            class="logout-button"
            :disabled="busy"
            @click="logout"
            aria-label="退出登录"
            title="退出登录"
          >
            <UiIcon name="arrow-right" />
          </button>
        </div>
      </div>
    </aside>
    <main :ref="setMainContent" class="app-main" tabindex="-1">
      <div class="topbar">
        <div class="breadcrumbs">
          <span>工作空间</span><UiIcon name="chevron-right" /><strong>{{ current.name }}</strong>
        </div>
        <div class="topbar-right">
          <span>{{ zone }}</span
          ><button class="refresh-button" :disabled="loading || busy || !site" @click="refresh">
            <UiIcon name="refresh" />{{ loading ? '正在更新' : '刷新数据' }}</button
          ><button class="mobile-logout" :disabled="busy" @click="logout">退出</button>
        </div>
      </div>
      <header class="page-header">
        <div>
          <h1>{{ current.name }}</h1>
          <p class="page-intro">{{ current.description }}</p>
        </div>
        <div v-if="analyticalTab" class="range-row">
          <div class="segments" role="group" aria-label="统计时间范围">
            <button
              v-for="days in [1, 7, 30]"
              :key="days"
              :aria-pressed="applied.days === days && !applied.start"
              @click="selectDays(days)"
            >
              {{ days === 1 ? '今天' : `近 ${days} 天` }}
            </button>
          </div>
          <span class="date-range">{{ dateRange }}</span>
        </div>
      </header>
      <p v-if="error" class="notice danger" role="alert">{{ error }}</p>
      <p v-if="success" class="notice success" role="status">{{ success }}</p>
      <div v-if="dataError" class="notice warning" role="alert">
        <div>
          <strong>数据更新失败</strong>
          <p>
            {{ dataError
            }}<span v-if="updatedAt">；上次成功更新：{{ time(updatedAt, zone) }}。</span>
            当前状态需重新确认。
          </p>
        </div>
        <button class="secondary-button" :disabled="loading" @click="refresh">重试更新</button>
      </div>
      <DashboardFilters />

      <slot />
      <footer class="footer">
        <span><UiIcon name="info-circle" />{{ originNote }}</span
        ><span v-if="updatedAt">最后更新 {{ time(updatedAt, zone) }}</span>
      </footer>
    </main>
  </div>
</template>
