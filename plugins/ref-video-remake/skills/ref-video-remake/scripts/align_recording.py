"""Get word timings for a voice-over the user recorded themselves (no speech-recognition model needed).

    python align_recording.py --audio RECORDING.mp3 --text "文案……" --out OUT_DIR
        -> OUT_DIR/vo.mp3 (copy of the recording) + OUT_DIR/words.json

How: synthesise the same script with a TTS voice (which gives exact word timings), then align the TTS audio
to the recording with dynamic time warping on MFCC features and map every word time across.
Check the result against the real pauses printed at the end; they should line up within ~0.1 s.
"""
import argparse
import asyncio
import json
import os
import shutil
import wave

import edge_tts
import numpy as np

import os as _os, sys as _sys
_HERE = _os.path.dirname(_os.path.abspath(__file__)); _sys.path.insert(0, _HERE)
from common import run, silences, spoken


async def tts(text, voice, rate, mp3, words):
    for i in range(6):
        try:
            c = edge_tts.Communicate(text, voice, rate=rate, boundary='WordBoundary')
            au, wb = b'', []
            async for ch in c.stream():
                if ch['type'] == 'audio':
                    au += ch['data']
                elif ch['type'] == 'WordBoundary':
                    wb.append([ch['offset'] / 1e7, (ch['offset'] + ch['duration']) / 1e7, ch['text']])
            open(mp3, 'wb').write(au); json.dump(wb, open(words, 'w', encoding='utf-8'), ensure_ascii=False)
            return
        except Exception as e:
            print('retry', e); await asyncio.sleep(4)
    raise SystemExit('TTS failed')


def load(p):
    w = wave.open(p)
    return np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(np.float32) / 32768, w.getframerate()


def mfcc(x, sr, hop=0.01, win=0.025, n_mels=40):
    h, n, n_fft = int(sr * hop), int(sr * win), 512
    fr = np.lib.stride_tricks.sliding_window_view(x, n)[::h] * np.hanning(n)
    spec = np.abs(np.fft.rfft(fr, n_fft)) ** 2
    hz2m = lambda f: 2595 * np.log10(1 + f / 700)
    m2hz = lambda m: 700 * (10 ** (m / 2595) - 1)
    bins = np.floor((n_fft + 1) * m2hz(np.linspace(hz2m(60), hz2m(7600), n_mels + 2)) / sr).astype(int)
    fb = np.zeros((n_mels, n_fft // 2 + 1))
    for i in range(n_mels):
        a, b, c = bins[i:i + 3]
        fb[i, a:b] = (np.arange(a, b) - a) / max(b - a, 1)
        fb[i, b:c] = (c - np.arange(b, c)) / max(c - b, 1)
    m = np.log(spec @ fb.T + 1e-8)
    k = np.arange(n_mels)
    dct = np.cos(np.pi / n_mels * (k + 0.5)[None, :] * np.arange(1, 14)[:, None])
    c = m @ dct.T
    c = (c - c.mean(0)) / (c.std(0) + 1e-6)
    e = m.mean(1, keepdims=True); e = (e - e.mean()) / (e.std() + 1e-6)
    return np.hstack([c, 1.5 * e])


def dtw_map(A, B):
    D = np.sqrt(((A[:, None, :] - B[None, :, :]) ** 2).sum(-1))
    n, m = D.shape
    C = np.full((n + 1, m + 1), np.inf); C[0, 0] = 0
    for i in range(1, n + 1):
        row = D[i - 1]; best = np.minimum(C[i - 1, :-1], C[i - 1, 1:]); acc = row + best
        cur = np.empty(m + 1); cur[0] = np.inf
        for j in range(1, m + 1):
            h = cur[j - 1] + row[j - 1]
            cur[j] = acc[j - 1] if acc[j - 1] < h else h
        C[i] = cur
    i, j = n, m; path = [(n - 1, m - 1)]
    while i > 1 or j > 1:
        _, i, j = min((C[i - 1, j - 1], i - 1, j - 1), (C[i - 1, j], i - 1, j), (C[i, j - 1], i, j - 1))
        path.append((max(i - 1, 0), max(j - 1, 0)))
    mp = {}
    for pi, pj in path:
        mp.setdefault(pi, []).append(pj)
    return mp, n


ap = argparse.ArgumentParser()
ap.add_argument('--audio', required=True); ap.add_argument('--text', required=True); ap.add_argument('--out', required=True)
ap.add_argument('--voice', default='zh-CN-YunjianNeural', help='TTS voice for the timing reference (any Chinese voice works)')
ap.add_argument('--ref-audio', help='reuse an existing TTS rendering of the same script (skips synthesis)')
ap.add_argument('--ref-words', help='word timings that belong to --ref-audio')
a = ap.parse_args()
os.makedirs(a.out, exist_ok=True)
ref_mp3, ref_words = os.path.join(a.out, '_tts_ref.mp3'), os.path.join(a.out, '_tts_ref_words.json')
ext = os.path.splitext(a.audio)[1] or '.mp3'
vo = os.path.join(a.out, 'vo' + ext)
shutil.copyfile(a.audio, vo)
if a.ref_audio and a.ref_words:
    ref_mp3, ref_words = a.ref_audio, a.ref_words
else:
    asyncio.run(tts(spoken(a.text), a.voice, '+30%', ref_mp3, ref_words))
wa, wb_ = os.path.join(a.out, '_ref.wav'), os.path.join(a.out, '_vo.wav')
run(['ffmpeg', '-v', 'error', '-y', '-i', ref_mp3, '-ac', '1', '-ar', '16000', wa])
run(['ffmpeg', '-v', 'error', '-y', '-i', vo, '-ac', '1', '-ar', '16000', wb_])
xa, sr = load(wa); xb, _ = load(wb_)
mp, n = dtw_map(mfcc(xa, sr), mfcc(xb, sr))


def conv(t):
    k = min(int(round(t / 0.01)), n - 1)
    while k not in mp and k > 0:
        k -= 1
    return float(np.median(mp[k]) * 0.01)


words = [[round(conv(s), 3), round(conv(e), 3), w] for s, e, w in json.load(open(ref_words, encoding='utf-8'))]
json.dump(words, open(os.path.join(a.out, 'words.json'), 'w', encoding='utf-8'), ensure_ascii=False)
print('words:', ' '.join(f'{w}@{s:.2f}' for s, e, w in words))
print('real pauses end at:', ' '.join(f'{e:.2f}' for s, e in silences(vo) if e))
print(f'-> {os.path.join(a.out, "words.json")}   voice file: {vo}')
