"""Verify a finished video by decoding it completely (never trust container headers or a few sampled frames).

    python verify.py OUT.mp4 --voice VO.mp3 [--segments segments.json] [--strip strip.png]

Checks (exit code 1 if any fails):
  * decoded audio length ~= video length ~= frame_count / fps
  * no gaps or jumps in audio packet / video frame timestamps
  * the voice inside the video has the same rhythm as the source voice file (envelope correlation >= 0.85),
    i.e. it was not sped up, truncated or swapped for another file
Also writes a strip of frames, one at the middle of each subtitle segment, to look at.
"""
import argparse
import json
import os
import subprocess
import wave

import numpy as np

import os as _os, sys as _sys
_HERE = _os.path.dirname(_os.path.abspath(__file__)); _sys.path.insert(0, _HERE)
from common import media_info, run

ap = argparse.ArgumentParser()
ap.add_argument('video'); ap.add_argument('--voice'); ap.add_argument('--segments'); ap.add_argument('--strip')
a = ap.parse_args()
fails = []
info = media_info(a.video)
fps = info['fps']
print(f"container: {info['width']}x{info['height']} {fps:.2f}fps {info['duration']:.3f}s")

tmpd = os.path.splitext(a.video)[0] + '_verify'
os.makedirs(tmpd, exist_ok=True)
wav = os.path.join(tmpd, 'a.wav')
run(['ffmpeg', '-v', 'error', '-y', '-i', a.video, '-vn', '-ac', '1', '-ar', '16000', wav])
w = wave.open(wav); audio_len = w.getnframes() / w.getframerate()
x = np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(float)
r = subprocess.run(['ffmpeg', '-i', a.video, '-map', '0:v', '-f', 'null', '-'], capture_output=True, text=True, errors='replace').stderr
import re
frames = int(re.findall(r'frame=\s*(\d+)', r)[-1])
video_len = frames / fps
print(f'decoded: audio {audio_len:.3f}s, video {frames} frames = {video_len:.3f}s')
if abs(audio_len - video_len) > 0.25:
    fails.append(f'audio ({audio_len:.2f}s) and video ({video_len:.2f}s) lengths differ')


def gaps(stream, lo, hi):
    out = subprocess.run(['ffprobe', '-v', 'error', '-select_streams', stream, '-show_entries',
                          'packet=pts_time,duration_time' if stream == 'a' else 'frame=pts_time', '-of', 'csv=p=0', a.video],
                         capture_output=True, text=True).stdout.split()
    ts = sorted(float(l.split(',')[0]) for l in out if l.split(',')[0] not in ('', 'N/A'))
    d = np.diff(ts)
    return int(((d > hi) | (d < lo)).sum()) if len(d) else 0


ga = gaps('a', 0.0, 0.03)
gv = gaps('v', 1 / fps - 0.002, 1 / fps + 0.002)
print(f'timestamp gaps: audio {ga}, video {gv}')
if ga:
    fails.append(f'{ga} audio timestamp gaps')
if gv:
    fails.append(f'{gv} video timestamp gaps')

if a.voice:
    vw = os.path.join(tmpd, 'v.wav')
    run(['ffmpeg', '-v', 'error', '-y', '-i', a.voice, '-ac', '1', '-ar', '16000', vw])
    vv = wave.open(vw); y = np.frombuffer(vv.readframes(vv.getnframes()), np.int16).astype(float)
    n = min(len(x), len(y))
    env = lambda s: np.array([np.sqrt((s[i:i + 1600] ** 2).mean()) for i in range(0, n - 1600, 1600)])
    c = float(np.corrcoef(env(x[:n]), env(y[:n]))[0, 1])
    print(f'voice rhythm match: {c:.3f} (voice file {len(y) / 16000:.2f}s)')
    if c < 0.85:
        fails.append(f'voice inside the video does not follow the voice file (corr {c:.2f})')

if a.segments:
    segs = json.load(open(a.segments, encoding='utf-8'))
    tiles = []
    for i, s in enumerate(segs):
        o = os.path.join(tmpd, f'm{i:02d}.png')
        run(['ffmpeg', '-v', 'error', '-y', '-ss', f"{(s['start'] + s['end']) / 2:.3f}", '-i', a.video, '-frames:v', '1',
             '-vf', 'scale=180:-2', o])
        tiles.append(o)
    strip = a.strip or os.path.join(tmpd, 'strip.png')
    run(['ffmpeg', '-v', 'error', '-y', *sum([['-i', t] for t in tiles], []), '-filter_complex',
         ''.join(f'[{i}]' for i in range(len(tiles))) + f'hstack={len(tiles)}' if len(tiles) > 1 else 'null', strip])
    print('frame strip:', strip)

loud = subprocess.run(['ffmpeg', '-i', a.video, '-af', 'ebur128', '-f', 'null', '-'], capture_output=True, text=True, errors='replace').stderr
m = re.findall(r'I:\s+(-?[\d.]+) LUFS', loud)
print(f"loudness: {m[-1] if m else '?'} LUFS")
print('PASS' if not fails else 'FAIL:\n  ' + '\n  '.join(fails))
raise SystemExit(1 if fails else 0)
