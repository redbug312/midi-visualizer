#!/usr/bin/env python3
import midi
import video

sheet = midi.Midi('midi/The Positive and Negative.mid')
video.midi_videoclip(sheet)
