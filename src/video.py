#!/usr/bin/env python3
import gizeh
import moviepy.editor as mpy
from heapq import heappush, heappop
from more_itertools import peekable, first
from parser import Note
from itertools import count
import numpy as np

IS_IVORY_KEYS = [x not in [1, 3, 6, 8, 10] for x in range(12)]

is_ebony = lambda pitch: not IS_IVORY_KEYS[pitch % 12]
is_ivory = lambda pitch: IS_IVORY_KEYS[pitch % 12]

NEAR_EBONY_KEYS = [[] for _ in range(12)]
for ebony in [1, 3, 6, 8, 10]:
    NEAR_EBONY_KEYS[ebony + 1].append(-1)
    NEAR_EBONY_KEYS[ebony - 1].append(1)

OFFSET = [0.0] * 110

ivory = filter(is_ivory, range(21, 109))
ivory_offsets = count(start=0.5)
ebony = filter(is_ebony, range(21, 109))
ebony_offsets = filter(lambda x: x % 7 not in [2, 5], count(start=1))

for pitch, off in zip(ivory, ivory_offsets):
    OFFSET[pitch] = off / 52

for pitch, off in zip(ebony, ebony_offsets):
    OFFSET[pitch] = off / 52

PALETTE = {
    'ivory': [
        (0.93, 0.77, 0.45),  #F0C674
        (0.53, 0.74, 0.71),  #8ABEB7
        (0.69, 0.57, 0.73),  #B294BB
        (0.50, 0.63, 0.74),  #81A2BE
        (0.79, 0.80, 0.79),  #CBCFCC, for idle keys
    ],
    'ebony': [
        (0.86, 0.57, 0.37),  #DE935F
        (0.36, 0.55, 0.52),  #5E8D87
        (0.51, 0.40, 0.55),  #85678F
        (0.37, 0.50, 0.61),  #5F819D
        (0.22, 0.24, 0.25),  #3A3E42, for idle keys
    ],
}


class ForeseePart:
    def __init__(self, midi, size):
        self.midi = midi
        self.size = size
        self.notes = list()
        all_notes = [Note(i[0], i[1], i[2]) for i in midi.timeline.items()]
        all_notes = sorted(all_notes, key=lambda n: n.begin)
        self.waits = peekable(all_notes)
        self.foresee = 2  # sec

    def make_frame(self, time):
        now = self.midi.second2tick(time)
        future = self.midi.second2tick(time + self.foresee)
        NONE = Note(float('inf'), float('inf'), 0)

        while first(self.notes, NONE).end < now:
            heappop(self.notes)
        while self.waits.peek(NONE).begin <= future:
            note = next(self.waits)
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
        track = self.midi.notes[note.index]['track']
        material = 'ivory' if is_ivory(pitch) else 'ebony'
        color = PALETTE[material][track % 4]

        lx = w / 52 if is_ivory(pitch) else w / 52 * 0.7
        ly = h * (end - begin) / (future - now) - 5
        xy = (w * OFFSET[pitch],
              h * (future - end / 2 - begin / 2) / (future - now))
        fill = color

        return gizeh.rectangle(lx=lx, ly=ly, xy=xy, fill=fill)


class PianoPart:
    def __init__(self, midi, size):
        self.midi = midi
        self.size = size
        self.notes = list()
        all_notes = [Note(i[0], i[1], i[2]) for i in midi.timeline.items()]
        all_notes = sorted(all_notes, key=lambda n: n.begin)
        self.waits = peekable(all_notes)
        self.idle_piano = self.init_idle_piano()

    def make_frame(self, time):
        now = self.midi.second2tick(time)
        NONE = Note(float('inf'), float('inf'), 0)

        while first(self.notes, NONE).end < now:
            heappop(self.notes)
        while self.waits.peek(NONE).begin <= now:
            note = next(self.waits)
            heappush(self.notes, note)

        redraw_ivory = {}
        redraw_ebony = {}
        for note in self.notes:
            pitch = self.midi.notes[note.index]['note']
            if is_ivory(pitch):
                redraw_ivory[pitch] = note
                for neighbor in NEAR_EBONY_KEYS[pitch % 12]:
                    if pitch + neighbor not in redraw_ebony:
                        redraw_ebony[pitch + neighbor] = None
            else:
                redraw_ebony[pitch] = note

        surface = gizeh.Surface(*self.size)
        arr = np.frombuffer(surface._cairo_surface.get_data(), np.uint8)
        arr += self.idle_piano
        surface._cairo_surface.mark_dirty()

        for pitch, note in redraw_ivory.items():
            rect = self.spawn_ivory_key(pitch, note)
            rect.draw(surface)
        for pitch, note in redraw_ebony.items():
            rect = self.spawn_ebony_key(pitch, note)
            rect.draw(surface)

        return surface.get_npimage()

    def init_idle_piano(self):
        surface = gizeh.Surface(*self.size)
        for pitch in filter(is_ivory, range(21, 109)):
            rect = self.spawn_ivory_key(pitch, None)
            rect.draw(surface)
        for pitch in filter(is_ebony, range(21, 109)):
            rect = self.spawn_ebony_key(pitch, None)
            rect.draw(surface)

        w, h = self.size
        image = surface.get_npimage()
        image = image[:, :, [2, 1, 0]]
        image = np.dstack([image, 255 * np.ones((h, w), dtype=np.uint8)])
        image = image.flatten()
        return image

    def spawn_ivory_key(self, pitch, note=None):
        w, h = self.size
        color = PALETTE['ivory'][-1]
        if note:
            pitch = self.midi.notes[note.index]['note']
            track = self.midi.notes[note.index]['track']
            material = 'ivory' if is_ivory(pitch) else 'ebony'
            color = PALETTE[material][track % 4]

        lx = w / 52
        ly = h
        xy = (w * OFFSET[pitch], h / 2)
        fill = color
        stroke = PALETTE['ebony'][-1]
        stroke_width = 1
        return gizeh.rectangle(lx=lx, ly=ly, xy=xy, fill=fill, stroke=stroke,
                               stroke_width=stroke_width)

    def spawn_ebony_key(self, pitch, note=None):
        w, h = self.size
        color = PALETTE['ebony'][-1]
        if note:
            pitch = self.midi.notes[note.index]['note']
            track = self.midi.notes[note.index]['track']
            material = 'ivory' if is_ivory(pitch) else 'ebony'
            color = PALETTE[material][track % 4]

        lx = w / 52 * 0.7
        ly = h * 2 / 3
        xy = (w * OFFSET[pitch], h / 3)
        fill = color
        return gizeh.rectangle(lx=lx, ly=ly, xy=xy, fill=fill)


def midi_videoclip(midi, size=(640, 360)):
    lower_size = (size[0], int(size[0] / 52 * 6))
    upper_size = (size[0], size[1] - lower_size[1])
    lower_part = PianoPart(midi, lower_size)
    upper_part = ForeseePart(midi, upper_size)

    duration = midi.midi.length  # expensive call
    upper_clip = mpy.VideoClip(upper_part.make_frame, duration=duration)
    lower_clip = mpy.VideoClip(lower_part.make_frame, duration=duration)
    final_clip = mpy.clips_array([[upper_clip], [lower_clip]])

    return final_clip


if __name__ == '__main__':
    from parser import Midi
    midi = Midi('midi/at-the-end-of-the-spring.mid')
    clip = midi_videoclip(midi)
    clip.write_videofile('/tmp/test.mp4', fps=30, audio=False)
