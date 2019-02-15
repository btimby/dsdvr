<template>
    <div :class="{ 'vjs-hide': local.hidden }" id="player-overlay">
        <video
            id="videojs-player"
            class="video-js vjs-default-skin vjs-big-play-centered"
            controls
            preload="auto"
            width="80%"
            height="80%">
        </video>
    </div>
</template>

<script>
import axios from 'axios';
import _ from 'lodash';

/* Video player and plugins. */
import videojs from 'video.js';
import videojsDock from 'videojs-dock';
import vjsSeekButtons from 'videojs-seek-buttons';
import vjsStopButton from 'videojs-stop-button';
import vjsUpNext from 'videojs-upnext';
import vjsDvr from 'videojs-dvr';

/* Video player styles. */
import 'video.js/dist/video-js.css';
import 'videojs-dock/dist/videojs-dock.css';
import 'videojs-seek-buttons/dist/videojs-seek-buttons.css';
import 'videojs-upnext/dist/videojs-upnext.css';
import 'videojs-dvr/dist/videojs-dvr.css';

export default {
    name: "VideoPlayer",

    data() {
        return {
            local: {
                hidden: true,
                player: null,
            },
            store: this.$store.state,
        }
    },

    watch: {
        // Wait for new stream to be accessible. Then modify the datum bound
        // to the video player src attribute.
        'store.nowPlaying': function (media, oldMedia) {
            // Set poster and unhide player.
            this.local.player.poster(`/api/media/${media.id}/poster.jpg`);
            this.local.hidden = false;

            // Wait for the stream to become available.
            this.testStreamUrl(media);
        }
    },

    methods: {
        testStreamUrl(media) {
            axios.head(media.streamUrl)
                .then(r => {
                    // Stream is available, start playing...
                    let src = {
                        type: 'application/x-mpegUrl',
                        src: media.streamUrl,
                    };
                    this.local.player.src(src);

                    // NOTE: this is kinda hacky, but setting currentTime()
                    // before or after play() does not work.
                    /* this.local.player.one('timeupdate', () => {
                        
                    }); */

                    // Start playback in lieu of autoplay...
                    this.local.player.play().then(() => {
                        this.local.player.currentTime(media.streamCursor || 0);
                    });
                })
                .catch(e => {
                    setTimeout(function() {
                        this.testStreamUrl(media);
                    }.bind(this), 3000);
                });
        }
    },

    mounted() {
        const options = {
            liveui: true,
            aspectRatio: '16:9',
            fluid: true,
        };

        const player = this.local.player = videojs("videojs-player", options, () => {
            player.on('timeupdate', _.throttle(() => {
                const currentTime = player.currentTime();
                const mediaId = this.store.nowPlaying.id;

                console.log(currentTime);
                axios.patch(`/api/media/${mediaId}/stream/`, { cursor: currentTime });
            }, 4000));

            player.dock({
                title: this.local.nowPlaying.title,
                description: this.local.nowPlaying.desc,
            });

            // player.stopButton();
            player.seekButtons({
                forward: 30,
                back: 10
            });

            player.upnext({
                timeout: 5000,
                headText: 'Up Next',
                cancelText: 'Cancel',
                getTitle: () => {
                    return 'Next video title...';
                },
                next: () => {
                    // ...
                }
            });

            player.dvr();
        });
    }
}
</script>

<style scoped>

.vjs-hide {
    display: none;
}

#player-overlay {
  position: fixed; /* Sit on top of the page content */
  width: 100%; /* Full width (cover the whole page) */
  height: 100%; /* Full height (cover the whole page) */
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background-color: rgba(0,0,0,0.9); /* Black background with opacity */
  z-index: 4; /* Specify a stack order in case you're using a different order for other elements */
  cursor: pointer; /* Add a pointer on hover */

  padding: 20px;

  text-align: center;
  vertical-align: middle;
}

/* Make "poster" (first frame) fill player. */
video[poster]{
    object-fit: cover;
}
.vjs-poster {
    background-size: cover;
    background-position: inherit;
}
</style>
