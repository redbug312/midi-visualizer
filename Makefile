.PHONY: start debug test

MIDI := 'midi/The Positive and Negative.mid'
OUT  := '/tmp/test.webm'

start:
	python3 main.py
	xdg-open $(OUT) 2> /dev/null

debug:
	python3 $(FILE)

test:
	musescore $(MIDI)
