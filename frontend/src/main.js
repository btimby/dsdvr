import Vue from 'vue'
import './plugins/vuetify'
import './plugins/vuetify'
import App from './App.vue'
import Store from './store'
import router from './router'

Vue.config.productionTip = false

Vue.mixin({
  beforeCreate() {
    const options = this.$options;
    // Push store down to all components...
    if (options.store) {
      this.$store = options.store;
    } else if (options.parent && options.parent.$store) {
      this.$store = options.parent.$store;
    }
  }
});

const store = new Store();

window.App = new Vue({
  store,
  router,
  render: h => h(App)
}).$mount('#app')
