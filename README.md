Dead Simple DVR
===============

This software application consists of server components deployed in a docker
container and client components that run on embedded devices such as android
machines and smart TVs.

Dead Simple DVR Video Streaming Service
=======================================

This service consumes the guide and recording service to provide video
streaming, playback control, and guide / scheduling.

This service will provide a REST API that performs the following functions:

1. Manage video streams.
   1. Allow viewer to start an ephemeral recording stream.
   2. Allow viewer to stream a video file from the library (previously
      recorded)
   3. Allow viewer to pause, play, ffwd, rwnd, and stop a stream.
2. Display information about current streams. This can be used for the system
   dashboard.
3. Store what is viewed and when along with cursors. This can be used to
   provide advanced features like:
    1. Continue watching...
    2. Favorite shows...

Streaming
=========

Streams will always originate from a file on disk. Even viewing live TV will
require an ephemeral recording for the desired channel which will then be
streamed to the viewer.

ffmpeg or VLC or similar will be used to actually stream the video data.

Streaming may use RTP or HTTP or both.

Transcoding
===========

Recordings will be written using a configurable format. Viewers may request a
different format which will require transcoding. The streaming software
(ffmpeg or VLC or similar) will convert the data before streaming it.

Dead Simple DVR Guide Service
=============================

The guide service is responsible for providing the data necessary for viewing
and scheduling TV shows and recordings.

This service provides a REST API to perform the following functions:

1. Fetch a dataset including available channels and the programming scheduled
   for those channels as well as scheduled and ongoing recordings. This data
   will come from HDHomeRun tuner, the recording service and a TV listing data
   source.
2. Create a scheduled recording by POSTing the start time, end time, and
   channel.
3. Fetch a list of scheduled recordings.
   
As well as an HTML interface that:

1. Renders an HTML / Javascript guide that can be viewed within client
   applications. The data will originate from the guide service.
2. Performs necessary actions to allow a browser to view a video stream.

The guide service may serve the web interface available to desktop computers.
If the user chooses not to use the viewer "app" on an embedded device, the web
interface available from the guide will be their only UI.
