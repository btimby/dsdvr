import axios from "axios";

class Store {
    constructor() {
        this.state = { 
            nowPlaying: null,
            user: {
                name: 'Ben Timby',
                email: 'btimby@gmail.com',
            },
        };
    }

    getTasks() {
        // Get tasks from the API...
        return axios.get('/api/tasks/')
            .catch(e => console.log(e));
    }

    deleteTask(taskId) {
        return axios.delete(`/api/tasks/${taskId}/`)
            .catch(e => console.log(e))
    }

    getRecordings() {
        // Get recordings from the API...
        return axios.get('/api/recordings/')
            .catch(e => {
                console.log(e);
                throw e;
            });
    }

    deleteRecording(recordingId) {
        return axios.delete(`/api/recordings/${recordingId}/`)
            .catch(e => {
                console.log(e);
                throw e;
            });
    }

    getMedia() {
        return axios.get('/api/media/')
            .catch(e => {
                console.log(e);
                throw e;
            });
    }

    playVideo(media) {
        // TODO: wait for stream to become ready, move code from
        // VideoPlayer.vue...
        axios.post(`/api/media/${media.id}/stream/`, { 'type': 0 })
            .then(r => {
                media.streamUrl = r.data.url;
                media.streamCursor = r.data.cursor;
                this.state.nowPlaying = media;
            })
            .catch(e => {
                console.log(e);
                throw e;
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
            `/api/media/${mediaId}/stream/`, { cursor: currentTime })
        .catch(e => {
            console.log(e);
            throw e;
        });
    }
}

export default Store;
