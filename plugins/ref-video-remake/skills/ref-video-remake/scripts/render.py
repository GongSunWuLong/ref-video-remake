"""Render a short video from plan.json (see references/plan-format.md).

    python render.py plan.json

Pipeline: one clip per shot (scaled/cropped to the output size, burned-in text blurred, stills animated)
-> concat -> subtitles/title burned with libass -> voice (+ optional BGM) mixed to a clean WAV first -> mux.
The audio is always rendered to a WAV before muxing: filtering audio in the final mux step (loudnorm + apad +
atrim there) once produced files whose audio was only a few seconds long, stretched over the whole timeline.
Always run verify.py on the result.
"""
import json
import os
import subprocess
import sys

import os as _os, sys as _sys
_HERE = _os.path.dirname(_os.path.abspath(__file__)); _sys.path.insert(0, _HERE)
from common import default_font, media_info, need, run

need('ffmpeg', 'ffprobe')
plan_path = os.path.abspath(sys.argv[1])
BASE = os.path.dirname(plan_path)
P = json.load(open(plan_path, encoding='utf-8'))


LIB = {}
if P.get('library'):  # lets shots say "V24" / "I09" (ids from library_index.py) instead of full paths
    lp = P['library'] if os.path.isabs(P['library']) else os.path.join(BASE, P['library'])
    LIB = {it['id']: it['path'] for it in json.load(open(lp, encoding='utf-8'))}


def path(p):
    if p in LIB:
        return LIB[p]
    return p if os.path.isabs(p) else os.path.normpath(os.path.join(BASE, p))


W, H = P.get('size', [720, 1280])
FPS = P.get('fps', 30)
K = W / 720.0  # style sizes below are defined for a 720-wide frame
TMP = path(P.get('work_dir', '_render'))
os.makedirs(TMP, exist_ok=True)
ENC = ['-c:v', 'libx264', '-preset', 'fast', '-crf', '15', '-pix_fmt', 'yuv420p', '-r', str(FPS), '-an']
segs = P['segments'] if isinstance(P['segments'], list) else json.load(open(path(P['segments']), encoding='utf-8'))
shots_in = P['shots']
if len(shots_in) != len(segs):
    raise SystemExit(f'plan has {len(shots_in)} shot entries for {len(segs)} subtitle segments; they must match 1:1')
END = segs[-1]['end']

# ---- expand shots: an entry may be one shot, a list of shots (split the segment evenly), or "prev"/"next"
parts = []
for seg, sh in zip(segs, shots_in):
    a, b = seg['start'], seg['end']
    if sh in ('prev', 'next'):
        parts.append([sh, a, b])
    elif isinstance(sh, list):
        step = (b - a) / len(sh)
        parts += [[s, a + i * step, a + (i + 1) * step] for i, s in enumerate(sh)]
    else:
        parts.append([sh, a, b])
for i, p in enumerate(parts):
    if p[0] == 'prev':
        parts[i - 1][2] = p[2]
for i in range(len(parts) - 1, -1, -1):
    if parts[i][0] == 'next':
        parts[i + 1][1] = parts[i][1]
parts = [p for p in parts if p[0] not in ('prev', 'next')]


def conv_fps(src):
    f = media_info(src).get('fps', 30)
    return 'fps=30' if abs(f - FPS) < 0.5 or f > 45 else f'framerate=fps={FPS}'  # blend frames for 24/25 fps sources


def blur_chain(boxes, inp):
    chain, cur = '', inp
    for k, (x, y, w, h) in enumerate(boxes or []):
        chain += f"[{cur}]split[m{k}][c{k}];[c{k}]crop={w}:{h}:{x}:{y},boxblur=18:3[b{k}];[m{k}][b{k}]overlay={x}:{y}[q{k}];"
        cur = f'q{k}'
    return chain, cur


