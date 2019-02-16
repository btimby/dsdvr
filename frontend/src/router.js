import Vue from 'vue';
import Router from 'vue-router';
import Home from '@/views/Home';
import About from '@/views/About';
import Guide from '@/views/Guide';
import Recordings from '@/views/Recordings';
import Media from '@/views/Media';
import Login from '@/views/Login';

Vue.use(Router)

export default new Router({
  routes: [
    {
      path: '/',
      name: 'home',
      component: Home
    },
    {
      path: '/about',
      name: 'about',
      component: About
    },
    {
      path: '/guide',
      name: 'guide',
      component: Guide
    },
    {
      path: '/recordings',
      name: 'recordings',
      component: Recordings
    },
    {
      path: '/media',
      name: 'media',
      component: Media
    },
    {
      path: '/login',
      name: 'login',
      component: Login
    }
  ]
})
