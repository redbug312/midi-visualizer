#!/usr/bin/env python3
import gizeh
import moviepy.editor as mpy
import midi


def visualize_midi(midi, size):
    def make_frame(t):
        surface = gizeh.Surface(*size)
        current, future = midi.second2tick(t), midi.second2tick(t+4)
        for begin, end, note in midi.timeline[current:future]:
            try:
                assert future is not None
            except AssertionError:  # future exceeds midi length
                future = 2 * current - midi.second2tick(t-4)
            begin, end, note = max(begin, current), min(end, future), midi.notes[note]
            rect_params = {
                'lx'  : 5,
                'ly'  : size[1] * (end - begin) / (future - current) - 3,
                'xy'  : (size[0] * (note['note'] - 21) / 87,
                         size[1] * (future - end/2 - begin/2) / (future - current)),
                'fill': (0, 1, 0)
            }
            gizeh.rectangle(**rect_params).draw(surface)
        return surface.get_npimage()
    return make_frame

def midi_videoclip(sheet, size=(640, 360)):
    clip = mpy.VideoClip(visualize_midi(sheet, size), duration=sheet.midi.length)
    clip.write_videofile('/tmp/test.webm', fps=15)
