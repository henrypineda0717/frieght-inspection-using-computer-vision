import os
import re
import gi

gi.require_version('Gst', '1.0')
gi.require_version('GstApp', '1.0')
from gi.repository import Gst, GstApp


def extract_rtsp_link(full_path: str) -> str:
    match = re.search(r'(rtsp://[^\s]+)', full_path)
    if match:
        link = match.group(1)
        if link.endswith('.mp4'):
            link = link[:-4]
        return link
    return full_path


def create_video_reader_pipeline(video_path: str, width: int, height: int):
    Gst.init(None)

    if '://' in video_path:
        uri = extract_rtsp_link(video_path)
    else:
        uri = f"file://{os.path.abspath(video_path)}"
        print('url', uri)

    sync_mode = 'false' if uri.startswith(('http://', 'https://', 'udp://')) else 'true'

    if uri.startswith('rtsp://'):
        pipeline_str = f"""
            rtspsrc location=\"{uri}\" latency=200 drop-on-latency=true !
            rtph264depay ! h264parse ! decodebin !
            videoconvert ! videoscale !
            video/x-raw,format=BGRx,width={width},height={height} !
            videoconvert !
            video/x-raw,format=BGR !
            appsink name=sink emit-signals=true sync=false max-buffers=1 drop=true
        """
    else:
        pipeline_str = f"""
            uridecodebin uri=\"{uri}\" !
            decodebin !
            videoconvert ! videoscale !
            video/x-raw,format=BGRx,width={width},height={height} !
            videoconvert !
            video/x-raw,format=BGR !
            appsink name=sink emit-signals=true sync={sync_mode} max-buffers=5 drop=true
        """

    pipeline = Gst.parse_launch(pipeline_str)
    appsink = pipeline.get_by_name('sink')
    return pipeline, appsink
