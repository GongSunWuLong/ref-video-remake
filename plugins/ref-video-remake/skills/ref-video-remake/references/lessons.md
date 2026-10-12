# Lessons learned (read when something looks off)

## Output correctness
- **Audio built in the final mux can silently break.** A chain like `[1:a]aresample,loudnorm,apad,atrim` inside the
  last ffmpeg call produced files whose audio decoded to about 4 s while the header said 15 s. Players raced
  through it, so the user heard sped-up, jumpy audio and video. `render.py` therefore renders the mixed audio to a
  WAV first and muxes it without filters.
- **Verify by decoding**, never by `ffprobe` duration or a handful of extracted frames. `verify.py` does this.
- **Parallel downloads into the same filename corrupt files** ("Invalid NAL unit size"). Use one process per file
  plus a full decode check; `pexels_download.py` does both. Kill stray ffmpeg processes after aborting a batch job,
  because orphaned xargs workers kept downloading and hogged bandwidth.

## Timing / subtitles
- edge-tts `boundary='WordBoundary'` gives word timings. Older defaults only give sentence boundaries.
- Convert digits before TTS and use the same conversion when matching timings (`common.spoken`): `10万`→十万,
  `7年`→七年, contact codes `扣66`→扣六六 (digit by digit), and `1.5万`→一点五万.
- To time a human recording, DTW against a TTS rendering of the same script. MFCC + energy features at 10 ms hops
  aligned within about 0.1 s of the real pauses. No ASR model is needed.
- Cut each shot about 50 ms before its first word, or snap to the end of the real pause, so the picture leads the voice.
- ASS/libass: `\fax-0.12` gives an italic slant to any font; two layered dialogue lines (thick outer stroke under a
  thin inner stroke) make the double-outline Douyin look; `BorderStyle=3` makes a solid box.

## Picture
- Scaling a still image with `eval=frame` and `unsharp` after it crashed ffmpeg (exit 127). Sharpen before the
  per-frame scale, and keep widths even (`trunc(x/2)*2`).
- Smooth slow pans need sub-pixel precision. Draw at 2× and downscale.
- `fps=30` on 25 fps sources duplicates 5 frames a second (visible judder). `framerate=fps=30` blends them instead.
- A Windows drive colon in filter arguments (e.g. `fontfile=C:/...`) breaks filter parsing. Run ffmpeg from the
  work dir with relative paths.
- Cover-cropping 4:3 or 16:9 clips to 9:16 loses a lot of the picture. For letterboxed clips (e.g. news), use
  `region` and fill the frame with a blurred copy.

## Footage choice
- Stock search results are often wrong for the literal subject. Check titles/descriptions and look at frames
  (searches for "lottery" returned bowling balls, a euro note and a neon sign).
- Low-res source clips (576×1024) look soft at 1080×1920. Match the reference resolution instead.
- When the user says their library is pre-cleared, use it freely: blur captions and don't add warnings about real
  people or filming locations.

## Network
- edge-tts, Pexels and Mixkit connections fail intermittently on some networks. Every network step in the scripts
  retries. If everything fails at once, wait and retry rather than changing code.
