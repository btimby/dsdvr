FROM python:3.6.7-alpine3.8
MAINTAINER Ben Timby btimby@gmail.com

ADD Pipfile* /install/
ADD docker/supervisord.conf /etc/
COPY dist/dsdvr-*.tar.gz /install

WORKDIR /install

# TODO: install libhdhomerun and other deps.
RUN apk add --update-cache git build-base supervisor && \
    apk del --purge git build-base && \
    rm -rf /var/cache/apk*

# NOTE: for debugging
RUN find /install

RUN pip3 install pipenv
RUN pipenv install --system
RUN pip3 install dsdvr-*.tar.gz

RUN rm -rf /install

ENTRYPOINT ["supervisord", "--configuration", "/etc/supervisord.conf"]
