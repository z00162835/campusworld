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
    meta: { title: '个人资料', requiresAuth: true }
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
  },
  {
    path: '/:pathMatch(.*)*',
    name: 'NotFound',
    component: () => import('@/views/NotFound.vue'),
    meta: { title: '404' }
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

// Navigation guard - check authentication
router.beforeEach((to, _from, next) => {
  if (to.meta.requiresAuth && !localStorage.getItem('access_token')) {
    next('/login')
  } else {
    next()
  }
})

export default router
