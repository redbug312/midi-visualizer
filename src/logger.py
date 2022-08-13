import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk
from proglog import ProgressBarLogger


class Logger(ProgressBarLogger):
    def __init__(self, gtk_bar, init_state=None):
        ProgressBarLogger.__init__(self, init_state)
        self.gtk_bar = gtk_bar

    def bars_callback(self, bar, attr, value, old_value=None):
        percentage = value / self.bars[bar]['total']
        self.gtk_bar.set_fraction(percentage)
        while Gtk.events_pending():
            Gtk.main_iteration()
