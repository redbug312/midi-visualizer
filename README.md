# MIDI Visualizer
MIDI visualize_midi written in Gtk and Gstreamer

## Build Environment

### Linux

```bash
$ sudo apt install gstreamer1.0-plugins-bad python3-pip ffmpeg libffi-dev
$ pip3 install --user gizeh moviepy mido intervaltree
```

### Windows

1. Install Python 3.4 from
    - Noted thst PyGObject for Windows do not support Python 3.5 or above
2. Install PyGObject for Windows from
    1. Choose these items in GNOME libraries:
        - Base packages
        - Gst-plugins
        - Gst-plugins-extra
        - Gst-plugins-more
        - Gstreamer
        - GTK+
        - JSON-glib
    2. Choose none in non-GNOME libraries
    3. Choose none in development packages
3. Open the `cmd.exe` to prepare for installing dependencies
    ```batch
    > python -m pip install --upgrade pip
    > pip install requests pycparser
    ```
4. Download wheel packages from [Unofficial Windows Binaries for Python Extension Packages](https://www.lfd.uci.edu/~gohlke/pythonlibs)
    - `cffi‑1.11.5‑cp34‑cp34m‑win_amd64.whl`
    - `moviepy‑0.2.3.4‑py2.py3‑none‑any.whl`
5. Open the `cmd.exe` again to install dependencies
    ```batch
    > pip install cffi‑1.11.5‑cp34‑cp34m‑win_amd64.whl
    > pip install moviepy‑0.2.3.4‑py2.py3‑none‑any.whl
    > pip install gizeh mido intervaltree
    ```
6. Open `C:\Python34\Lib\site-packages\cairocffi\__init__.py`
    - Change line 41 and save
        ```diff
        - cairo = dlopen(ffi, 'cairo', 'cairo-2')
        + cairo = dlopen(ffi, 'cairo', 'cairo-2', 'cairo-gobject-2')
        ```

<!--TODO: links to their websites-->
## Contributes
1. Gtk framework
    - Gtk+
    - Gstreamer
2. Python libraries
    - gizeh
    - moviepy
    - mido
    - intervaltree
3. Resources
    - `midi/The Positive And Negative.mid`
    - `midi/Charming Domination.mid`
    - `soundfont/Touhou.sf2`
