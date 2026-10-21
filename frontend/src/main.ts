import { createApp } from 'vue'
import { createPinia } from 'pinia'
import App from './App.vue'
import router from './router'
import './styles/main.css'

const app = createApp(App).use(createPinia()).use(router)
// Resolve authentication before mounting layouts which fetch protected resources.
void router.isReady().then(() => app.mount('#app'))
