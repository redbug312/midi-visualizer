.PHONY: start debug

start:
	python3 main.py

debug:
	env GST_DEBUG_DUMP_DOT_DIR=/tmp python3 main.py
	dot -Tpng /tmp/pipeline.dot > /tmp/pipeline.png
	xdg-open /tmp/pipeline.png
