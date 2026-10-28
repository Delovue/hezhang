import { createApp } from 'vue'
import { createPinia } from 'pinia'
import { ElAlert, ElButton, ElDialog, ElIcon, ElInput, ElProgress, ElSkeleton } from 'element-plus'
import 'element-plus/dist/index.css'
import './style.css'
import App from './App.vue'
import { router } from './router'
import { configureSession } from './api/client'
import { useSessionStore } from './stores/session'

const app = createApp(App)
app.use(createPinia())
const session = useSessionStore()
configureSession({ getToken: () => session.token, onUnauthorized: () => session.expire() })
app.use(router)
for (const component of [ElAlert, ElButton, ElDialog, ElIcon, ElInput, ElProgress, ElSkeleton]) app.use(component)
app.mount('#app')
