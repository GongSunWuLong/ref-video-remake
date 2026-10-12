# plan.json format (render.py input)

Relative paths resolve against the folder that holds plan.json.

```json
{
  "output": "成片/今早7点_成片.mp4",
  "size": [720, 1280],
  "fps": 30,
  "voice": "work/vo.mp3",
  "segments": "work/segments.json",
  "library": "work/lib/library.json",
  "subtitle": {"preset": "red-italic"},
  "title": {"lines": ["主标题", "副标题一", "副标题二"]},
  "bgm": {"file": "music/bgm.mp3", "start": 12, "gain_db": -17},
  "loudness": -16,
  "work_dir": "_render",
  "fonts_dir": "fonts",
  "shots": [ ...one entry per segment... ]
}
```

| key | meaning |
|---|---|
| `output` | final mp4 |
| `size`, `fps` | output frame. Use the reference's size (9:16 references are usually 720×1280 or 1080×1920) |
| `voice` | voice-over audio (TTS `vo.mp3` or the user's recording copied by `align_recording.py`) |
| `segments` | `segments.json` from `segment.py`, or an inline list of `{text, start, end}` |
| `library` | optional `library.json` from `library_index.py`, so shots can say `"V24"` / `"I03"` |
| `subtitle` | `preset` plus optional overrides: `fill`, `inner`, `outer` (ASS colours `&H00BBGGRR`), `size` (px at 720 wide), `y` (fraction of height for the centre), `italic`, `max_chars` (longer lines shrink to fit), `font` |
| `title` | optional fixed top title, 1–3 lines (line 1 orange, lines 2–3 white, black stroke). Optional `y` list (fractions), `color1`, `color2`, `font` |
| `bgm` | optional music bed: `start` offset into the track, `gain_db` relative level (−17 sits well under a −16 LUFS voice) |
| `loudness` | target LUFS for the voice (default −16) |
| `fonts_dir` | folder with extra font files for libass (e.g. a downloaded Source Han Serif Heavy) |

## Subtitle presets

| preset | look | from |
|---|---|---|
| `red-italic` | red bold italic, white inner stroke, navy outer stroke, centre at 69% height, no title | reference A |
| `yellow-italic` | same layout, yellow fill, deep-red stroke, white outer stroke | colour variant |
| `yellow-box` | black text on a solid yellow box at 71% height; pair with `title` for the 3-line top title | reference B |

Colours are ASS `&H00BBGGRR`. For example, pure red #E61A1A is `&H001A1AE6`.

## Shot entries

`shots[i]` belongs to `segments[i]`.

| entry | effect |
|---|---|
| `{"video": "V24", "start": 3.5}` | clip from 3.5 s, cover-cropped to the frame |
| `{"video": "...", "start": 2, "blur": [[x, y, w, h], ...]}` | blur boxes (source pixels) over burned-in captions or logos |
| `{"video": "...", "start": 18, "region": [x, y, w, h]}` | use only that part of the source (e.g. the picture inside a letterboxed news clip); the rest of the frame is filled with its blurred copy |
| `{"image": "I03"}` | still image, side-slide in from the right then slow drift (default `"motion": "slide"`; `"zoom"` = slow push-in). Optional `blur`, `width` (fraction of frame, default 0.92) |
| `{"card": "card.png", "bg": "photo.jpg", "angle": 5}` | a card/document image floating over a blurred photo with a shadow, a tilt and a slow push-in (good for ID cards or visas) |
| `[shotA, shotB]` | split the segment evenly between two shots (use for phrases longer than about 2.2 s) |
| `"prev"` / `"next"` | no new shot; extend the previous or next shot across this segment (for very short phrases) |

Pick `start` so the useful part of the clip falls inside the segment. The clip must be at least `start + segment
length` long. Pexels downloads are only as long as `--seconds`.
