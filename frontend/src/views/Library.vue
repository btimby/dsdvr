<template>
  <div>
    <h1>Library: {{ local.library.name }}</h1>

    <v-container fluid grid-list-md>
        <!-- TODO: don't need a v-data-iterator here, could do with grid //-->
        <v-data-iterator
        :items="local.media"
        :pagination="local.pagination"
        :total-items="local.media.length"
        content-tag="v-layout"
        hide-actions
        row
        wrap
        >
        <v-flex
            slot="item"
            slot-scope="props"
            xs12
            sm6
            md4
            lg2
        >
            <v-card>
            <v-card-title><h4 class="text-no-wrap text-truncate">{{ props.item.title }}</h4></v-card-title>
            <div style="text-align: center" class="mb-4">
                <div class="bounding-box"
                     style="display: table; margin: 0 auto"
                     v-bind:style="{ backgroundImage: `url(${(props.item.icon || '/static/images/poster.jpg')})` }">
                    <img
                         @click.stop="playVideo(props.item)"
                         src="/static/images/play-button.png"
                         class="play-button">
                </div>
            </div>
            <v-divider></v-divider>
            <v-list dense>
                <v-list-tile>
                <v-list-tile-content>Title:</v-list-tile-content>
                <v-list-tile-content class="align-end text-no-wrap text-truncate">{{ props.item.title }}</v-list-tile-content>
                </v-list-tile>
                <v-list-tile>
                <v-list-tile-content>Rating:</v-list-tile-content>
                <v-list-tile-content class="align-end">{{ props.item.rating }}</v-list-tile-content>
                </v-list-tile>
                <v-list-tile>
                <v-list-tile-content>Category:</v-list-tile-content>
                <v-list-tile-content class="align-end">{{ props.item.category }}</v-list-tile-content>
                </v-list-tile>
            </v-list>
            </v-card>
        </v-flex>
        </v-data-iterator>
    </v-container>

  </div>
</template>

<script>
// TODO: This component is very much like TaskGear.vue, the can be consolidated.
export default {
    data() {
        return {
            local: {
                pagination: {
                    rowsPerPage: -1,
                },
                library: {},
                media: [],
            },
            store: this.$store.state,
        }
    },

    beforeRouteUpdate(to, from, next) {
        this.getData(to.params.id);
        next();
    },

    mounted() {
        this.getData(this.$route.params.id);
    },

    methods: {
        getData(libraryId) {
            this.$store.getLibrary(libraryId, { media: true})
                .then(r => {
                    this.local.media = r.data.media;
                    delete r.data.media;
                    this.local.library = r.data;
                    this.local.pagination.totalItems = this.local.media.length;
                });
        },

        playVideo(video) {
            this.$store.playVideo(video);
        }
    }
}
</script>

<style scoped>

.bounding-box {
    background-repeat: no-repeat;
    background-size: contain;
    height: 300px;
    width: 100%;
    background-position: center;
}

.bounding-box:hover .play-button {
    display: block;
}

.play-button {
   position: absolute;
   width: 48px;
   height: 48px;
   top: 50%;
   left: 50%;
   margin-top: -64px;
   margin-left: -24px;
   display: none;
   cursor: pointer;
}

</style>
