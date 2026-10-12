"""Check that everything the pipeline needs is installed. Run this first on a new machine.

    python check_env.py
"""
import importlib
import shutil
import subprocess
import sys

import os as _os, sys as _sys
_HERE = _os.path.dirname(_os.path.abspath(__file__)); _sys.path.insert(0, _HERE)
from common import default_font

ok = True


def report(name, good, hint=''):
    global ok
    ok &= good
    print(f"[{'OK' if good else 'MISSING'}] {name}" + ('' if good else f'  ->  {hint}'))


report('ffmpeg', bool(shutil.which('ffmpeg')), 'install ffmpeg: winget install Gyan.FFmpeg / brew install ffmpeg / apt install ffmpeg')
report('ffprobe', bool(shutil.which('ffprobe')), 'comes with ffmpeg')
if shutil.which('ffmpeg'):
    out = subprocess.run(['ffmpeg', '-hide_banner', '-filters'], capture_output=True, text=True).stdout
    report('ffmpeg libass (subtitles filter)', ' ass ' in out or ' subtitles ' in out, 'use a full ffmpeg build (e.g. gyan.dev "full")')
    report('ffmpeg libx264', 'libx264' in subprocess.run(['ffmpeg', '-hide_banner', '-encoders'], capture_output=True, text=True).stdout,
           'use an ffmpeg build with libx264')
for mod, pip in [('numpy', 'numpy'), ('edge_tts', 'edge-tts')]:
    try:
        importlib.import_module(mod)
        report(f'python: {mod}', True)
    except ImportError:
        report(f'python: {mod}', False, f'{sys.executable} -m pip install {pip}')
print(f'subtitle font: {default_font()}')
print('ALL GOOD' if ok else 'Fix the items above, then run again.')
sys.exit(0 if ok else 1)
