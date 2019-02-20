<template>
    <div>
        <v-layout row>
            <v-flex>
                <v-btn @click="downloadGuide">Download Guide Data</v-btn>
            </v-flex>
            <v-flex>
                <p>Downloaded {{ local.guide.length }} programs.</p>
            </v-flex>
        </v-layout>
    </div>
</template>

<script>
export default {
    name: 'GuideDownload',

    data() {
        return {
            local:
            {
                guide: [],
            },
            store: this.$store.state,
        }
    },

    created() {
        this.getGuide();
    },

    methods: {
        downloadGuide() {
            this.$store.downloadGuide(r => {
                if (r.data.status == 'done') {
                    this.getGuide();
                }
            });
        },

        getGuide() {
            this.$store.getGuide()
                .then(r => {
                    this.local.guide = r.data;
                });
        }
    }
}
</script>

<style scoped>
</style>