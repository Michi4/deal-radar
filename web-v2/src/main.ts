import { createApp } from 'vue';
import { createPinia } from 'pinia';
import App from './App.vue';
import router from './router';
import './styles/tokens.css';
import { useUi } from './stores/ui';

const app = createApp(App);
app.use(createPinia());
app.use(router);
const ui = useUi();
ui.initTheme();
app.mount('#app');
