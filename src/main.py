#!/usr/bin/env python3
import os
import gi
gi.require_version('Gst', '1.0')
gi.require_version('Gtk', '3.0')
from gi.repository import Gst, Gtk, GLib

from parser import Midi
import video
import pipeline


class Player(object):

    def __init__(self):
        Gtk.init(None)
        Gst.init(None)

        self.refresh_interval = 30  # in milliseconds
        self.destination = None
        self.duration = Gst.CLOCK_TIME_NONE
        self.player = Gst.Pipeline.new('player')
        self.builder = None

        frontend_elements = ['webmsrc', 'matroskademux', 'webmqueue',
                             'midisrc', 'midiparse', 'fluiddec']
        backend_elements = ['vp8dec', 'videoconvert', 'gtksink',
                            'autoaudiosink']
        frontend = pipeline.make_frontend_pipeline('frontend', frontend_elements)
        play_backend = pipeline.make_play_backend_pipeline('backend', backend_elements)
        frontend.get_by_name('fluiddec').set_property('soundfont', 'soundfont/touhou.sf2')

        self.player.add(frontend)
        self.player.add(play_backend)
        frontend.link_pads('video_src', play_backend, 'video_sink')
        frontend.link_pads('audio_src', play_backend, 'audio_sink')

        gtksink = play_backend.get_by_name('gtksink')
        self.builder = self.build_ui()
        self.builder.get_object('video_container').pack_start(gtksink.props.widget, True, True, 0)
        # slider connected not through Glade, for getting handler_id
        self.slider_update_signal_id = \
            self.builder.get_object('time_slider').connect('value_changed', self.on_slider_changed)

        bus = self.player.get_bus()
        bus.add_signal_watch()
        bus.connect('message', self.on_message)

    def start(self):
        GLib.timeout_add(self.refresh_interval, self.refresh_ui)
        Gtk.main()

    def cleanup(self):
        try:
            os.remove('tmp.webm~')
        except OSError:
            pass
        if self.player:
            self.player.set_state(Gst.State.NULL)

    def build_ui(self):
        builder = Gtk.Builder()
        builder.add_from_file('src/ui.glade')
        builder.connect_signals(self)
        builder.get_object('main_window').show()
        return builder

    def refresh_ui(self):
        state = self.player.get_state(timeout=self.refresh_interval)[1]
        button = self.builder.get_object('play_pause_button')

        if state == Gst.State.PLAYING:
            button.get_image().set_from_icon_name(Gtk.STOCK_MEDIA_PAUSE, Gtk.IconSize.BUTTON)
            button.set_label('暫停')
        else:
            button.get_image().set_from_icon_name(Gtk.STOCK_MEDIA_PLAY, Gtk.IconSize.BUTTON)
            button.set_label('播放')
            return True

        slider = self.builder.get_object('time_slider')
        if self.duration == Gst.CLOCK_TIME_NONE:
            ret, self.duration = self.player.query_duration(Gst.Format.TIME)
            slider.set_range(0, self.duration / Gst.SECOND)
            slider.set_fill_level(self.duration / Gst.SECOND)

        ret, current = self.player.query_position(Gst.Format.TIME)
        if ret:
            slider.handler_block(self.slider_update_signal_id)
            slider.set_value(current / Gst.SECOND)
            slider.handler_unblock(self.slider_update_signal_id)
        return True

    # Gtk utilizing functions

    def set_window_sensitive(self, sensitive):
        self.player.set_state(Gst.State.READY if sensitive else Gst.State.NULL)
        for gtkobject in ['play_pause_button', 'stop_button', 'time_slider',
                          'gtk_open', 'gtk_save', 'gtk_save_as', 'gtk_quit']:
            self.builder.get_object(gtkobject).set_sensitive(sensitive)

    # Gtk events: Control bar

    def on_play_pause(self, button):
        state = self.player.get_state(timeout=10)[1]
        state = Gst.State.PAUSED if state == Gst.State.PLAYING else Gst.State.PLAYING
        self.player.set_state(state)

    def on_stop(self, button):
        self.duration = 0
        self.player.seek_simple(Gst.Format.TIME, Gst.SeekFlags.FLUSH, 0)
        self.player.set_state(Gst.State.READY)

    def on_slider_changed(self, slider):
        value = slider.get_value()
        self.player.seek_simple(Gst.Format.TIME, Gst.SeekFlags.FLUSH, value * Gst.SECOND)

    # Gtk events: Menu bar

    def on_file_open_activate(self, menuitem):
        webmsrc = self.player.get_by_name('webmsrc')
        midisrc = self.player.get_by_name('midisrc')

        open_dialog  = self.builder.get_object('open_dialog')
        progress_bar = self.builder.get_object('progressing_bar')
        hint_label   = self.builder.get_object('hint_label')

        response = open_dialog.run()
        open_dialog.hide()
        if response == Gtk.ResponseType.OK:
            self.duration = Gst.CLOCK_TIME_NONE
            source = open_dialog.get_filename()
            progress_bar.set_fraction(0)
            hint_label.set_text('正在解析 MIDI 檔案為影片...')

            self.set_window_sensitive(False)

            def update_progress_bar(progress):
                progress_bar.set_fraction(progress)
                while Gtk.events_pending():
                    Gtk.main_iteration()

            sheet = Midi(source)
            clip = video.midi_videoclip(sheet, iter_callback=update_progress_bar)
            clip.write_videofile('tmp.webm', fps=30, audio=False, threads=4)
            os.rename('tmp.webm', 'tmp.webm~')  # MoviePy disallows illegal file extension
            webmsrc.set_property('location', 'tmp.webm~')
            midisrc.set_property('location', source)

            self.set_window_sensitive(True)

            progress_bar.set_fraction(1)
            hint_label.set_visible(False)
            self.player.get_by_name('gtksink').props.widget.show()
        elif response == Gtk.ResponseType.CANCEL:
            return

    def on_file_save_activate(self, menuitem, save_as=False):
        if not self.destination or save_as:
            save_dialog = self.builder.get_object('save_dialog')
            response = save_dialog.run()
            save_dialog.hide()
            if response == Gtk.ResponseType.OK:
                self.destination = save_dialog.get_filename()
            elif response == Gtk.ResponseType.CANCEL:
                return

        if self.destination:
            backend_elements = ['webmmux', 'filesink',
                                'audioconvert', 'vorbisenc', 'midiqueue']
            frontend     = self.player.get_by_name('frontend')
            play_backend = self.player.get_by_name('backend').ref()  # Avoid making the same subpipeline
            save_backend = pipeline.make_save_backend_pipeline('backend', backend_elements)
            save_backend.get_by_name('filesink').set_property('location', self.destination)

            self.set_window_sensitive(False)

            self.player.remove(play_backend)
            self.player.add(save_backend)
            frontend.link_pads('video_src', save_backend, 'video_sink')
            frontend.link_pads('audio_src', save_backend, 'audio_sink')

            self.player.set_state(Gst.State.PLAYING)
            bus = self.player.get_bus()
            # Refresh slider bar while waiting for EOS
            while bus.timed_pop_filtered(self.refresh_interval * 1e6, Gst.MessageType.EOS) is None:
                while Gtk.events_pending():
                    Gtk.main_iteration()

            self.player.remove(save_backend)
            self.player.add(play_backend)
            frontend.link_pads('video_src', play_backend, 'video_sink')
            frontend.link_pads('audio_src', play_backend, 'audio_sink')

            self.set_window_sensitive(True)

    def on_file_save_as_activate(self, menuitem):
        self.on_file_save_activate(menuitem, save_as=True)

    def on_delete_event(self, widget, event=None):
        self.on_stop(None)
        Gtk.main_quit()

    def on_help_about_activate(self, menuitem):
        about_dialog = self.builder.get_object('about_dialog')
        about_dialog.run()
        about_dialog.hide()

    # Gst events

    def on_message(self, bus, message):
        if message.type == Gst.MessageType.ERROR:
            err, debug = message.parse_error()
            print('ERROR: {}, {}'.format(message.src.get_name(), err.message))
            self.cleanup()
        elif message.type == Gst.MessageType.STATE_CHANGED:
            old, new, pending = message.parse_state_changed()
            if message.src == self.player:
                self.refresh_ui()
        elif message.type == Gst.MessageType.EOS:
            self.player.set_state(Gst.State.READY)


if __name__ == '__main__':
    player = Player()
    player.start()
    player.cleanup()
