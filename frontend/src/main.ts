import { createApp } from 'vue'
import { createPinia } from 'pinia'
import i18n from './locales'

import App from './App.vue'
import router from './router'
import './styles/index.css'
import { initTheme } from './utils/theme'

// Initialize theme
initTheme()

const app = createApp(App)

app.use(createPinia())
app.use(router)
app.use(i18n)

app.mount('#app')
