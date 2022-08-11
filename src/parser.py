#!/usr/bin/env python3
import mido
import intervaltree


class Note:
    def __init__(self, begin, end, index):
        self.begin = begin
        self.end = end
        self.index = index

    def __lt__(self, other):
        return self.end < other.end

    def __repr__(self):
        return 'Note(%s, %d..%d)' % (self.index, self.begin, self.end)


class Midi():
    def __init__(self, file=None):
        self.midi = None
        self.notes = list()
        self.metas = intervaltree.IntervalTree()    # indexed by second intervals
        self.timeline = intervaltree.IntervalTree() # indexed by tick intervals
        self.pending_notes = dict()
        if file:
            self.parse(file)

    def parse(self, file):
        self.midi = mido.MidiFile(file)

        tick = 0
        count_notes = 0
        current_meta = {'tempo': 500000}
        meta_messages = [(tick, dict(current_meta))]

        for track_num, track in enumerate(self.midi.tracks):
            for message in track:
                tick += message.time
                if message.type == 'note_on':
                    self.notes.append({'note' : message.note,
                                       'track': track_num})
                    self.pending_notes[message.note] = (count_notes, tick)  # index, begin_tick
                    count_notes += 1
                elif message.type == 'note_off':
                    try:
                        assert message.note in self.pending_notes, 'a note_off before note_on'
                    except AssertionError:
                        continue
                    index, begin = self.pending_notes[message.note]
                    if tick > begin:
                        self.timeline[begin:tick] = index
                    del self.pending_notes[message.note]
                elif message.type == 'set_tempo':
                    current_meta['tempo'] = message.tempo
                    meta_messages.append((tick, dict(current_meta)))
                elif message.type == 'end_of_track':
                    try:
                        assert not self.pending_notes, 'no note_off after note_on'
                    except AssertionError:
                        self.pending_notes = dict()
                    meta_messages.append((tick, dict(current_meta)))
                    tick = 0

        lasttime_sec = 0.0

        for prev_meta, curr_meta in zip(meta_messages, meta_messages[1:]):
            interval_sec = mido.tick2second(curr_meta[0] - prev_meta[0],
                                            self.midi.ticks_per_beat,
                                            prev_meta[1]['tempo'])
            try:
                self.metas[lasttime_sec : lasttime_sec + interval_sec] = \
                    dict(prev_meta[1], ticks=(prev_meta[0], curr_meta[0]))
            except ValueError:  # interval_sec is not a positive number
                continue
            lasttime_sec += interval_sec

        try:
            assert abs(lasttime_sec - self.midi.length) < 1, 'wrong mapping from seconds to ticks'
        except AssertionError:
            pass

    def second2tick(self, time):
        # TODO move to Visualizer and avoid intervaltree lookup
        # or maintain Note time unit in sec
        index = min(time, self.metas.end() - 1)
        meta = next(iter(self.metas[index]))
        secs, ticks = (meta[0], meta[1]), meta[2]['ticks']
        return ticks[0] + (ticks[1] - ticks[0]) * (time - secs[0]) / (secs[1] - secs[0])
