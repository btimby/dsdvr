<template>
    <div>
        <v-layout row>
            <v-flex>
                <v-btn @click="discoverTuners">Scan for tuners</v-btn>
            </v-flex>
            <v-flex>
                <p>Detected {{ local.tuners.length }} tuners.</p>
            </v-flex>
        </v-layout>
    </div>
</template>

<script>
export default {
    name: 'TunerScan',

    data() {
        return {
            local:
            {
                tuners: [],
            },
            store: this.$store.state,
        }
    },

    created() {
        this.getTuners();
    },

    methods: {
        discoverTuners() {
            this.$store.discoverTuners(r => {
                if (r.data.status == 'done') {
                    this.getTuners();
                }
            });
        },

        getTuners() {
            this.$store.getTuners()
                .then(r => {
                    this.local.tuners = r.data;
                });
        }
    }
}
</script>

<style scoped>
</style>