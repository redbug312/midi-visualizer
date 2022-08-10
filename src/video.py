#!/usr/bin/env python3
import gizeh
import moviepy.editor as mpy
import numpy as np


RGB = lambda hx: tuple(map(lambda c: int(c, 16) / 256, [hx[1:3], hx[3:5], hx[5:7]]))
is_ebony = lambda pitch: (pitch % 12) in [1, 3, 6, 8, 10]
is_ivory = lambda pitch: not is_ebony(pitch)

position = dict()
position.update({ivory: (index + 0.5) / 52 for index, ivory in enumerate(filter(is_ivory, range(21, 109)))})
position.update({ebony: index / 52 for index, ebony in zip(filter(lambda x: x % 7 not in [2, 5], range(1, 52)),
                                                           filter(is_ebony, range(21, 109)))})
track_colors = [
    (RGB('#DE935F'), RGB('#F0C674')),
    (RGB('#5E8D87'), RGB('#8ABEB7')),
    (RGB('#85678F'), RGB('#B294BB')),
    (RGB('#5F819D'), RGB('#81A2BE'))
]


from heapq import heappush, heappop
from more_itertools import peekable, first
from parser import Note


class ForeseePart:
    def __init__(self, midi, size):
        self.midi = midi
        self.size = size
        self.notes = list()
        all_notes = [Note(i[0], i[1], i[2]) for i in midi.timeline.items()]
        all_notes = sorted(all_notes, key=lambda n: n.begin)
        self.waits = peekable(all_notes)
        self.foresee = 2  # sec
        self.callback = lambda _: None

    def inject_callback(self, func):
        self.callback = func

    def make_frame(self, time):
        self.callback(time)
        now = self.midi.second2tick(time)
        future = self.midi.second2tick(time + self.foresee)
        NONE = Note(float('inf'), float('inf'), 0)

        while first(self.notes, NONE).end < now:
            heappop(self.notes)
        while self.waits.peek(NONE).begin <= future:
            note = self.waits.next()
            heappush(self.notes, note)

        surface = gizeh.Surface(*self.size)
        for note in self.notes:
            rect = self.spawn_rectangle(note, now, future)
            rect.draw(surface)
        return surface.get_npimage()

    def spawn_rectangle(self, note, now, future):
        w, h = self.size
        begin, end = max(note.begin, now), min(note.end, future)
        pitch = self.midi.notes[note.index]['note']
        color = track_colors[self.midi.notes[note.index]['track'] % 4]

        lx = w / 52 if is_ivory(pitch) else w / 52 * 0.7
        ly = h * (end - begin) / (future - now) - 5
        xy = (w * position[pitch],
              h * (future - end / 2 - begin / 2) / (future - now))
        fill = color[1] if is_ivory(pitch) else color[0]

        return gizeh.rectangle(lx=lx, ly=ly, xy=xy, fill=fill)


class PianoPart:
    def __init__(self, midi, size):
        self.midi = midi
        self.size = size
        self.notes = list()
        all_notes = [Note(i[0], i[1], i[2]) for i in midi.timeline.items()]
        all_notes = sorted(all_notes, key=lambda n: n.begin)
        self.waits = peekable(all_notes)

    def make_frame(self, time):
        now = self.midi.second2tick(time)
        NONE = Note(float('inf'), float('inf'), 0)

        while first(self.notes, NONE).end < now:
            heappop(self.notes)
        while self.waits.peek(NONE).begin <= now:
            note = self.waits.next()
            heappush(self.notes, note)

        hits = {
            self.midi.notes[note.index]['note']: note for note in self.notes
        }

        surface = gizeh.Surface(*self.size)
        for pitch in filter(is_ivory, range(21, 109)):
            note = hits[pitch] if pitch in hits else None
            rect = self.spawn_ivory_key(pitch, note)
            rect.draw(surface)
        for pitch in filter(is_ebony, range(21, 109)):
            note = hits[pitch] if pitch in hits else None
            rect = self.spawn_ebony_key(pitch, note)
            rect.draw(surface)
        return surface.get_npimage()

    def spawn_ivory_key(self, pitch, note=None):
        w, h = self.size
        color = RGB('#CBCFCC')
        if note:
            # pitch = self.midi.notes[note.index]['note']
            color = track_colors[self.midi.notes[note.index]['track'] % 4][1]

        lx = w / 52
        ly = h
        xy = (w * position[pitch], h / 2)
        fill = color
        stroke = RGB('#3A3E42')
        stroke_width = 1
        return gizeh.rectangle(lx=lx, ly=ly, xy=xy, fill=fill, stroke=stroke,
                               stroke_width=stroke_width)

    def spawn_ebony_key(self, pitch, note=None):
        w, h = self.size
        color = RGB('#3A3E42')
        if note:
            # pitch = self.midi.notes[note.index]['note']
            color = track_colors[self.midi.notes[note.index]['track'] % 4][0]

        lx = w / 52 * 0.7
        ly = h * 2 / 3
        xy = (w * position[pitch], h / 3)
        fill = color
        return gizeh.rectangle(lx=lx, ly=ly, xy=xy, fill=fill)


def midi_videoclip(midi, size=(640, 360), iter_callback=lambda _: None):
    lower_size = (size[0], int(size[0] / 52 * 6))
    upper_size = (size[0], size[1] - lower_size[1])
    lower_part = PianoPart(midi, lower_size)
    upper_part = ForeseePart(midi, upper_size)

    duration = midi.midi.length  # expensive call
    upper_part.inject_callback(lambda t: iter_callback(t / duration))

    upper_clip = mpy.VideoClip(upper_part.make_frame, duration=duration)
    lower_clip = mpy.VideoClip(lower_part.make_frame, duration=duration)
    final_clip = mpy.clips_array([[upper_clip], [lower_clip]])

    return final_clip


if __name__ == '__main__':
    # import os
    # import gi
    # gi.require_version('Gst', '1.0')
    # gi.require_version('Gtk', '3.0')
    # from gi.repository import Gst, Gtk, GLib
    from parser import Midi

    sheet = Midi('midi/The Positive and Negative.mid')
    clip = midi_videoclip(sheet)
    clip.write_videofile('/tmp/test.webm', fps=20)
