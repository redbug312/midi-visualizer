#!/usr/bin/env python3
import os
import gi
gi.require_version('Gst', '1.0')
gi.require_version('Gtk', '3.0')
from gi.repository import Gst, Gtk, GLib
import midi
import video


class Player(object):

    def __init__(self):
        Gtk.init(None)
        Gst.init(None)

        self.destination = None                   # file path to save the result
        self.duration = Gst.CLOCK_TIME_NONE       # time length of the video
        self.player = Gst.Pipeline.new('player')  # the gstreamer pipeline, as below

        # Pipeline below is equivalent to
        #   Gst.parse_launch("""
        #       filesrc location=..webm ! matroskademux ! queue ! vp8dec ! videoconvert ! gtksink
        #       filesrc location=..mid ! midiparse ! fluiddec soundfont=..sf2 ! autoaudiosink
        #   """)

        webmsrc       = Gst.ElementFactory.make('filesrc', 'webmsrc')
        matroskademux = Gst.ElementFactory.make('matroskademux', 'matroskademux')
        vp8dec        = Gst.ElementFactory.make('vp8dec', 'vp8dec')
        webmqueue     = Gst.ElementFactory.make('queue', 'webmqueue')
        videoconvert  = Gst.ElementFactory.make('videoconvert', 'videoconvert')
        gtksink       = Gst.ElementFactory.make('gtksink', 'gtksink')
        midisrc       = Gst.ElementFactory.make('filesrc', 'midisrc')
        midiparse     = Gst.ElementFactory.make('midiparse', 'midiparse')
        fluiddec      = Gst.ElementFactory.make('fluiddec', 'fluiddec')
        autoaudiosink = Gst.ElementFactory.make('autoaudiosink', 'autoaudiosink')

        for element in [webmsrc, matroskademux, webmqueue, vp8dec, videoconvert,
                        gtksink, midisrc, midiparse, fluiddec, autoaudiosink]:
            self.player.add(element)

        def on_demux_pad_added(demux, pad):
            caps = pad.query_caps(None)
            structure_name = caps.to_string()
            if structure_name.startswith('video'):
                pad.link(webmqueue.get_static_pad('sink'))

        webmsrc.link(matroskademux)
        matroskademux.connect('pad-added', on_demux_pad_added)
        webmqueue.link(vp8dec)
        vp8dec.link(videoconvert)
        videoconvert.link(gtksink)
        midisrc.link(midiparse)
        midiparse.link(fluiddec)
        fluiddec.link(autoaudiosink)
        fluiddec.set_property('soundfont', 'soundfont/Touhou.sf2')

        self.gtksink = gtksink.ref()
        self.builder = self.build_ui()
        # slider connected not through Glade, for getting handler_id
        self.slider_update_signal_id = \
            self.builder.get_object('time_slider').connect('value_changed', self.on_slider_changed)
        self.builder.get_object('video_container').pack_start(self.gtksink.props.widget, True, True, 0)

        bus = self.player.get_bus()
        bus.add_signal_watch()
        bus.connect('message', self.on_message)

    def start(self):
        GLib.timeout_add(30, self.refresh_ui)
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
        builder.add_from_file('ui.glade')
        builder.connect_signals(self)
        builder.get_object('main_window').show()
        return builder

    def refresh_ui(self):
        state = self.player.get_state(timeout=10)[1]

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

    # Utilizing functions

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
            source = open_dialog.get_filename()
            progress_bar.set_fraction(0)
            hint_label.set_text('正在解析 MIDI 檔案為影片...')

            self.set_window_sensitive(False)

            def update_pregress_bar(clip):
                progress = progress_bar.get_fraction() + 1 / clip.nframes
                progress_bar.set_fraction(progress)
                while Gtk.events_pending():
                    Gtk.main_iteration()

            sheet = midi.Midi(source)
            clip = video.midi_videoclip(sheet, callback=update_pregress_bar)
            clip.write_videofile('tmp.webm', codec='libvpx', fps=15)
            os.rename('tmp.webm', 'tmp.webm~')  # MoviePy disallows illegal file extension

            self.set_window_sensitive(True)

            webmsrc.set_property('location', 'tmp.webm~')
            midisrc.set_property('location', source)
            progress_bar.set_fraction(1)
            hint_label.set_visible(False)

            self.gtksink.props.widget.show()
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
            # Pipeline below is equivalent to
            #   Gst.parse_launch("""
            #       webmmux name=mux ! filesink location="test.webm"
            #       filesrc location=..webm ! matroskademux ! queue ! mux
            #       filesrc location=..mid ! midiparse ! fluiddec soundfont=..sf2 ! \
            #           audioconvert ! vorbisenc ! queue ! mux
            #   """)
            webmqueue    = self.player.get_by_name('webmqueue')
            fluiddec     = self.player.get_by_name('fluiddec')

            webmmux      = Gst.ElementFactory.make('webmmux', 'webmmux')
            filesink     = Gst.ElementFactory.make('filesink', 'filesink')
            audioconvert = Gst.ElementFactory.make('audioconvert', 'audioconvert')
            vorbisenc    = Gst.ElementFactory.make('vorbisenc', 'vorbisenc')
            midiqueue    = Gst.ElementFactory.make('queue', 'midiqueue')

            self.set_window_sensitive(False)

            for gstobject in ['vp8dec', 'videoconvert', 'gtksink', 'autoaudiosink']:
                self.player.remove(self.player.get_by_name(gstobject))
            for gstobject in [webmmux, filesink, audioconvert, vorbisenc, midiqueue]:
                self.player.add(gstobject)
            webmmux.link(filesink)
            fluiddec.link(audioconvert)
            webmqueue.link_pads(None, webmmux, 'video_0')
            audioconvert.link(vorbisenc)
            vorbisenc.link(midiqueue)
            midiqueue.link_pads(None, webmmux, 'audio_0')
            filesink.set_property('location', self.destination)

            self.player.set_state(Gst.State.PLAYING)


    def on_file_save_as_activate(self, menuitem):
        self.on_file_save_activate(menuitem, save_as=True)

    def on_file_save_revert(self):
        # Revert the pipeline, triggered only when receiving EOS
        # Noticed that remove() also dereference the Gst element
        webmqueue     = self.player.get_by_name('webmqueue')
        fluiddec      = self.player.get_by_name('fluiddec')

        autoaudiosink = Gst.ElementFactory.make('autoaudiosink', 'autoaudiosink')
        vp8dec        = Gst.ElementFactory.make('vp8dec', 'vp8dec')
        videoconvert  = Gst.ElementFactory.make('videoconvert', 'videoconvert')
        gtksink       = self.gtksink

        self.set_window_sensitive(False)

        for gstobject in ['webmmux', 'filesink', 'audioconvert', 'vorbisenc', 'midiqueue']:
            self.player.remove(self.player.get_by_name(gstobject))
        for gstobject in [autoaudiosink, vp8dec, videoconvert, gtksink]:
            self.player.add(gstobject)
        webmqueue.link(vp8dec)
        vp8dec.link(videoconvert)
        videoconvert.link(gtksink)
        fluiddec.link(autoaudiosink)

        self.set_window_sensitive(True)

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
            is_saving = bool(self.player.get_by_name('filesink'))
            if is_saving:
                self.on_file_save_revert()
            self.player.set_state(Gst.State.READY)


if __name__ == '__main__':
    player = Player()
    player.start()
    player.cleanup()
