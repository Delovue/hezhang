import { createRouter, createWebHistory } from 'vue-router'
import { useSessionStore } from './stores/session'
import { safeRedirect } from './utils/activity'

export const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', redirect: '/activities' },
    { path: '/login', component: () => import('./views/AuthView.vue'), meta: { title: '登录' } },
    { path: '/register', component: () => import('./views/AuthView.vue'), meta: { title: '注册' } },
    { path: '/activities', component: () => import('./views/ActivitiesView.vue'), meta: { protected: true, title: '我的活动' } },
    { path: '/activities/:id', component: () => import('./views/ActivityDetailView.vue'), meta: { protected: true, title: '活动详情' } },
    { path: '/:pathMatch(.*)*', component: () => import('./views/NotFoundView.vue'), meta: { title: '页面不存在' } },
  ],
  scrollBehavior: () => ({ top: 0 }),
})

router.beforeEach((to) => {
  const session = useSessionStore()
  if (to.meta.protected && !session.authenticated && !session.expired) {
    return { path: '/login', query: { redirect: to.path } }
  }
  if (session.authenticated && (to.path === '/login' || to.path === '/register')) return safeRedirect(to.query.redirect)
})
router.afterEach((to) => { document.title = `${String(to.meta.title || '合账')} · 合账` })
