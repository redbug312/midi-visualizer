#!/usr/bin/env python3
import gizeh
import moviepy.editor as mpy
import numpy as np
import midi


def visualize_midi(midi, size):
    def make_frame(t):
        surface = gizeh.Surface(*size)
        current, future = midi.second2tick(t), midi.second2tick(t+3)
        for begin, end, note in midi.timeline[current:future]:
            try:
                assert future is not None
            except AssertionError:  # future exceeds midi length
                future = 2 * current - midi.second2tick(t-3)

            begin, end, note = max(begin, current), min(end, future), midi.notes[note]
            rect_params = {
                'lx'  : 5,
                'ly'  : size[1] * (end - begin) / (future - current) - 5,
                'xy'  : (size[0] * (note['note'] - 21) / 87,
                         size[1] * (future - end/2 - begin/2) / (future - current)),
                'fill': (0, 1, 0)
            }
            gizeh.rectangle(**rect_params).draw(surface)
        return surface.get_npimage()
    return make_frame


def midi_videoclip(sheet, size=(640, 360), iter_callback=None):
    clip = mpy.VideoClip(visualize_midi(sheet, size), duration=sheet.midi.length)

    # callback function is for refreshing gtk progressing bar
    # the following code is altered from github.com/Zulko/moviepy/blob/6cbd4f347735e8bdd8224589f986e42addbec8a1/moviepy/Clip.py#L446
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

# sheet = midi.Midi('midi/The Positive and Negative.mid')
# clip = midi_videoclip(sheet)
# clip.write_videofile('/tmp/test.webm', fps=20)
