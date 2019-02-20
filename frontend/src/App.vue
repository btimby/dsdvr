<template>
  <v-app class="grey lighten-4">
    <v-container v-if="local.loggedIn === null" bg fill-height grid-list-md text-xs-center>
      <v-layout row wrap align-center>
        <v-flex>
          <v-progress-circular
            :size="50"
            color="primary"
            indeterminate
          ></v-progress-circular>
          <h1 style="display-3" class="mt-4">Loading...</h1>
        </v-flex>
      </v-layout>
    </v-container>
    <div class="mx-12" v-else-if="local.loggedIn === false">
      <Login @login="login" />
    </div>
    <div v-else>
      <Toolbar @logout="logout" :user="local.user"/>
      <v-content class="mx-4">
        <router-view />
        <MediaPlayer />
      </v-content>
    </div>
  </v-app>
</template>

<script>
import MediaPlayer from '@/components/MediaPlayer'
import Toolbar from '@/components/Toolbar';
import Login from '@/components/Login';

export default {
  name: 'App',

  components: {
    Login,
    MediaPlayer,
    Toolbar,
  },

  data() {
    return {
      local: {
        loggedIn: null,
        user: null,
      },
      store: this.$store.state,
    }
  },

  methods: {
    login() {
      this.$store.getUser()
        .then(r => {
          this.local.loggedIn = true;
          this.local.user = r.data;
        })
        .catch(e => {
          this.logout();
        });
    },

    logout() {
      this.local.loggedIn = false;
      this.local.user = null;
    },
  },

  mounted() {
    this.login();
  },
}
</script>
