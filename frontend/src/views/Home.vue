<template>
  <div>
    <Setup v-if="!configured" />
  </div>
</template>

<script>
import Setup from './Setup.vue';

export default {
  name: 'Home',

  components: {
    Setup,
  },

  data() {
    return {
      configured: false,
    }
  },
}
</script>

<style>
</style>
