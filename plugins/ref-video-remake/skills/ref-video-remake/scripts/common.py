"""Shared helpers for the ref-video-remake scripts (ffmpeg wrappers, probing, Chinese number reading)."""
import json
import os
import re
import shutil
import subprocess
import sys

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')


def run(cmd, quiet=True):
    """Run a command; on failure print the command and the tail of stderr, then exit."""
    r = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='replace')
    if r.returncode:
        print(' '.join(map(str, cmd)))
        print(r.stderr[-3000:])
        raise SystemExit(1)
    return r


def ffprobe_json(path):
    r = run(['ffprobe', '-v', 'error', '-show_streams', '-show_format', '-of', 'json', path])
    return json.loads(r.stdout)


def media_info(path):
    """Width, height, fps, duration and audio presence of a media file."""
    j = ffprobe_json(path)
    v = next((s for s in j['streams'] if s['codec_type'] == 'video'), None)
    a = next((s for s in j['streams'] if s['codec_type'] == 'audio'), None)
    info = {'duration': float(j['format'].get('duration', 0) or 0), 'has_audio': a is not None}
    if v:
        n, d = (v.get('r_frame_rate', '0/1').split('/') + ['1'])[:2]
        info.update(width=int(v['width']), height=int(v['height']), fps=float(n) / float(d or 1))
    return info


def decoded_duration(path):
    """Duration measured by actually decoding the audio, not the container header."""
    r = subprocess.run(['ffmpeg', '-i', path, '-vn', '-f', 'null', '-'],
                       capture_output=True, text=True, encoding='utf-8', errors='replace')
    m = re.findall(r'time=(\d+):(\d+):([\d.]+)', r.stderr)
    if not m:
        return 0.0
    h, mi, s = m[-1]
    return int(h) * 3600 + int(mi) * 60 + float(s)


def silences(path, noise_db=-35, min_d=0.12):
    """List of (start, end) silent spans found by ffmpeg silencedetect."""
    r = subprocess.run(['ffmpeg', '-i', path, '-af', f'silencedetect=n={noise_db}dB:d={min_d}', '-f', 'null', '-'],
                       capture_output=True, text=True, encoding='utf-8', errors='replace').stderr
    st = [float(x) for x in re.findall(r'silence_start: ([\d.]+)', r)]
    en = [float(x) for x in re.findall(r'silence_end: ([\d.]+)', r)]
    return list(zip(st, en + [None] * (len(st) - len(en))))


# ---------------------------------------------------------------- Chinese number reading
DIG = '零一二三四五六七八九'


def _int_zh(n):
    if n == 0:
        return '零'
    units = [(100000000, '亿'), (10000, '万'), (1000, '千'), (100, '百'), (10, '十')]
    out = ''
    zero = False
    for val, name in units:
        q, n = divmod(n, val)
        if q:
            if zero and out:
                out += '零'
            out += (_int_zh(q) if val >= 10000 else DIG[q]) + name
            zero = False
        elif out:
            zero = True
    if n:
        if zero and out:
            out += '零'
        out += DIG[n]
    if out.startswith('一十'):
        out = out[1:]
    return out


def _num_zh(s):
    if '.' in s:
        a, b = s.split('.', 1)
        return _int_zh(int(a)) + '点' + ''.join(DIG[int(c)] for c in b)
    return _int_zh(int(s))


CODE_PREFIX = r'(扣|扣扣|私信|评论|加|回复|打|发)'


def spoken(text):
    """How a TTS engine will read `text`: digits become Chinese characters.
    Contact codes such as "扣66" are read digit by digit (六六); other numbers are read as amounts (十万, 七年)."""
    text = re.sub(r'[「」“”"\'《》]', '', text)
    text = re.sub(CODE_PREFIX + r'\s*(\d+)', lambda m: m.group(1) + ''.join(DIG[int(c)] for c in m.group(2)), text)
    text = re.sub(r'(?<!\d)(\d{4})(?=年)', lambda m: ''.join(DIG[int(c)] for c in m.group(1)), text)  # years: 二零二六年
    text = re.sub(r'\d+(?:\.\d+)?', lambda m: _num_zh(m.group(0)), text)
    return text


def word_chars(s):
    return re.sub(r'[^\w]', '', s)


# ---------------------------------------------------------------- fonts
FONT_CANDIDATES = [
    ('Microsoft YaHei', [r'C:\Windows\Fonts\msyhbd.ttc', r'C:\Windows\Fonts\msyh.ttc']),
    ('PingFang SC', ['/System/Library/Fonts/PingFang.ttc']),
    ('Noto Sans CJK SC', ['/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc', '/usr/share/fonts/noto-cjk/NotoSansCJK-Bold.ttc']),
    ('Source Han Sans SC', []),
    ('SimHei', [r'C:\Windows\Fonts\simhei.ttf']),
]


def default_font():
    for name, paths in FONT_CANDIDATES:
        if any(os.path.exists(p) for p in paths):
            return name
    return 'Microsoft YaHei'


def need(*tools):
    miss = [t for t in tools if not shutil.which(t)]
    if miss:
        raise SystemExit(f'missing tools: {miss}. Install ffmpeg (includes ffprobe) and make sure it is on PATH.')
