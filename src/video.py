#!/usr/bin/env python3
import gizeh
import moviepy.editor as mpy
import numpy as np


RGB = lambda hx: tuple(map(lambda c: int(c, 16) / 256, [hx[1:3], hx[3:5], hx[5:7]]))
is_ebony = lambda note: (note % 12) in [1, 3, 6, 8, 10]
is_ivory = lambda note: not is_ebony(note)

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


class Visualizer:
    def __init__(self, midi, size):
        self.midi = midi
        self.size = size
        self.piano_size     = (size[0], int(size[0]/52 * 6))
        self.piano_offset   = (0, 0)
        self.foresee_size   = (size[0], size[1] - self.piano_size[1])
        self.foresee_offset = (0, 0)
        all_notes = [Note(i[0], i[1], i[2]) for i in midi.timeline.items()]
        all_notes = sorted(all_notes, key=lambda n: n.begin)
        self.notes = peekable(all_notes)
        self.notes_hit = peekable(all_notes)
        self.queue_wait = list()
        self.queue_hit = list()

    def foresee_surface(self, time, notes):
        midi = self.midi
        size = self.foresee_size
        offset = self.foresee_offset
        surface = gizeh.Surface(*size)
        foresee = 2
        current, future = midi.second2tick(time), midi.second2tick(time + foresee)
        for note in notes:
            begin, end, note = note.begin, note.end, note.index
            # future = future or 2 * current - midi.second2tick(time - foresee)

            begin, end = max(begin, current), min(end, future)
            note, colors = midi.notes[note]['note'], track_colors[midi.notes[note]['track'] % 4]
            rect_params = {
                'lx'  : size[0]/52 if is_ivory(note) else size[0]/52 * 0.7,
                'ly'  : size[1] * (end - begin) / (future - current) - 5,
                'xy'  : (size[0] * position[note] + offset[0],
                         size[1] * (future - end/2 - begin/2) / (future - current) + offset[1]),
                'fill': colors[1] if is_ivory(note) else colors[0]
            }
            gizeh.rectangle(**rect_params).draw(surface)
        return surface


    def piano_surface(self, time, notes):
        midi = self.midi
        size = self.piano_size
        surface = gizeh.Surface(*size)
        hit_note_colors = {
            midi.notes[interval.index]['note']:
            track_colors[midi.notes[interval.index]['track'] % 4]
            for interval in notes
        }

        ivory_params = lambda note: {
            'lx'    : size[0]/52,
            'ly'    : size[1],
            'xy'    : (size[0] * position[note], size[1] / 2),
            'fill'  : hit_note_colors[note][1] if note in hit_note_colors.keys() else RGB('#CBCFCC'),
            'stroke': RGB('#3A3E42'),
            'stroke_width': 1
        }
        ebony_params = lambda note: {
            'lx'  : size[0]/52 * 0.7,
            'ly'  : size[1] * 2/3,
            'xy'  : (size[0] * position[note], size[1] / 3),
            'fill': hit_note_colors[note][0] if note in hit_note_colors.keys() else RGB('#3A3E42')
        }

        for note in filter(is_ivory, range(21, 109)):
            gizeh.rectangle(**ivory_params(note)).draw(surface)
        for note in filter(is_ebony, range(21, 109)):
            gizeh.rectangle(**ebony_params(note)).draw(surface)
        return surface


    def make_frame(self, time):
        midi = self.midi
        foresee = 2
        current = midi.second2tick(time)
        future = midi.second2tick(time + foresee)
        # print(time, current, future)
        NONE = Note(float('inf'), float('inf'), 0)

        while first(self.queue_wait, NONE).end < current:
            heappop(self.queue_wait)
        while self.notes.peek(NONE).begin <= future:
            note = next(self.notes)
            heappush(self.queue_wait, note)

        while first(self.queue_hit, NONE).end < current:
            # print(self.queue_hit[0][1] < current, self.queue_hit[0][1], current)
            heappop(self.queue_hit)
        while self.notes_hit.peek(NONE).begin <= current:
            note = next(self.notes_hit)
            heappush(self.queue_hit, note)

        # print(self.queue_wait)

        # qw = {n.index for n in self.queue_wait}
        # qh= {n.index for n in self.queue_hit}
        # tw = {i[2] for i in midi.timeline[current:future]}
        # th = {i[2] for i in midi.timeline[current]}
        # assert(qw == tw)
        # print(self.queue_wait)
        # print(midi.timeline[current:future])
        # assert(qh == th)

        # print(current, future)
        # print(sorted(notes_hit))
        # print(self.queue_hit)
        # assert(sorted(notes_hit) == sorted(self.queue_hit))
        foresee = self.foresee_surface(time, self.queue_wait).get_npimage()
        piano = self.piano_surface(time, self.queue_hit).get_npimage()
        # TODO stack two video clips
        return np.concatenate((foresee, piano), axis=0)


def midi_videoclip(sheet, size=(640, 360), iter_callback=None):
    vis = Visualizer(sheet, size)
    clip = mpy.VideoClip(lambda t: vis.make_frame(t), duration=sheet.midi.length)

    # callback function is for refreshing gtk progressing bar
    # the following code is altered from moviepy/Clip.py:446
    # TODO move callback into make_frame
    if iter_callback is not None:
        def my_iter_frames(fps=None, with_times=False, progress_bar=False,
                           dtype=None, logger=None):
            clip.nframes = int(clip.duration * fps) + 1

            def generator():
                for t in np.arange(0, clip.duration, 1.0 / fps):
                    iter_callback(clip)
                    frame = clip.get_frame(t)
                    if (dtype is not None) and (frame.dtype != dtype):
                        frame = frame.astype(dtype)
                    if with_times:
                        yield t, frame
                    else:
                        yield frame

            return generator()

        clip.iter_frames = my_iter_frames

    return clip


if __name__ == '__main__':
    # import os
    # import gi
    # gi.require_version('Gst', '1.0')
    # gi.require_version('Gtk', '3.0')
    # from gi.repository import Gst, Gtk, GLib
    from parser import Midi

    sheet = Midi('midi/The Positive and Negative.mid')
    # clip = midi_videoclip(sheet, iter_callback=None)
    # clip.write_videofile('/tmp/test.webm', fps=20)
