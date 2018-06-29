#!/usr/bin/env python3
import gizeh
import moviepy.editor as mpy
import numpy as np
import midi


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


def foresee_surface(midi, size, offset, time):
    surface = gizeh.Surface(*size)
    foresee = 2
    current, future = midi.second2tick(time), midi.second2tick(time + foresee)
    for begin, end, note in midi.timeline[current:future]:
        future = future or 2 * current - midi.second2tick(time - foresee)

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


def piano_surface(midi, size, offset, time):
    surface = gizeh.Surface(*size)
    current = midi.second2tick(time)
    hit_note_colors = {
        midi.notes[interval[2]]['note']: track_colors[midi.notes[interval[2]]['track'] % 4]
        for interval in midi.timeline[current]
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


def visualize_midi(midi, size):
    piano_size     = (size[0], int(size[0]/52 * 6))
    piano_offset   = (0, 0)
    foresee_size   = (size[0], size[1] - piano_size[1])
    foresee_offset = (0, 0)

    def make_frame(t):
        foresee = foresee_surface(midi, foresee_size, foresee_offset, t).get_npimage()
        piano = piano_surface(midi, piano_size, piano_offset, t).get_npimage()
        return np.concatenate((foresee, piano), axis=0)

    return make_frame


def midi_videoclip(sheet, size=(640, 360), iter_callback=None):
    clip = mpy.VideoClip(visualize_midi(sheet, size), duration=sheet.midi.length)

    # callback function is for refreshing gtk progressing bar
    # the following code is altered from moviepy/Clip.py:446
    if iter_callback is not None:
        def my_iter_frames(fps=None, with_times=False, progress_bar=False, dtype=None):
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


# Test script
# sheet = midi.Midi('midi/The Positive and Negative.mid')
# clip = midi_videoclip(sheet)
# clip.write_videofile('/tmp/test.webm', fps=20)
