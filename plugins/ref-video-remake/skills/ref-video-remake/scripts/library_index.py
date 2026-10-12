"""Index a local material library (videos + images) and make numbered preview sheets to choose shots from.

    python library_index.py LIBRARY_DIR OUT_DIR

Writes OUT_DIR/library.json  [{id: "V07" | "I03", path, kind, width, height, duration}]
       OUT_DIR/videos_N.png  each video as a column of 3 frames (15% / 50% / 85% of its first 60 s), labelled V..
       OUT_DIR/images.png    all images, labelled I..
Look at the sheets: note what each clip shows, which ones carry burned-in text (blur those regions later),
and at which time the useful part is.
"""
import json
import os
import shutil
import sys

import os as _os, sys as _sys
_HERE = _os.path.dirname(_os.path.abspath(__file__)); _sys.path.insert(0, _HERE)
from common import media_info, need, run

need('ffmpeg', 'ffprobe')
lib, out = os.path.abspath(sys.argv[1]), os.path.abspath(sys.argv[2])
os.makedirs(os.path.join(out, '_frames'), exist_ok=True)
os.chdir(out)  # drawtext gets a relative font path (Windows drive colons break filter syntax)
VID = ('.mp4', '.mov', '.m4v', '.mkv', '.webm', '.avi')
IMG = ('.jpg', '.jpeg', '.png', '.webp', '.bmp')
files = []
for root, _, fs in os.walk(lib):
    for f in sorted(fs):
        if f.lower().endswith(VID + IMG):
            files.append(os.path.join(root, f))
items, nv, ni = [], 0, 0
font = None
if os.path.exists(r'C:\Windows\Fonts\arial.ttf'):
    shutil.copyfile(r'C:\Windows\Fonts\arial.ttf', 'label.ttf')
    font = 'label.ttf'
for p in files:
    try:
        inf = media_info(p)
    except SystemExit:
        continue
    if p.lower().endswith(VID):
        nv += 1; items.append(dict(id=f'V{nv:02d}', path=p, kind='video', **{k: inf.get(k) for k in ('width', 'height', 'duration', 'fps')}))
    else:
        ni += 1; items.append(dict(id=f'I{ni:02d}', path=p, kind='image', width=inf.get('width'), height=inf.get('height')))
json.dump(items, open(os.path.join(out, 'library.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)


def label(i):
    return f"drawtext=text='{i}':fontsize=22:fontcolor=yellow:box=1:boxcolor=black:x=2:y=2" + (
        f':fontfile={font}' if font else '')


strips = []
for it in [x for x in items if x['kind'] == 'video']:
    d = min(it['duration'] or 1, 60)
    fr = []
    for k, p in enumerate((0.15, 0.5, 0.85)):
        o = os.path.join(out, '_frames', f"{it['id']}_{k}.png")
        run(['ffmpeg', '-v', 'error', '-y', '-ss', f'{d * p:.2f}', '-i', it['path'], '-frames:v', '1',
             '-vf', 'scale=120:213:force_original_aspect_ratio=increase,crop=120:213', o])
        fr.append(o)
    s = os.path.join(out, '_frames', f"{it['id']}.png")
    run(['ffmpeg', '-v', 'error', '-y', *sum([['-i', f] for f in fr], []), '-filter_complex', f'vstack=3,{label(it["id"])}', s])
    strips.append(s)
for g in range(0, len(strips), 15):
    grp = strips[g:g + 15]
    o = os.path.join(out, f'videos_{g // 15 + 1}.png')
    run(['ffmpeg', '-v', 'error', '-y', *sum([['-i', f] for f in grp], []), '-filter_complex',
         ''.join(f'[{i}]' for i in range(len(grp))) + f'hstack={len(grp)}' if len(grp) > 1 else 'null', o])
    print('sheet', o)
imgs = [x for x in items if x['kind'] == 'image']
if imgs:
    tiles = []
    for it in imgs:
        o = os.path.join(out, '_frames', f"{it['id']}.png")
        run(['ffmpeg', '-v', 'error', '-y', '-i', it['path'], '-vf',
             f"scale=200:260:force_original_aspect_ratio=decrease,pad=200:260:-1:-1,{label(it['id'])}", o])
        tiles.append(o)
    lay = '|'.join(f'{(k % 8) * 200}_{(k // 8) * 260}' for k in range(len(tiles)))
    o = os.path.join(out, 'images.png')
    if len(tiles) == 1:
        run(['ffmpeg', '-v', 'error', '-y', '-i', tiles[0], o])
    else:
        run(['ffmpeg', '-v', 'error', '-y', *sum([['-i', f] for f in tiles], []), '-filter_complex',
             f'xstack=inputs={len(tiles)}:layout={lay}:fill=black', o])
    print('sheet', o)
for it in items:
    extra = f"{it['duration']:.1f}s" if it['kind'] == 'video' else ''
    print(f"{it['id']}  {it['width']}x{it['height']} {extra:>7}  {os.path.relpath(it['path'], lib)}")
