#!/usr/bin/env python3
import gi
gi.require_version('Gst', '1.0')
gi.require_version('Gtk', '3.0')
from gi.repository import Gst, Gtk


class Player:
    def __init__(self):
        self.pipeline = Gst.Pipeline.new('player')
        self.elements = dict()

        self.load_pipe, self.elements['load'] = make_load_pipeline()
        self.play_pipe, self.elements['play'] = make_play_pipeline()
        self.save_pipe, self.elements['save'] = make_save_pipeline()

        self.pipeline.add(self.load_pipe)
        self.pipeline.add(self.play_pipe)
        self.load_pipe.link_pads('video_sink', self.play_pipe, 'video_src')
        self.load_pipe.link_pads('audio_sink', self.play_pipe, 'audio_src')

    def load(self, webm, midi):
        webmsrc = self.elements['load'][0]
        midisrc = self.elements['load'][3]
        webmsrc.set_property('location', webm)
        midisrc.set_property('location', midi)

    def save(self, file):
        filesink = self.elements['save'][1]
        filesink.set_property('location', file)

        self.pipeline.set_state(Gst.State.NULL)
        self.pipeline.remove(self.play_pipe)
        self.pipeline.add(self.save_pipe)
        self.load_pipe.link_pads('video_sink', self.save_pipe, 'video_src')
        self.load_pipe.link_pads('audio_sink', self.save_pipe, 'audio_src')

        self.pipeline.set_state(Gst.State.PLAYING)
        bus = self.pipeline.get_bus()
        # Refresh slider bar while waiting for EOS
        self.refresh_interval = 30 # ms
        while bus.timed_pop_filtered(self.refresh_interval * 1e6, Gst.MessageType.EOS) is None:
            while Gtk.events_pending():
                Gtk.main_iteration()

        self.pipeline.set_state(Gst.State.NULL)
        self.pipeline.remove(self.save_pipe)
        self.pipeline.add(self.play_pipe)
        self.load_pipe.link_pads('video_sink', self.play_pipe, 'video_src')
        self.load_pipe.link_pads('audio_sink', self.play_pipe, 'audio_src')

    def widget(self):
        gtksink = self.elements['play'][2]
        return gtksink.props.widget

    def draw_pipeline(self):
        Gst.debug_bin_to_dot_file(self.pipeline, Gst.DebugGraphDetails.ALL, 'pipeline')


def extend_pipe(pipeline, names):
    elements = [Gst.ElementFactory.make(name) for name in names]
    for element in elements:
        pipeline.add(element)
    for pred, succ in zip(elements, elements[1:]):
        assert pred.link(succ), 'failed to link %s to %s' % (pred, succ)
    return elements


def make_load_pipeline():
    pipeline = Gst.Pipeline.new('load')
    elements = []
    elements += extend_pipe(pipeline, ['filesrc', 'matroskademux'])
    elements += extend_pipe(pipeline, ['queue'])
    elements += extend_pipe(pipeline, ['filesrc', 'midiparse', 'fluiddec'])

    def on_demux_pad_added(_, pad):
        caps = pad.query_caps(None)
        if caps.to_string().startswith('video'):
            pad.link(elements[2].get_static_pad('sink'))

    elements[1].connect('pad_added', on_demux_pad_added)
    elements[5].set_property('soundfont', 'soundfont/touhou.sf2')

    video_sink = Gst.GhostPad.new('video_sink', elements[2].get_static_pad('src'))
    audio_sink = Gst.GhostPad.new('audio_sink', elements[5].get_static_pad('src'))
    pipeline.add_pad(video_sink)
    pipeline.add_pad(audio_sink)
    return pipeline, elements


def make_play_pipeline():
    pipeline = Gst.Pipeline.new('play')
    elements = []
    elements += extend_pipe(pipeline, ['vp8dec', 'videoconvert', 'gtksink'])
    elements += extend_pipe(pipeline, ['autoaudiosink'])

    video_src = Gst.GhostPad.new('video_src', elements[0].get_static_pad('sink'))
    audio_src = Gst.GhostPad.new('audio_src', elements[3].get_static_pad('sink'))
    pipeline.add_pad(video_src)
    pipeline.add_pad(audio_src)
    return pipeline, elements


def make_save_pipeline():
    pipeline = Gst.Pipeline.new('save')
    elements = []
    elements += extend_pipe(pipeline, ['webmmux', 'filesink'])
    elements += extend_pipe(pipeline, ['audioconvert', 'vorbisenc', 'queue'])

    elements[4].link(elements[0])  # use queue before a mux
    video_src = Gst.GhostPad.new('video_src', elements[0].get_request_pad('video_0'))
    audio_src = Gst.GhostPad.new('audio_src', elements[2].get_static_pad('sink'))
    pipeline.add_pad(video_src)
    pipeline.add_pad(audio_src)
    return pipeline, elements


if __name__ == '__main__':
    Gst.init(None)
    Gtk.init(None)
    player = Player()
    player.draw_pipeline()
    player.load('/tmp/test.webm', 'midi/at-the-end-of-the-spring.mid')
    player.pipeline.set_state(Gst.State.PLAYING)
