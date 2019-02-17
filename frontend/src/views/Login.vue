<template>
    <v-container fluid fill-height>
    <v-layout align-center justify-center>
        <v-flex xs12 sm8 md4>
        <v-card dark class="elevation-12">
            <v-toolbar dark color="primary">
            <v-toolbar-title>Login form</v-toolbar-title>
            <v-spacer></v-spacer>
            </v-toolbar>
            <v-form @submit.prevent="login" ref="loginForm">
                <v-card-text>
                    <v-text-field required :rules="local.emailRules" v-model="local.email" prepend-icon="person" label="Email"></v-text-field>
                    <v-text-field required :rules="local.passwordRules" v-model="local.password" prepend-icon="lock" label="Password" type="password"></v-text-field>
                </v-card-text>
                <v-card-actions>
                <v-spacer></v-spacer>
                    <v-btn type="submit" color="primary">Login</v-btn>
                </v-card-actions>
            </v-form>
        </v-card>
        </v-flex>
    </v-layout>
    </v-container>
</template>

<script>
export default {
    name: 'Login',

    data() {
        return {
            local: {
                email: null,
                password: null,

                emailRules: [
                    v => !!v || 'E-mail is required',
                    v => /.+@.+/.test(v) || 'E-mail must be valid'
                ],
                passwordRules: [
                    v => !!v || 'Password is required',
                ],
            },
            store: this.$store.state,
        }
    },

    methods: {
        login() {
            if (this.$refs.loginForm.validate()) {
                this.$store.login(this.local.email, this.local.password)
                    .then(r => {
                        this.$router.push('home');
                    })
            }
        }
    },
}
</script>

<style scoped>

</style>