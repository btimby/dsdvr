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
            .catch(e => console.log(e));
    }

    deleteRecording(recordingId) {
        return axios.delete(`/api/recordings/${recordingId}/`)
            .catch(e => console.log(e));
    }

    getLibraries(options) {
        let url = '/api/libraries/';
        if (options && !options.media)
            url += '?fields!=media';
        return axios.get(url)
            .catch(e => console.log(e));
    }

    getLibrary(libraryId, options) {
        let url = `/api/libraries/${libraryId}/`;
        if (options && !options.media)
            url += '?fields!=media';
        return axios.get(url)
            .catch(e => console.log(e));
    }

    deleteLibrary(libraryId) {
        return axios.delete(`/api/libraries/${libraryId}/`)
            .catch(e => console.log(e));
    }

    getLibraryMedia(libraryId) {
        return axios.get(`/api/libraries/${libraryId}/media/`)
            .catch(e => console.log(e));
    }

    playVideo(video) {
        // TODO: create a stream and set that to nowPlaying...
        this.state.nowPlaying = video;
    }

    stopVideo() {
        this.state.nowPlaying = null;
    }
}

export default Store;
