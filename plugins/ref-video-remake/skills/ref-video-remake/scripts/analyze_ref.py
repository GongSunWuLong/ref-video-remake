"""Analyse a reference short video so a new one can match its format and rhythm.

    python analyze_ref.py REF.mp4 OUT_DIR [--chars N]

Writes OUT_DIR/ref.json and images to look at:
  contact.png      one frame per second, tiled  -> layout, title / subtitle placement, shot style
  frames/f_*.png   full-size frames at a few moments -> measure subtitle position, font size, colours
--chars N: number of spoken characters in the reference (if you know its script) -> speech rate.
"""
import argparse
import json
import os
import re
import subprocess
import wave

import numpy as np

import os as _os, sys as _sys
_HERE = _os.path.dirname(_os.path.abspath(__file__)); _sys.path.insert(0, _HERE)
from common import media_info, need, run

need('ffmpeg', 'ffprobe')
ap = argparse.ArgumentParser()
ap.add_argument('ref'); ap.add_argument('out'); ap.add_argument('--chars', type=int, default=0)
a = ap.parse_args()
os.makedirs(os.path.join(a.out, 'frames'), exist_ok=True)

info = media_info(a.ref)
dur = info['duration']

# shot cuts
r = subprocess.run(['ffmpeg', '-hide_banner', '-i', a.ref, '-vf', "select='gt(scene,0.25)',showinfo", '-an', '-f', 'null', '-'],
                   capture_output=True, text=True, encoding='utf-8', errors='replace').stderr
cuts = [float(x) for x in re.findall(r'pts_time:([\d.]+)', r)]
cuts = [c for c in cuts if c > 0.3]
bounds = [0.0] + cuts + [dur]
shots = [round(b - a_, 2) for a_, b in zip(bounds, bounds[1:]) if b - a_ > 0.05]

# contact sheet + full frames
cols = 10
n = max(1, int(dur))
rows = (n + cols - 1) // cols
run(['ffmpeg', '-v', 'error', '-y', '-i', a.ref, '-vf', f'fps=1,scale=240:-2,tile={cols}x{rows}', '-frames:v', '1',
     os.path.join(a.out, 'contact.png')])
for t in [dur * p for p in (0.1, 0.3, 0.5, 0.7, 0.9)]:
    run(['ffmpeg', '-v', 'error', '-y', '-ss', f'{t:.2f}', '-i', a.ref, '-frames:v', '1',
         '-vf', 'drawgrid=w=iw/10:h=ih/20:t=1:c=yellow@0.5', os.path.join(a.out, 'frames', f'f_{t:05.2f}.png')])

audio = {}
if info['has_audio']:
    wav = os.path.join(a.out, 'ref_audio.wav')
    run(['ffmpeg', '-v', 'error', '-y', '-i', a.ref, '-vn', '-ac', '1', '-ar', '16000', wav])
    w = wave.open(wav); sr = w.getframerate()
    x = np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(float)
    win = sr // 10
    lev = np.array([20 * np.log10(np.sqrt((x[i:i + win] ** 2).mean()) / 32768 + 1e-9) for i in range(0, len(x) - win, win)])
    # quietest 10% of 100ms windows (ignoring digital silence): above ~-45 dB means a music bed under the voice
    quiet = float(np.percentile(lev[lev > -120], 10)) if (lev > -120).any() else -120.0
    f0 = []
    for i in range(0, len(x) - 1024, 800):
        s = x[i:i + 1024] - x[i:i + 1024].mean()
        if np.sqrt((s ** 2).mean()) < 1500:
            continue
        c = np.correlate(s, s, 'full')[1023:]
        lo, hi = sr // 400, sr // 70
        k = lo + int(np.argmax(c[lo:hi]))
        if c[k] > 0.4 * c[0]:
            f0.append(sr / k)
    pitch = float(np.median(f0)) if f0 else 0.0
    loud = subprocess.run(['ffmpeg', '-i', a.ref, '-af', 'ebur128', '-f', 'null', '-'], capture_output=True, text=True,
                          encoding='utf-8', errors='replace').stderr
    m = re.findall(r'I:\s+(-?[\d.]+) LUFS', loud)
    audio = {'loudness_lufs': float(m[-1]) if m else None, 'quiet_floor_db': round(quiet, 1),
             'has_music_bed': quiet > -45, 'voice_pitch_hz': round(pitch), 'voice_guess': 'female' if pitch > 180 else 'male'}

res = {
    'file': a.ref, 'width': info.get('width'), 'height': info.get('height'), 'fps': round(info.get('fps', 0), 3),
    'duration': round(dur, 2), 'cuts': [round(c, 2) for c in cuts], 'shot_count': len(shots),
    'avg_shot_sec': round(float(np.mean(shots)), 2) if shots else None, 'shots': shots, 'audio': audio,
}
if a.chars:
    res['chars_per_sec'] = round(a.chars / dur, 2)
json.dump(res, open(os.path.join(a.out, 'ref.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print(json.dumps(res, ensure_ascii=False, indent=1))
print(f"\nLook at {os.path.join(a.out, 'contact.png')} and frames/ to read the subtitle / title style.")
