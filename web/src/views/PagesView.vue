<script setup lang="ts">
import { useWorkspaceContext } from '../composables/workspaceContext'
import PagesPanel from '../components/dashboard/PagesPanel.vue'

const { loading, pages, pageDetail, selectedPath, pageOffset, zone, openPage, openRecords, changePage, closePage } = useWorkspaceContext()
</script>

<template>
  <PagesPanel
    :data="pages"
    :detail="pageDetail"
    :selected="selectedPath"
    :timezone="zone"
    :loading="loading"
    :offset="pageOffset"
    @select="openPage"
    @close="closePage()"
    @records="openRecords"
    @page="changePage"
  />
</template>
