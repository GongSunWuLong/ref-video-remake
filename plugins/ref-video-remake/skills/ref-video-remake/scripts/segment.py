"""Split the script into on-screen subtitle phrases and time them from word timings.

    python segment.py --text "文案……" --words OUT/words.json --vo OUT/vo.mp3 --out OUT/segments.json
                      [--max-chars 12] [--snap]

Rules (matching typical Douyin voice-over shorts):
  * split at punctuation (and at '|' you put in the text to force a break); a phrase longer than --max-chars
    is broken at the word boundary where the voice pauses longest (both halves >= 3 characters)
  * a phrase shorter than 0.65 s is merged with the next one (joined with a space)
  * digits stay as digits on screen (10万, 扣66) while timing follows how they are spoken
  * --snap: move each phrase start onto the end of a real pause in the voice-over when one is within 0.3 s
    (use it for human recordings / aligned timings)
Prints one line per phrase so you can sanity-check, and writes [{text, start, end}, ...].
"""
import argparse
import json
import re

import os as _os, sys as _sys
_HERE = _os.path.dirname(_os.path.abspath(__file__)); _sys.path.insert(0, _HERE)
from common import media_info, silences, spoken, word_chars

ap = argparse.ArgumentParser()
ap.add_argument('--text', required=True); ap.add_argument('--words', required=True); ap.add_argument('--vo', required=True)
ap.add_argument('--out', required=True); ap.add_argument('--max-chars', type=int, default=12); ap.add_argument('--snap', action='store_true')
ap.add_argument('--tail', type=float, default=0.4, help='seconds kept after the last word')
a = ap.parse_args()

words = json.load(open(a.words, encoding='utf-8'))
cs = []  # (char, time, starts_a_word, pause before this word in seconds)
prev_end = 0.0
for s, e, w in words:
    w = word_chars(w)
    for k, ch in enumerate(w):
        cs.append((ch, s + (e - s) * k / max(len(w), 1), k == 0, max(0.0, s - prev_end) if k == 0 else 0.0))
    prev_end = e

phrases = [p.strip() for p in re.split(r'[，。？！：；、,.!?;:\n（）()|]+', a.text) if p.strip()]


DANGLING_END = set('在为和与跟对从向给把被让将的地得及或并而且')
DANGLING_START = set('的了着过们吗呢吧啊')


def split_long(disp, chunk):
    """Break an over-long phrase where the voice pauses longest between two words (prosodic boundary),
    keeping both halves at least 3 characters and the first half within the limit; recurse on the rest."""
    if len(disp) <= a.max_chars:
        return [[disp, chunk[0][1]]]
    cands = []
    for k in range(1, len(chunk)):
        if not chunk[k][2]:
            continue
        dk = next((d for d in range(1, len(disp)) if len(word_chars(spoken(disp[:d]))) == k), None)
        if dk and 3 <= dk <= a.max_chars and len(disp) - dk >= 3:
            # never leave a preposition/conjunction dangling at the end of a line or a particle at the start
            glue = disp[dk - 1] in DANGLING_END or disp[dk] in DANGLING_START
            cands.append((not glue, chunk[k][3], -abs(dk - len(disp) / 2), k, dk))
    if cands:
        k, dk = max(cands)[3:]
    else:  # no usable word boundary: hard split at the limit
        dk = a.max_chars
        k = len(word_chars(spoken(disp[:dk])))
    return [[disp[:dk], chunk[0][1]]] + split_long(disp[dk:], chunk[k:])


segs, pos = [], 0
for p in phrases:
    sp = word_chars(spoken(p))
    chunk = cs[pos:pos + len(sp)]
    got = ''.join(c[0] for c in chunk)
    if got != sp:
        raise SystemExit(f'timing text mismatch at "{p}": expected "{sp}", words give "{got}".\n'
                         f'Make sure --text is exactly the script that was spoken.')
    segs += split_long(re.sub(r'[「」“”"\'《》]', '', p), chunk)
    pos += len(sp)
if pos != len(cs):
    raise SystemExit(f'script covers {pos} of {len(cs)} spoken characters; --text does not match the voice-over')

vo_dur = media_info(a.vo)['duration']
end = min(words[-1][1] + a.tail, vo_dur + 0.2)
starts = [s for _, s in segs]
if a.snap:
    pauses = [e for s, e in silences(a.vo) if e]
    starts = [max([e for e in pauses if s - 0.3 <= e <= s + 0.08], default=s + 0.02) - 0.03 for s in starts]
else:
    starts = [s - 0.05 for s in starts]
starts[0] = 0.0
out = [{'text': t, 'start': round(max(0.0, s), 3)} for (t, _), s in zip(segs, starts)]
for i, o in enumerate(out):
    o['end'] = out[i + 1]['start'] if i + 1 < len(out) else round(end, 3)
# merge phrases that would flash by too quickly
merged = []
for o in out:
    if merged and merged[-1]['end'] - merged[-1]['start'] < 0.65 and len(merged[-1]['text']) + len(o['text']) <= a.max_chars + 2:
        merged[-1] = {'text': merged[-1]['text'] + ' ' + o['text'], 'start': merged[-1]['start'], 'end': o['end']}
    else:
        merged.append(o)
json.dump(merged, open(a.out, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
for i, o in enumerate(merged):
    print(f"{i:2d} {o['start']:6.2f}-{o['end']:6.2f} ({o['end'] - o['start']:.2f}s) {o['text']}")
print(f'total {merged[-1]["end"]:.2f}s, {len(merged)} phrases -> {a.out}')
