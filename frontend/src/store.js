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

    getLibraries(options) {
        let url = '/api/libraries/';
        if (options && !options.media)
            url += '?fields!=media';
        return axios.get(url)
            .catch(e => {
                console.log(e);
                throw e;
            });
    }

    getLibrary(libraryId, options) {
        let url = `/api/libraries/${libraryId}/`;
        if (options && !options.media)
            url += '?fields!=media';
        return axios.get(url)
            .catch(e => {
                console.log(e);
                throw e;
            });
    }

    deleteLibrary(libraryId) {
        return axios.delete(`/api/libraries/${libraryId}/`)
            .catch(e => {
                console.log(e);
                throw e;
            });
    }

    getLibraryMedia(libraryId) {
        return axios.get(`/api/libraries/${libraryId}/media/`)
            .catch(e => {
                console.log(e);
                throw e;
            });
    }

    playVideo(media) {
        // TODO: create a stream and set that to nowPlaying...
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
        this.state.nowPlaying = null;
    }
}

export default Store;
