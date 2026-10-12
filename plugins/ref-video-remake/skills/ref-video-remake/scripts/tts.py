"""Text-to-speech with word timings (Microsoft Edge neural voices via edge-tts; free, needs internet).

    python tts.py --text "文案……" --voice zh-CN-YunjianNeural --rate +30% --out OUT_DIR
        -> OUT_DIR/vo.mp3 + OUT_DIR/words.json  ([start, end, word] in seconds)
    python tts.py --samples --text "试听文案" --out OUT_DIR [--rate +12%]
        -> one audition mp3 per voice in VOICES, so the user can pick by ear

Digits are converted to how they should be read (10万 -> 十万, 扣66 -> 扣六六) before synthesis.
"""
import argparse
import asyncio
import json
import os
import subprocess

import edge_tts

import os as _os, sys as _sys
_HERE = _os.path.dirname(_os.path.abspath(__file__)); _sys.path.insert(0, _HERE)
from common import spoken

VOICES = [  # (voice id, label shown to the user)
    ('zh-CN-XiaoxiaoNeural', '女_晓晓_温和播音'),
    ('zh-CN-XiaoyiNeural', '女_晓伊_活泼'),
    ('zh-TW-HsiaoChenNeural', '女_晓臻_台湾腔'),
    ('en-US-AvaMultilingualNeural', '女_Ava_多语种'),
    ('zh-CN-YunyangNeural', '男_云扬_新闻播报'),
    ('zh-CN-YunxiNeural', '男_云希_阳光'),
    ('zh-CN-YunjianNeural', '男_云健_激情口播'),
    ('en-US-AndrewMultilingualNeural', '男_Andrew_多语种'),
]


async def synth(text, voice, rate, mp3, words_json=None, tries=6):
    for i in range(tries):
        try:
            c = edge_tts.Communicate(text, voice, rate=rate, boundary='WordBoundary')
            audio, wb = b'', []
            async for ch in c.stream():
                if ch['type'] == 'audio':
                    audio += ch['data']
                elif ch['type'] == 'WordBoundary':
                    wb.append([ch['offset'] / 1e7, (ch['offset'] + ch['duration']) / 1e7, ch['text']])
            if not audio:
                raise RuntimeError('empty audio')
            open(mp3, 'wb').write(audio)
            if words_json:
                json.dump(wb, open(words_json, 'w', encoding='utf-8'), ensure_ascii=False)
            return
        except Exception as e:  # the service drops connections now and then; retry
            print('retry', i + 1, e)
            await asyncio.sleep(4)
    raise SystemExit(f'TTS failed for {voice}')


def dur(p):
    return float(subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', p],
                                capture_output=True, text=True).stdout or 0)


ap = argparse.ArgumentParser()
ap.add_argument('--text', required=True)
ap.add_argument('--voice', default='zh-CN-YunjianNeural')
ap.add_argument('--rate', default='+30%')
ap.add_argument('--out', required=True)
ap.add_argument('--samples', action='store_true')
a = ap.parse_args()
os.makedirs(a.out, exist_ok=True)
text = spoken(a.text)
if a.samples:
    for i, (v, label) in enumerate(VOICES, 1):
        p = os.path.join(a.out, f'{i:02d}_{label}.mp3')
        asyncio.run(synth(text, v, a.rate, p))
        print(f'{i:02d} {label:<18} {v:<32} {dur(p):5.1f}s')
else:
    mp3 = os.path.join(a.out, 'vo.mp3')
    asyncio.run(synth(text, a.voice, a.rate, mp3, os.path.join(a.out, 'words.json')))
    print(f'{mp3}  {dur(mp3):.2f}s  ({len(text)} chars spoken)')
