<template>
  <error-boundary>
    <div id="app">
      <el-header class="app-header" v-if="showHeader">
        <nav-bar />
      </el-header>
      <tab-bar v-if="showAppChrome" />
      <div class="app-wrapper">
        <el-container class="app-container">
          <el-main class="app-main">
            <router-view v-if="isAuthRoute" />
            <div
              v-else-if="showAppChrome"
              :class="['tab-content', { 'tab-content--flush': isWorksTab }]"
            >
              <component
                v-if="activeTab"
                :is="getComponent(activeTab.component)"
                :key="activeTab.id"
              />
              <div v-else class="empty-tab">
                <p>Welcome to CampusWorld</p>
              </div>
            </div>
          </el-main>

          <el-footer class="app-footer" v-if="showFooter">
            <footer-component />
          </el-footer>
        </el-container>
      </div>
    </div>
  </error-boundary>
</template>

<script setup lang="ts">
import { computed, onMounted, watch, defineAsyncComponent, onBeforeUnmount } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useTabsStore } from '@/stores/tabs'
import { DEFAULT_APP_ROUTE, isAppTabRoute } from '@/stores/appTabs'
import { useAppTabs } from '@/composables/useAppTabs'
import ErrorBoundary from '@/components/common/ErrorBoundary.vue'
import NavBar from '@/components/layout/NavBar.vue'
import TabBar from '@/components/layout/TabBar.vue'
import FooterComponent from '@/components/layout/Footer.vue'

const WorldInteractionView = defineAsyncComponent(() => import('@/views/WorldInteractionView.vue'))
const Spaces = defineAsyncComponent(() => import('@/views/spaces/Spaces.vue'))
const Agents = defineAsyncComponent(() => import('@/views/agents/Agents.vue'))
const Discovery = defineAsyncComponent(() => import('@/views/discovery/Discovery.vue'))
const History = defineAsyncComponent(() => import('@/views/history/History.vue'))
const Profile = defineAsyncComponent(() => import('@/views/user/Profile.vue'))

const route = useRoute()
const router = useRouter()
const tabsStore = useTabsStore()
const { syncRouteToTab } = useAppTabs()

const authRoutes = ['/login', '/register']

const isAuthRoute = computed(() => authRoutes.includes(route.path))

const showAppChrome = computed(() => !isAuthRoute.value)

const showHeader = computed(() => !isAuthRoute.value)

const showFooter = computed(() => !isAuthRoute.value)

const activeTab = computed(() => tabsStore.activeTab)

const isWorksTab = computed(() => activeTab.value?.route === '/works')

watch(
  () => route.path,
  newPath => {
    if (showAppChrome.value && isAppTabRoute(newPath)) {
      syncRouteToTab(newPath)
    }
  },
  { immediate: true },
)

onMounted(() => {
  if (showAppChrome.value && !activeTab.value) {
    syncRouteToTab(isAppTabRoute(route.path) ? route.path : DEFAULT_APP_ROUTE)
  }
})

const handleSessionExpired = (event: Event) => {
  const detail = (event as CustomEvent<{ reason?: string }>).detail
  if (!isAuthRoute.value) {
    const redirect = route.fullPath && route.fullPath !== '/login'
      ? `?redirect=${encodeURIComponent(route.fullPath)}`
      : ''
    router.replace(`/login${redirect}`)
  }
  if (detail?.reason) {
    console.info(`Session ended: ${detail.reason}`)
  }
}

onMounted(() => {
  window.addEventListener('auth-session-ended', handleSessionExpired)
})

onBeforeUnmount(() => {
  window.removeEventListener('auth-session-ended', handleSessionExpired)
})

const componentMap: Record<string, unknown> = {
  WorldInteractionView,
  Spaces,
  Agents,
  Discovery,
  History,
  Profile,
}

const getComponent = (componentName: string) => {
  return componentMap[componentName] || null
}
</script>

<style scoped>
/* App-specific overrides live in global layout.css */
</style>
