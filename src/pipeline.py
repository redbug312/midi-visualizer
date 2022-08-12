#!/usr/bin/env python3
import gi
gi.require_version('Gst', '1.0')
gi.require_version('Gtk', '3.0')
from gi.repository import Gst, Gtk

# Gst utilizing functions

class Player:
    def __init__(self):
        frontend_elements = ['webmsrc', 'matroskademux', 'webmqueue',
                             'midisrc', 'midiparse', 'fluiddec']
        backend_elements = ['vp8dec', 'videoconvert', 'gtksink',
                            'autoaudiosink']
        frontend = make_frontend_pipeline('frontend', frontend_elements)
        play_backend = make_play_backend_pipeline('backend', backend_elements)
        frontend.get_by_name('fluiddec').set_property('soundfont', 'soundfont/touhou.sf2')

        self.pipeline = Gst.Pipeline.new('player')
        self.pipeline.add(frontend)
        self.pipeline.add(play_backend)
        frontend.link_pads('video_src', play_backend, 'video_sink')
        frontend.link_pads('audio_src', play_backend, 'audio_sink')

    def load(self, webm, midi):
        webmsrc = self.pipeline.get_by_name('webmsrc')
        midisrc = self.pipeline.get_by_name('midisrc')
        webmsrc.set_property('location', webm)
        midisrc.set_property('location', midi)

    def save(self, file):
        backend_elements = ['webmmux', 'filesink',
                            'audioconvert', 'vorbisenc', 'midiqueue']
        frontend     = self.pipeline.get_by_name('frontend')
        play_backend = self.pipeline.get_by_name('backend').ref()  # Avoid making the same subpipeline
        save_backend = make_save_backend_pipeline('backend', backend_elements)
        save_backend.get_by_name('filesink').set_property('location', file)


        self.pipeline.set_state(Gst.State.NULL)
        self.pipeline.remove(play_backend)
        self.pipeline.add(save_backend)
        frontend.link_pads('video_src', save_backend, 'video_sink')
        frontend.link_pads('audio_src', save_backend, 'audio_sink')

        self.pipeline.set_state(Gst.State.PLAYING)
        bus = self.pipeline.get_bus()
        # Refresh slider bar while waiting for EOS
        self.refresh_interval = 30 # ms
        while bus.timed_pop_filtered(self.refresh_interval * 1e6, Gst.MessageType.EOS) is None:
            while Gtk.events_pending():
                Gtk.main_iteration()

        self.pipeline.set_state(Gst.State.NULL)
        self.pipeline.remove(save_backend)
        self.pipeline.add(play_backend)
        frontend.link_pads('video_src', play_backend, 'video_sink')
        frontend.link_pads('audio_src', play_backend, 'audio_sink')

    def widget(self):
        return self.pipeline.get_by_name('gtksink').props.widget

    def draw_pipeline(self):
        Gst.debug_bin_to_dot_file(self.pipeline, Gst.DebugGraphDetails.ALL, 'pipeline')
        print('Ok')


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


if __name__ == '__main__':
    Gst.init(None)
    Gtk.init(None)
    player = Player()
    player.draw_pipeline()
    player.load('/tmp/test.webm', 'midi/at-the-end-of-the-spring.mid')
    player.pipeline.set_state(Gst.State.PLAYING)