def render_shot(s, dur, out):
    frames = round(dur * FPS)
    if 'video' in s:
        src = path(s['video'])
        chain, cur = blur_chain(s.get('blur'), '0:v')
        if s.get('region'):  # use only part of the source (e.g. a letterboxed news clip); fill the rest with its blur
            x, y, w, h = s['region']
            chain += (f"[{cur}]crop={w}:{h}:{x}:{y},split[ra][rb];[ra]scale={W}:{H}:force_original_aspect_ratio=increase,"
                      f"crop={W}:{H},gblur=sigma=25,eq=brightness=-0.15[rbg];[rb]scale={W}:-2:flags=lanczos[rfg];"
                      f"[rbg][rfg]overlay=0:(H-h)/2-{int(40 * K)},setsar=1,{conv_fps(src)}[out]")
        else:
            chain += (f"[{cur}]scale={W}:{H}:force_original_aspect_ratio=increase:flags=lanczos,crop={W}:{H},"
                      f"setsar=1,{conv_fps(src)}[out]")
        run(['ffmpeg', '-v', 'error', '-y', '-ss', str(s.get('start', 0)), '-i', src, '-frames:v', str(frames),
             '-filter_complex', chain, '-map', '[out]', *ENC, out])
    elif 'image' in s:
        chain, cur = blur_chain(s.get('blur'), '0:v')
        S = 2  # draw at 2x and scale down so slow sub-pixel motion stays smooth
        CW, CH = W * S, H * S
        fw = int(CW * s.get('width', 0.92)) // 2 * 2
        if s.get('motion', 'slide') == 'slide':  # slides in from the right with a cubic ease-out, then drifts left
            T = 0.45
            x = f"(W-w)/2+W*pow(1-min(t/{T}\\,1)\\,3)+{int(30 * K * S)}*(1-t/{dur:.3f})-{int(15 * K * S)}"
            fg = f"[b]scale={fw}:-2:flags=lanczos,unsharp=5:5:0.6[fg]"
        else:  # slow push-in
            x = '(W-w)/2'
            fg = f"[b]unsharp=5:5:0.5,scale=w='trunc({fw}*(1+0.08*t/{dur:.3f})/2)*2':h=-2:eval=frame[fg]"
        chain += (f"[{cur}]split[a][b];[a]scale={CW}:{CH}:force_original_aspect_ratio=increase,crop={CW}:{CH},"
                  f"gblur=sigma=30,eq=brightness=-0.15[bg];{fg};"
                  f"[bg][fg]overlay=x='{x}':y='(H-h)/2-{int(60 * K * S)}':eval=frame,scale={W}:{H}:flags=lanczos,setsar=1[out]")
        run(['ffmpeg', '-v', 'error', '-y', '-loop', '1', '-framerate', str(FPS), '-i', path(s['image']), '-frames:v', str(frames),
             '-filter_complex', chain, '-map', '[out]', *ENC, out])
    elif 'card' in s:  # a document/card image floating over a blurred photo, with shadow and slight tilt
        ang = s.get('angle', 4)
        cw = int(W * 0.83) // 2 * 2
        fc = (f"[1]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},gblur=sigma=14,eq=brightness=-0.18[bg];"
              f"[0]scale={cw}:-2:flags=lanczos,unsharp=5:5:0.9,format=rgba,pad=iw+{int(110 * K)}:ih+{int(110 * K)}:{int(55 * K)}:{int(55 * K)}:color=black@0,split[c1][c2];"
              f"[c2]lutrgb=r=0:g=0:b=0,colorchannelmixer=aa=0.55,boxblur={int(16 * K)}:2[sh];"
              f"[sh][c1]overlay=-{int(12 * K)}:-{int(20 * K)},rotate={ang}*PI/180:c=none:ow=rotw({ang}*PI/180):oh=roth({ang}*PI/180)[card];"
              f"[card]scale=w='trunc(iw*(0.96+0.08*t/{dur:.3f})/2)*2':h=-2:eval=frame[fg];"
              f"[bg][fg]overlay=x=(W-w)/2:y=(H-h)/2-{int(40 * K)}:format=auto,format=yuv420p,setsar=1")
        run(['ffmpeg', '-v', 'error', '-y', '-loop', '1', '-framerate', str(FPS), '-i', path(s['card']),
             '-loop', '1', '-framerate', str(FPS), '-i', path(s['bg']), '-frames:v', str(frames), '-filter_complex', fc, *ENC, out])
    else:
        raise SystemExit(f'unknown shot: {s}')


lst = []
for k, (s, a, b) in enumerate(parts):
    fa, fb = round(a * FPS), round(b * FPS)
    o = os.path.join(TMP, f'shot_{k:02d}.mp4')
    render_shot(s, (fb - fa) / FPS, o)
    lst.append(o)
    print(f'shot {k:2d} {a:6.2f}-{b:6.2f}  {s}', flush=True)
with open(os.path.join(TMP, 'list.txt'), 'w', encoding='utf-8') as f:
    f.writelines(f"file '{p.replace(os.sep, '/')}'\n" for p in lst)

# ---- subtitles / title (ASS). Colours are &HBBGGRR.
PRESETS = {
    # reference style A: red bold italic, white inner stroke, navy outer stroke, centre ~69% down, no title
    'red-italic': dict(fill='&H001A1AE6', inner='&H00FFFFFF', outer='&H00802010', size=64, y=0.69, italic=True, box=False),
    # same layout, yellow fill with deep-red stroke and white outer stroke
    'yellow-italic': dict(fill='&H0000E1FF', inner='&H002410B4', outer='&H00FFFFFF', size=64, y=0.69, italic=True, box=False),
    # reference style B: black text on a solid yellow box at ~71%, usually paired with a 3-line top title
    'yellow-box': dict(fill='&H00000000', inner='&H0000E6FF', outer=None, size=75, y=0.711, italic=False, box=True),
}
st = dict(PRESETS[P.get('subtitle', {}).get('preset', 'red-italic')])
st.update({k: v for k, v in P.get('subtitle', {}).items() if k != 'preset'})
font = st.get('font') or default_font()
FS = int(st['size'] * K)
maxc = st.get('max_chars', 10)


