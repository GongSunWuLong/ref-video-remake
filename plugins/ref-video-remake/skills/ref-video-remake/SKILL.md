---
name: ref-video-remake
description: >-
  Remake a short vertical voice-over video (Douyin/TikTok/Reels/Shorts style) from a reference video: match its
  aspect ratio, rhythm, subtitle look and shot style, using a new script/title, a TTS voice or the user's own
  recording, and footage from free stock sites (Pexels) or the user's local material folder. Use when the user
  says things like "参考这个视频做一条", "照着这个视频的节奏/字幕/比例做", "用我的文案/录音/素材库做短视频",
  "对标这条视频", "做口播短视频", or gives a reference .mp4 plus a script. Also use to re-run the pipeline for
  more videos in the same series, or to audition TTS voices for such a video.
---

# 对标参考视频做口播短视频 / Reference-matched short video

The pipeline turns **reference video + script (+ title) + voice + footage** into a finished MP4. The scripts are in
`scripts/`, run with `python scripts/<name>.py`. Everything is ffmpeg + numpy + edge-tts, and it runs on
Windows, macOS and Linux.

## 0. First contact: onboard the user (always do this first for a new video)

Run `python scripts/check_env.py`. If anything is missing, give the user the install command it prints and stop
until it passes.

Then collect the inputs. Ask only for what the user has not already given. Send it as one friendly message (or one
AskUserQuestion form):

> 我来帮你对标参考视频做一条新的口播短视频。请告诉我：
> 1. **参考视频**：直接上传，或者给出文件路径（例如 `D:\视频\参考.mp4`）。
> 2. **文案**：要配音的完整文字。**标题**是可选的；如果参考视频顶部有固定标题，你不给的话我会从文案里提炼一个。
> 3. **配音**：二选一。
>    - 用 AI 配音，我可以先生成几种音色给你试听；
>    - 用你自己的录音，给我音频文件的路径。
> 4. **素材**：三选一。
>    - 用无版权网站的素材（Pexels，可免费商用）；
>    - 用你的本地素材库，给我文件夹路径；
>    - 两者结合。
> 5. 可选：字幕颜色偏好、成片保存位置、结尾的引流话术（比如“想办理扣66”）。

Defaults when the user doesn't specify:
- Output goes next to the reference video, named `<标题或文案开头>_成片.mp4`.
- Subtitle colours copy the reference.
- Voice is `zh-CN-YunjianNeural` (male) or `zh-CN-XiaoxiaoNeural` (female), matched to the reference narrator's gender
  from `analyze_ref.py`, at `+30%` (or `+12%` for a calmer reference).

Check that `chars_per_sec` lands close to the reference's.

If the user asks for voice choices, run `tts.py --samples` and send the files. Let them pick by number.

## 1. Analyse the reference

`python scripts/analyze_ref.py REF.mp4 WORK/ref [--chars N]` → `ref.json`, `contact.png`, `frames/`.

Read `contact.png` and one or two full frames, and note:
- **Size / fps**. Render at the reference size. A 9:16 reference at 720×1280 stays 720×1280; low-res source
  footage looks worse when upscaled to 1080p.
- **Rhythm**. `avg_shot_sec` is usually 1–1.8 s. Plan roughly one shot per subtitle phrase; split a phrase longer
  than about 2.2 s into two shots.
- **Text layout**. Is there a fixed top title? Where does the subtitle sit (fraction of height)? What are the
  colours, strokes, box and italics? Pick the closest preset in `references/plan-format.md` and override
  colours/size/y if needed.
- **Audio**. `has_music_bed: true` means add quiet BGM under the voice. The voice-gender guess helps choose the TTS voice.

## 2. Voice + timings

- **TTS**: `python scripts/tts.py --text "<文案>" --voice <id> --rate +30% --out WORK` → `vo.mp3`, `words.json`.
- **User recording**: `python scripts/align_recording.py --audio REC.mp3 --text "<文案>" --out WORK`. It synthesises
  the same script with TTS and aligns it to the recording with DTW (no speech-recognition model needed). Confirm
  that the word times line up with the printed real pauses (within about 0.1 s).

