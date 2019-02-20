<template>
    <div
         v-bind:style="{ color: color }"
         v-bind:title="`There are ${running.length} running and ${errored.length} errored recordings`"
         class="mx-2">
        <svg
            xmlns="http://www.w3.org/2000/svg"
            id="recording-button-icon"
            viewBox="0 0 60 60"
            version="1.0"
            y="0"
            x="0"
            width="32px"
            height="32px">
            <path
                  id="path1711"
                  style="stroke-linejoin:round;color:#000000;stroke:#ffffff;stroke-linecap:round;stroke-width:7.127;fill:none"
                  d="m14.5 20.805a22.203 22.203 0 1 1 -44.406 0 22.203 22.203 0 1 1 44.406 0z"
                  transform="matrix(-1.14 3.5598e-7 -3.5598e-7 -1.14 21.218 53.719)"/>
            <path
                  id="path1710"
                  :style="`stroke-linejoin:round;fill-rule:evenodd;color:#000000;stroke:#000000;stroke-linecap:round;stroke-width:2.7412;fill:${color}`"
                  transform="matrix(-1.14 3.5598e-7 -3.5598e-7 -1.14 21.218 53.719)"
                  d="m14.5 20.805c0 12.256-9.9471 22.203-22.203 22.203s-22.203-9.947-22.203-22.203 9.947-22.202 22.203-22.202c12.256-0.0004 22.203 9.9465 22.203 22.202z"/>
            <text
                xml:space="preserve"
                style="font-style:normal;font-weight:normal;font-size:20.99726486px;line-height:1.25;font-family:sans-serif;letter-spacing:0px;word-spacing:0px;fill:#000000;fill-opacity:1;stroke:none;stroke-width:0.52493167">
                <tspan
                       x="23"
                       y="38"
                       style="font-size:24px;stroke-width:0.52493167">
                    {{ running.length + errored.length }}
                </tspan>
            </text>
        </svg>
    </div>
</template>

<script>
  export default {
    name: "RecordingButton",

    data() {
        return {
            local: {
                recordings: [],
                recordingInterval: null,
            },
            store: this.$store.state,
        }
    },

    mounted() {
        this.getRecordings();
        this.local.recordingIterval = setInterval(this.getRecordings, 10000);
    },

    beforeDestroy() {
        clearInterval(this.local.recordingIterval);
    },

    methods: {
        getRecordings() {
            // Don't fetch ajax data if a video is playing...
            if (this.store.nowPlaying)
                return;

            this.$store.getRecordings()
                .then(r => {
                    this.local.recordings = r.data;
                });
        }
    },

    computed: {
        errored: function() {
            const errored = [];

            this.local.recordings.forEach((task) => {
                if (task.status !== 'error')
                    return;
                errored.push(task);
            });

            return errored;
        },

        running: function() {
            const running = [];

            this.local.recordings.forEach((task) => {
                if (task.status !== 'recording')
                    return;
                running.push(task);
            });

            return running;
        },

        color: function() {
            if (this.running.length) {
                if (this.errored.length) {
                    return 'yellow';
                } else {
                    return 'red';
                }                
            } else if (this.errored.length) {
                return 'yellow';
            }
            return 'grey';
        }
    },
  }
</script>

<style scoped>
div {
    color: #91dc5a;
}
</style>
