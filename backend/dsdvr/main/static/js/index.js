Vue.component('player', {
    template: '<div></div>'
})

Vue.component('progressbar', {
    template: `<div class="progress" aria-valuenow="12">
        <div class="progress-bar" role="progressbar" v-bind:style="{ width: percent + \'%\' }"></div>
    </div>`,
    props: ['percent']
})

new Vue({
    el: '#app',
    data: {
        message: "Hello"
    }
})
