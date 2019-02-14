<template>
    <video
        id="videojs-player"
        class="video-js vjs-default-skin"
        v-bind:class="{ 'vjs-hide': hidden }"
        controls
        preload="auto"
        width="640"
        height="264"
    >
        <source src="" />
    </video>
</template>

<script>
import videojs from 'video.js';

export default {
    name: "video-player",

    data: () => ({
        hidden: true,
    }),

    ready: () => {
        const options = {
            liveui: true,
        };

        videojs("videojs-player", options, () => {
            // Player setup and ready.
        })
    }
}
</script>

<style>
.vjs-hide {
    display: none !important;
}
</style>
