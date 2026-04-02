import os
import gi
gi.require_version('Gst', '1.0')
gi.require_version('GstApp', '1.0')
from gi.repository import Gst, GLib

# def create_hls_pipeline(
#     width: int,
#     height: int,
#     hls_output_dir: str,
#     target_segment_duration: int = 2,
#     max_segments: int = 10
# ):
#     os.makedirs(hls_output_dir, exist_ok=True)

#     playlist_location = os.path.join(hls_output_dir, "playlist.m3u8")
#     segment_location = os.path.join(hls_output_dir, "segment%d.ts")

#     # This pipeline uses NVIDIA hardware acceleration (NVMM and NVENC)
#     pipeline_str = f"""
#         appsrc name=source
#             is-live=true
#             format=time
#             do-timestamp=true
#             caps=video/x-raw,format=BGRx,width={width},height={height},framerate=15/1 !

#         queue max-size-buffers=3 leaky=downstream !

#         nvvidconv !
#         video/x-raw(memory:NVMM),format=NV12 !

#         nvv4l2h264enc
#             maxperf-enable=true
#             bitrate=2000000
#             preset-level=2 
#             control-rate=1
#             insert-sps-pps=true
#             insert-vui=true
#             idrinterval=30
#             iframeinterval=30
#             vbv-size=33333

#         ! h264parse config-interval=1

#         ! hlssink2 name=hls_sink
#             max-files={max_segments}
#             playlist-length={max_segments}
#             target-duration={target_segment_duration}
#             location="{segment_location}"
#             playlist-location="{playlist_location}"
#             send-keyframe-requests=true
#         """

#     pipeline = Gst.parse_launch(pipeline_str)
#     appsource = pipeline.get_by_name("source")
#     hls_sink = pipeline.get_by_name("hls_sink")

#     return pipeline, appsource, hls_sink

def create_hls_pipeline(
    width: int,
    height: int,
    hls_output_dir: str,
    target_segment_duration: int = 2,
    max_segments: int = 10
):
    os.makedirs(hls_output_dir, exist_ok=True)

    playlist_location = os.path.join(hls_output_dir, "playlist.m3u8")
    segment_location = os.path.join(hls_output_dir, "segment%d.ts")

    # REPLACED: nvvidconv -> videoconvert
    # REPLACED: nvv4l2h264enc -> x264enc
    # REMOVED: memory:NVMM
    pipeline_str = f"""
        appsrc name=source
            is-live=true
            format=time
            do-timestamp=true
            caps=video/x-raw,format=BGRx,width={width},height={height},framerate=15/1 !

        queue max-size-buffers=3 leaky=downstream !

        videoconvert !
        video/x-raw,format=I420 !

        x264enc 
            bitrate=2000 
            speed-preset=ultrafast 
            tune=zerolatency 
            key-int-max=30 !
            
        h264parse config-interval=1 !

        hlssink2 name=hls_sink
            max-files={max_segments}
            playlist-length={max_segments}
            target-duration={target_segment_duration}
            location="{segment_location}"
            playlist-location="{playlist_location}"
            send-keyframe-requests=true
    """

    pipeline = Gst.parse_launch(pipeline_str)
    appsource = pipeline.get_by_name("source")
    hls_sink = pipeline.get_by_name("hls_sink")

    return pipeline, appsource, hls_sink