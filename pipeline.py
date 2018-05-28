#!/usr/bin/env python3
import gi
gi.require_version('Gst', '1.0')
from gi.repository import Gst

# Gst utilizing functions


def make_frontend_pipeline(pipeline_name, element_names):
    links = [('filesrc', 1), ('matroskademux', None), ('queue', None),
             ('filesrc', 4), ('midiparse', 5), ('fluiddec', None)]
    pipeline = Gst.Pipeline.new(pipeline_name)
    pipeline_get_by_index = lambda i: pipeline.get_by_name(element_names[i])

    for param in zip([link[0] for link in links], element_names):
        pipeline.add(Gst.ElementFactory.make(*param))
    for src, sink in [(i, x[1]) for i, x in enumerate(links) if x[1] is not None]:
        pipeline_get_by_index(src).link(pipeline_get_by_index(sink))

    def on_demux_pad_added(demux, pad):
        caps = pad.query_caps(None)
        structure_name = caps.to_string()
        if structure_name.startswith('video'):
            pad.link(pipeline_get_by_index(2).get_static_pad('sink'))

    pipeline_get_by_index(1).connect('pad-added', on_demux_pad_added)
    pipeline.add_pad(Gst.GhostPad.new('video_src', pipeline_get_by_index(2).get_static_pad('src')))
    pipeline.add_pad(Gst.GhostPad.new('audio_src', pipeline_get_by_index(5).get_static_pad('src')))
    return pipeline


def make_play_backend_pipeline(pipeline_name, element_names):
    # Gst.parse_launch("""
    #     filesrc location=..webm ! matroskademux ! queue ! vp8dec ! videoconvert ! gtksink
    #     filesrc location=..mid ! midiparse ! fluiddec soundfont=..sf2 ! autoaudiosink
    # """)
    links = [('vp8dec', 1), ('videoconvert', 2), ('gtksink', None),
             ('autoaudiosink', None)]
    pipeline = Gst.Pipeline.new(pipeline_name)
    pipeline_get_by_index = lambda i: pipeline.get_by_name(element_names[i])

    for param in zip([link[0] for link in links], element_names):
        pipeline.add(Gst.ElementFactory.make(*param))
    for src, sink in [(i, x[1]) for i, x in enumerate(links) if x[1] is not None]:
        pipeline_get_by_index(src).link(pipeline_get_by_index(sink))

    pipeline.add_pad(Gst.GhostPad.new('video_sink', pipeline_get_by_index(0).get_static_pad('sink')))
    pipeline.add_pad(Gst.GhostPad.new('audio_sink', pipeline_get_by_index(3).get_static_pad('sink')))
    return pipeline


def make_save_backend_pipeline(pipeline_name, element_names):
    # Gst.parse_launch("""
    #     webmmux name=mux ! filesink location="test.webm"
    #     filesrc location=..webm ! matroskademux ! queue ! mux
    #     filesrc location=..mid ! midiparse ! fluiddec soundfont=..sf2 !\
    #         audioconvert ! vorbisenc ! queue ! mux
    # """)
    links = [('webmmux', 1), ('filesink', None),
             ('audioconvert', 3), ('vorbisenc', 4), ('queue', 0)]
    pipeline = Gst.Pipeline.new(pipeline_name)
    pipeline_get_by_index = lambda i: pipeline.get_by_name(element_names[i])

    for param in zip([link[0] for link in links], element_names):
        pipeline.add(Gst.ElementFactory.make(*param))
    for src, sink in [(i, x[1]) for i, x in enumerate(links) if x[1] is not None]:
        pipeline_get_by_index(src).link(pipeline_get_by_index(sink))

    pipeline.add_pad(Gst.GhostPad.new('video_sink', pipeline_get_by_index(0).get_request_pad('video_0')))
    pipeline.add_pad(Gst.GhostPad.new('audio_sink', pipeline_get_by_index(2).get_static_pad('sink')))
    return pipeline
