import axios from "axios";

let refreshInProgress = false;

axios.interceptors.request.use (
    function(config) {
        const token = localStorage.getItem('accessToken');
        if (token)
            config.headers.Authorization = `Bearer ${token}`;
        return config;
    },
    function(error) {
        return Promise.reject (error);
    }
);

axios.interceptors.response.use(
    function(response) { return response;}, 
    function(error) {
        const { config, response: { status } } = error;

        if (status === 401 && !refreshInProgress) {
            let refreshToken = localStorage.getItem('refreshToken');
            refreshInProgress = true;

            axios.post('/api/token/refresh/', {
                'refresh': refreshToken,
            })
                .then(r => {
                    const token = r.data.access;
                    localStorage.setItem('accessToken', token);
                    config.headers.Authorization = `Bearer ${token}`;
                    refreshInProgress = false;
                    return axios.request(config);
                })
                .catch(e => {
                    refreshInProgress = false;
                });
        } else {
            return Promise.reject (error);
        }
    }
);

class Store {
    constructor() {
        this.state = { 
            nowPlaying: null,
            user: null,
        };

        axios.get('/api/me/')
            .then(r => {
                this.state.user = r.data;
            });
    }

    getTasks() {
        // Get tasks from the API...
        return axios.get('/api/tasks/');
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