Pass `--text` exactly as written. Digits stay digits (`10万`, `扣66`). Contact codes after 扣/私信/加 are read
digit by digit; other numbers are read as amounts.

If the TTS service fails to connect (`Cannot connect to host speech.platform.bing.com`), retry a little later. It
is a network problem, not a code problem.

## 3. Subtitle phrases

`python scripts/segment.py --text "<文案>" --words WORK/words.json --vo WORK/vo.mp3 --out WORK/segments.json [--snap]`

Use `--snap` for human recordings. **Read every printed line.** Each phrase should be a natural reading unit of at
most about 12 characters. Never end a line on 在/为/和/的. If a break is wrong, put `|` in the text where it should
break, or merge two parts by removing punctuation, then re-run.

## 4. Footage

Write down what each phrase needs to show (the literal subject, e.g. visa/green card, money, family at an airport,
kids at school, office, city skyline). Then pick shots:

- **Local library**: `python scripts/library_index.py LIB_DIR WORK/lib`. Look at `videos_*.png` / `images.png`.
  Every clip gets an id (V07, I03) that you can use directly in the plan. For each candidate, note what it shows
  and at what time. Clips with burned-in subtitles or captions are still usable: blur the text region (measure it on
  a full-size frame with a grid, e.g. `ffmpeg -ss T -i clip -frames:v 1 -vf drawgrid=w=64:h=64:t=1:c=yellow f.png`)
  or crop to the clean region. If the user says their library is pre-cleared, don't add warnings about locations
  or real people in it.
- **Free stock (Pexels)**: follow `references/pexels-search.md` to search in a browser and get file URLs. Then run
  `python scripts/pexels_download.py LIST.txt WORK/clips --seconds 5`. Prefer clips from 2021 or later, portrait,
  1080×1920 or larger, and real footage (skip AI-generated `aigc` results). Check the title/description:
  a search for "yuan" returned Philippine pesos, and one for "lottery" returned bowling balls.
- When nothing fits a phrase, use a scenery or city shot rather than forcing a weak match.
- Across a series of videos, don't reuse shots from the previous video. Keep overlap with earlier ones low.

Verify every chosen clip by looking at a frame from the exact segment you will use. If a clip shows something wrong
(off-topic, a foreign passport, a blurred face), replace it.

## 5. Plan + render

Write `WORK/plan.json` (format: `references/plan-format.md`) with one shot entry per subtitle segment, then run:
`python scripts/render.py WORK/plan.json`

Still images get a side-slide by default: they slide in from the right with an ease-out, then drift slowly. This is
drawn at 2× resolution so the motion is smooth. Videos are cover-cropped to the frame. 24/25 fps sources are
frame-blended to 30 fps.

## 6. Verify the finished file (mandatory)

`python scripts/verify.py OUT.mp4 --voice WORK/vo.mp3 --segments WORK/segments.json`

It decodes the whole file and checks:
- audio length = video length = frames/fps
- no timestamp gaps
- the voice in the video follows the voice file (not sped up or truncated)

**Never report a video as done from container metadata or a few sampled frames.** An early version once shipped
10 videos whose audio track was only about 4 s long, stretched over 15 s. Headers and sampled frames looked fine,
and playback was garbled. Look at the frame strip it writes, then send the user the file.

## 7. Report to the user

Give them:
- the output path, size/fps/duration and the verification numbers;
- a table of subtitle phrase → shot (and its source);
- any substitutions you made (e.g. no suitable stock footage, so a scenery shot was used) and anything you blurred or cropped.

Keep `WORK/` (`plan.json`, `segments.json`, `vo.mp3`) so later edits only need a re-render.

## Notes that save time
- `references/lessons.md`: pitfalls met while building this pipeline (network flakiness, corrupted parallel
  downloads, ffmpeg filter quirks).
- For several videos in one go, make one WORK dir per video, and pick all shots up front so none are reused.