def t(x):
    return '%d:%02d:%05.2f' % (x // 3600, (x % 3600) // 60, x % 60)


ass = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {W}
PlayResY: {H}
WrapStyle: 2

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
"""
if st['box']:
    ass += f"Style: Sub,{font},{FS},{st['fill']},&H0,{st['inner']},{st['inner']},1,0,0,0,100,100,1,0,3,{11 * K:.1f},0,5,10,10,0,1\n"
else:
    ass += (f"Style: Outer,{font},{FS},{st['outer']},&H0,{st['outer']},&H64000000,1,0,0,0,100,100,1,0,1,{10 * K:.1f},{2 * K:.1f},5,10,10,0,1\n"
            f"Style: Inner,{font},{FS},{st['fill']},&H0,{st['inner']},&H0,1,0,0,0,100,100,1,0,1,{4.5 * K:.1f},0,5,10,10,0,1\n")
title = P.get('title')
if title:
    tf = title.get('font') or font
    ass += (f"Style: T1,{tf},{int(88 * K)},{title.get('color1', '&H0024A8FF')},&H0,&H00000000,&H80000000,1,0,0,0,100,100,2,0,1,{5.5 * K:.1f},{2 * K:.1f},8,10,10,0,1\n"
            f"Style: T2,{tf},{int(75 * K)},{title.get('color2', '&H00FFFFFF')},&H0,&H00000000,&H80000000,1,0,0,0,100,100,2,0,1,{4 * K:.1f},{2 * K:.1f},8,10,10,0,1\n")
ass += "\n[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"
if title:
    ys = title.get('y', [0.0625, 0.146, 0.214])
    for j, line in enumerate(title['lines']):
        ass += f"Dialogue: 2,{t(0)},{t(END)},{'T1' if j == 0 else 'T2'},,0,0,0,,{{\\pos({W // 2},{int(H * ys[j])})}}{line}\n"
for sg in segs:
    txt = sg['text']
    fs = '' if len(txt) <= maxc else f'\\fs{int(FS * (maxc + 0.3) / len(txt))}'
    fax = '\\fax-0.12' if st['italic'] else ''
    tag = '{\\pos(%d,%d)%s%s}' % (W // 2, int(H * st['y']), fax, fs)
    if st['box']:
        ass += f"Dialogue: 0,{t(sg['start'])},{t(sg['end'])},Sub,,0,0,0,,{tag}{txt}\n"
    else:
        ass += f"Dialogue: 0,{t(sg['start'])},{t(sg['end'])},Outer,,0,0,0,,{tag}{txt}\n"
        ass += f"Dialogue: 1,{t(sg['start'])},{t(sg['end'])},Inner,,0,0,0,,{tag}{txt}\n"
open(os.path.join(TMP, 'subs.ass'), 'w', encoding='utf-8').write(ass)

# ---- audio: voice (+ BGM) -> clean wav
voice = path(P['voice'])
lufs = P.get('loudness', -16)
bgm = P.get('bgm')
cmd = ['ffmpeg', '-v', 'error', '-y', '-i', voice]
if bgm:
    cmd += ['-ss', str(bgm.get('start', 0)), '-i', path(bgm['file'])]
    fc = (f"[0:a]loudnorm=I={lufs}:TP=-1.5:LRA=11,aresample=44100,apad=whole_dur={END:.3f}[v];"
          f"[1:a]aresample=44100,volume={bgm.get('gain_db', -17)}dB,afade=t=in:d=0.3,"
          f"afade=t=out:st={END - 0.8:.3f}:d=0.8,atrim=0:{END:.3f}[m];"
          f"[v][m]amix=inputs=2:duration=first:normalize=0,alimiter=limit=0.95")
else:
    fc = f"[0:a]loudnorm=I={lufs}:TP=-1.5:LRA=11,aresample=44100,apad=whole_dur={END:.3f}"
mix = os.path.join(TMP, 'mix.wav')
run(cmd + ['-filter_complex', fc, '-ac', '2', '-ar', '44100', '-t', f'{END:.3f}', mix])

# ---- final mux (run inside TMP so the ass filter gets a plain relative path)
out = path(P['output'])
os.makedirs(os.path.dirname(out) or '.', exist_ok=True)
fontsdir = P.get('fonts_dir')
sub = 'ass=subs.ass' + (f":fontsdir='{path(fontsdir).replace(os.sep, '/').replace(':', chr(92) + ':')}'" if fontsdir else '')
cwd = os.getcwd(); os.chdir(TMP)
run(['ffmpeg', '-v', 'error', '-y', '-f', 'concat', '-safe', '0', '-i', 'list.txt', '-i', 'mix.wav',
     '-filter_complex', f'[0:v]{sub},format=yuv420p[v]', '-map', '[v]', '-map', '1:a',
     '-c:v', 'libx264', '-preset', 'medium', '-crf', '17', '-r', str(FPS), '-c:a', 'aac', '-b:a', '192k', '-ar', '44100',
     '-movflags', '+faststart', '-t', f'{END:.3f}', out])
os.chdir(cwd)
print('done', out)
