<template>
  <v-app class="grey lighten-4">
    <Toolbar />

    <v-content class="mx-4">
      <router-view />
      <MediaPlayer />
    </v-content>
  </v-app>
</template>

<script>
import MediaPlayer from '@/components/MediaPlayer'
import Toolbar from '@/components/Toolbar';

export default {
  name: 'App',

  components: {
    MediaPlayer,
    Toolbar,
  },

  data() {
    return {
      local: { },

      store: this.$store.state,
    }
  },
}
</script>
