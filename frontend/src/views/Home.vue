<template>
  <div>
    <TunerScan />
    <GuideDownload />
    <Setup v-if="!configured" />
  </div>
</template>

<script>
import Setup from '@/components/Setup.vue';
import TunerScan from '@/components/TunerScan';
import GuideDownload from '@/components/GuideDownload';

export default {
  name: 'Home',

  components: {
    Setup,
    TunerScan,
    GuideDownload,
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
