<script setup lang="ts">
import { provide } from 'vue'
import { useWorkspace } from './composables/useWorkspace'
import { workspaceKey } from './composables/workspaceContext'
import DashboardLayout from './layouts/DashboardLayout.vue'
import UiIcon from './components/ui/UiIcon.vue'
import LoginView from './views/LoginView.vue'
import OverviewView from './views/OverviewView.vue'
import VisitsView from './views/VisitsView.vue'
import PagesView from './views/PagesView.vue'
import InventoryView from './views/InventoryView.vue'
import HealthView from './views/HealthView.vue'
import SiteView from './views/SiteView.vue'
import RulesView from './views/RulesView.vue'

const workspace = useWorkspace()
provide(workspaceKey, workspace)
const { ready, loggedIn, tab } = workspace
</script>

<template>
  <div v-if="!ready" class="session-loading" role="status">
    <UiIcon name="circles-relation" /><strong>geo-monitor</strong>
    <p>正在读取登录状态…</p>
  </div>
  <LoginView v-else-if="!loggedIn" />
  <DashboardLayout v-else>
    <OverviewView v-if="tab === 'overview'" />
    <VisitsView v-else-if="tab === 'details'" />
    <PagesView v-else-if="tab === 'pages'" />
    <InventoryView v-else-if="tab === 'inventory'" />
    <HealthView v-else-if="tab === 'health'" />
    <SiteView v-else-if="tab === 'site'" />
    <RulesView v-else-if="tab === 'rules'" />
  </DashboardLayout>
</template>
