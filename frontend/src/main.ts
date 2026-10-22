import { createPinia } from "pinia";
import { createApp } from "vue";

import App from "./App.vue";
import { reveal } from "./directives/reveal";
import router from "./router";
import "./design/base.css";
import "./design/landing.css";
import "./design/motion.css";

const app = createApp(App);
app.directive("reveal", reveal);
app.use(createPinia()).use(router).mount("#app");
