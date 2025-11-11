import { createRouter, createWebHistory } from 'vue-router'
import type { RouteRecordRaw } from 'vue-router'

const routes: RouteRecordRaw[] = [
  {
    path: '/',
    name: 'Home',
    redirect: '/works',
    meta: { title: '首页' }
  },
  {
    path: '/login',
    name: 'Login',
    component: () => import('@/views/auth/Login.vue'),
    meta: { title: '登录' }
  },
  {
    path: '/register',
    name: 'Register',
    component: () => import('@/views/auth/Register.vue'),
    meta: { title: '注册' }
  },
  {
    path: '/profile',
    name: 'Profile',
    component: () => import('@/views/user/Profile.vue'),
    meta: { title: '个人资料' }
  },
  {
    path: '/works',
    name: 'Works',
    component: () => import('@/views/Home.vue'),
    meta: { title: 'Works' }
  },
  {
    path: '/spaces',
    name: 'Spaces',
    component: () => import('@/views/spaces/Spaces.vue'),
    meta: { title: 'Spaces' }
  },
  {
    path: '/agents',
    name: 'Agents',
    component: () => import('@/views/agents/Agents.vue'),
    meta: { title: 'Agents' }
  },
  {
    path: '/discovery',
    name: 'Discovery',
    component: () => import('@/views/discovery/Discovery.vue'),
    meta: { title: 'Discovery' }
  },
  {
    path: '/history',
    name: 'History',
    component: () => import('@/views/history/History.vue'),
    meta: { title: 'History' }
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

// Navigation guard - 已禁用认证要求，直接允许访问
router.beforeEach((_to, _from, next) => {
  // 屏蔽登录要求，直接允许访问所有页面
  next()
})

export default router
