import axios from "axios";

let refreshInProgress = false;

// Some endpoints that don't require a token...
const TOKEN_WHITELIST = [
    '/api/token/',
];

axios.interceptors.request.use (
    function(config) {
        const token = localStorage.getItem('accessToken');
        if (token)
            config.headers.Authorization = `Bearer ${token}`;
        // TODO: url may be absolute. We need to part the path out in that
        // case. Currently we use all relative URLs so this works.
        else if (TOKEN_WHITELIST.indexOf(config.url) == -1)
        {
            return {
                // TODO: this causes an error in response interceptor.
                ...config,
                cancelToken: new CancelToken((cancel) => cancel('No token'))
            };
        }
        return config;
    },
    function(error) {
        return Promise.reject (error);
    }
);

axios.interceptors.response.use(
    function(response) { return response;}, 
    function(e) {
        const { config, response: { status } } = e;

        if (status === 401 && !refreshInProgress) {
            let refreshToken = localStorage.getItem('refreshToken');
            if (!refreshToken) {
                // No refresh token, just bail.
                return Promise.reject(e);
            }

            refreshInProgress = true;
            axios.post('/api/token/refresh/', {
                'refresh': refreshToken,
            })
                .then(r => {
                    refreshInProgress = false;

                    localStorage.setItem('accessToken', r.data.access);
                    config.headers.Authorization = `Bearer ${r.data.access}`;

                    // Retry with fresh token...
                    return axios.request(config);
                })
                .catch(e => {
                    refreshInProgress = false;

                    const { config, response: { status } } = e;
                    if (status == 400) {
                        // Invalid / expired refresh token, delete tokens.
                        localStorage.removeItem('accessToken');
                        localStorage.removeItem('refreshToken');
                    }
                });

        } else {
            return Promise.reject(e);
        }
    }
);

class Status {
    constructor() {
        this._subscribers = [];
        this._interval = null;
        this._status = null;
    }

    _dispatch(status) {
        this._status = status;
        this._subscribers.forEach(fn => {
            try {
                fn(this._status);

            } catch(e) {
                // Don't let their issues affect us.
                console.log(e);
            }
        })
    }

    get() {
        return axios.get('/api/status/');
    }

    _poll() {
        this.get()
            .then(r => {
                // Simple quick comparison. Key order will match as API uses
                // OrderedDict. Even if this fails, it just means some extra
                // dispatches.
                if (JSON.stringify(r.data) === 
                    JSON.stringify(this._status))
                    return;
                this._dispatch(r.data);
            });
    }

    subscribe(fn) {
        this._subscribers.push(fn);
        if (this._interval === null) {
            // Get data for them right away.
            this._poll();
            // Poll every so often while we have subscribers.
            this._interval = setInterval(this._poll.bind(this), 10000);
        }
    }

    unsubscribe(fn) {
        const index = this._subscribers.indexOf(fn);
        if (index !== -1) {
            this._subscribers.splice(index, 1);
        }
        if (this._subscribers.length === 0) {
            // Don't poll if we don't have subscribers.
            clearInterval(this._interval);
            this._interval = null;
        }
    }
}

class Store {
    constructor() {
        this.state = { 
            nowPlaying: null,
            user: null,
        };
        this.status = new Status();

        axios.get('/api/me/')
            .then(r => {
                this.state.user = r.data;
            });
    }

    getTuners() {
        return axios.get('/api/tuners/');
    }

    discoverTuners(callback) {
        axios.post('/api/tuners/discover/')
            .then(r => {
                this.pollTask(r.data, callback);
            });
    }

    getGuide() {
        return axios.get('/api/guide/');
    }

    downloadGuide(callback) {
        axios.post('/api/guide/download/')
            .then(r => {
                this.pollTask(r.data, callback);
            });
    }

    getTasks() {
        // Get tasks from the API...
        return axios.get('/api/tasks/');
    }

    pollTask(task, callback) {
        function poll() {
            axios.get(`/api/tasks/${task.id}/`)
                .then(r => {
                    // If not complete, set another timeout...
                    if (r.data.status == 'running') {
                        setTimeout(poll, 1000);
                    }

                    callback(r);
                });
        }

        setTimeout(poll, 1000);
    }

    deleteTask(taskId) {
        return axios.delete(`/api/tasks/${taskId}/`);
    }

    getRecordings() {
        // Get recordings from the API...
        return axios.get('/api/recordings/');
    }

    deleteRecording(recordingId) {
        return axios.delete(`/api/recordings/${recordingId}/`);
    }

    getMedia() {
        return axios.get('/api/media/');
    }

    playVideo(media) {
        // TODO: wait for stream to become ready, move code from
        // VideoPlayer.vue...
        axios.post(`/api/media/${media.id}/stream/`, { 'type': 0 })
            .then(r => {
                media.streamUrl = r.data.url;
                media.streamCursor = r.data.cursor;
                this.state.nowPlaying = media;
            });
    }

    stopVideo() {
        // NOTE: This is tenuous. I would prefer to detect this condition on
        // playback also ask the user if they prefer resume or restart. But
        // also it makes sense to clear the cursor when playback finishes, so
        // we start with that.
        this.updateStreamCursor(this.state.nowPlaying.id, 0);
        this.state.nowPlaying = null;
    }

    updateStreamCursor(mediaId, currentTime) {
        return axios.patch(
            `/api/media/${mediaId}/stream/`, { cursor: currentTime });
    }

    login(email, password) {
        return axios.post('/api/token/', { email: email, password: password })
            .then(r => {
                localStorage.setItem('accessToken', r.data.access);
                localStorage.setItem('refreshToken', r.data.refresh);

                // TODO: extract this data from the JWT.
                axios.get('/api/me/')
                    .then(r => {
                        this.state.user = r.data;
                    });
            });
    }

    logout() {
        localStorage.removeItem('accessToken');
        localStorage.removeItem('refreshToken');
    }
}

export default Store;
