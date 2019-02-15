<template>
    <div :class="{ 'vjs-hide': local.hidden }" id="player-overlay">
        <video
            id="videojs-player"
            class="video-js vjs-default-skin"
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

/* Video player and plugin styles. */
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
            // media is set to null when playback stops.
            if (media === null)
                return;

            // Set poster and unhide player.
            this.local.player.poster(`/api/media/${media.id}/frame0.jpg`);
            // Start spinner.
            this.local.player.addClass('vjs-waiting');
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
                    const src = {
                        type: 'application/x-mpegUrl',
                        src: media.streamUrl,
                    };

                    const mediaTitle = media.title;
                    const mediaDesc = media.subtitle || media.desc;

                    this.local.player.dock({
                        title: mediaTitle,
                        description: mediaDesc,
                    });

                    // Stop spinner and set media URL.
                    this.local.player.removeClass('vjs-waiting');
                    this.local.player.src(src);

                    // Start playback in lieu of autoplay, shortly after
                    // playback starts set current time to resume location or 0
                    this.local.player.play().then(() => {
                        // TODO: Here we can check if cursor is near duration
                        // we just need an accurate duration from the API. If
                        // cursor _is_ near duration, we should restart
                        // playback.
                        this.local.player.currentTime(media.streamCursor || 0);
                    });
                })
                .catch(e => {
                    // TODO: Need to count our retries and eventually report
                    // an error.
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
            // NOTE: big play button looks dumb behind spinner.
            bigPlayButton: false,
        };

        const player = this.local.player = videojs("videojs-player", options, function() {
            player.on('timeupdate', _.throttle(() => {
                // NOTE: This can be called after playback has ended, in which
                // case nowPlaying will be null.
                if (this.store.nowPlaying === null)
                    return;

                const currentTime = player.currentTime();
                const mediaId = this.store.nowPlaying.id;
                this.$store.updateStreamCursor(mediaId, currentTime);
            }, 4000));

            player.on('ended', () => {
                console.log('Ended.');
                this.local.hidden = true;
                this.$store.stopVideo();
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
        }.bind(this));
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

/* Hide big play button */
.video-js .vjs-big-play-button {
    display: none;
}
.video-js .vjs-control-bar {
    display: flex;
}

</style>
