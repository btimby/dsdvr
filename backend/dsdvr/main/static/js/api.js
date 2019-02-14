var Tuners = {

    list() {
        return axios.get('/api/tuners/');
    },

    get(id) {
        return axios.get('/api/tuners/' + id + '/');
    },

    delete(id) {
        return axios.delete('/api/tuners/' + id + '/');
    },

    discover() {
        return axios.post('/api/tuners/discover/');
    }

};

var Shows = {
    list() {
        return axios.get('/api/shows/');
    },

    get(id) {
        return axios.get('/api/shows/' + id + '/');
    }
};

var Streams = {
    create(showId) {
        return axios.post('/api/streams/', { "show.id": showId });
    }
};
