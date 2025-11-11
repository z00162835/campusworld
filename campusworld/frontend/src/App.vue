<template>
  <div id="app">
    <el-header class="app-header" v-if="showHeader">
      <nav-bar />
    </el-header>
    <sidebar v-if="showSidebar" />
    <tab-bar v-if="showSidebar" />
    <div :class="['app-wrapper', { 'with-sidebar': showSidebar }]">
      <el-container class="app-container">
        <el-main class="app-main">
          <router-view v-if="route.path === '/login' || route.path === '/register' || route.path === '/profile'" />
          <div v-else-if="showSidebar" class="tab-content">
            <component
              v-if="activeTab"
              :is="getComponent(activeTab.component)"
              :key="activeTab.id"
            />
            <div v-else class="empty-tab">
              <p>选择一个菜单项开始</p>
            </div>
          </div>
        </el-main>
        
        <el-footer class="app-footer" v-if="showFooter">
          <footer-component />
        </el-footer>
      </el-container>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, watch } from 'vue'
import { useRoute } from 'vue-router'
import { useTabsStore } from '@/stores/tabs'
import Sidebar from '@/components/layout/Sidebar.vue'
import NavBar from '@/components/layout/NavBar.vue'
import TabBar from '@/components/layout/TabBar.vue'
import FooterComponent from '@/components/layout/Footer.vue'

// 动态导入组件
import Home from '@/views/Home.vue'
import Spaces from '@/views/spaces/Spaces.vue'
import Agents from '@/views/agents/Agents.vue'
import Discovery from '@/views/discovery/Discovery.vue'
import History from '@/views/history/History.vue'

const route = useRoute()
const tabsStore = useTabsStore()

// 定义不需要显示侧边栏、头部和底部的路由
const authRoutes = ['/login', '/register']

const showSidebar = computed(() => {
  return !authRoutes.includes(route.path)
})

const showHeader = computed(() => {
  return !authRoutes.includes(route.path)
})

const showFooter = computed(() => {
  return !authRoutes.includes(route.path)
})

const activeTab = computed(() => tabsStore.activeTab)

// 当路由变化到 /works 且没有激活的 tab 时，自动打开 Works tab
watch(
  () => route.path,
  (newPath) => {
    if (newPath === '/works' && !activeTab.value && showSidebar.value) {
      tabsStore.addTab({
        id: 'tab-works',
        title: 'Works',
        route: '/works',
        component: 'Home',
        closable: true
      })
    }
  },
  { immediate: true }
)

// 应用启动时，如果访问主页面，自动打开 Works tab
onMounted(() => {
  if ((route.path === '/' || route.path === '/works') && !activeTab.value && showSidebar.value) {
    tabsStore.addTab({
      id: 'tab-works',
      title: 'Works',
      route: '/works',
      component: 'Home',
      closable: true
    })
  }
})

const componentMap: Record<string, any> = {
  Home,
  Spaces,
  Agents,
  Discovery,
  History
}

const getComponent = (componentName: string) => {
  return componentMap[componentName] || null
}
</script>

<style scoped>
/* 使用全局样式，这里只保留组件特定的样式 */
</style>
