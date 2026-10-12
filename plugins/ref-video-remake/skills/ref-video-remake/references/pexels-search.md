# Finding free stock footage on Pexels

Pexels footage is free for commercial use under the Pexels License: no attribution needed, and it can be edited.
Do not resell clips unmodified, and do not imply that people shown endorse anything.

Pexels returns 403 to plain HTTP clients (curl/requests) for search pages, and its API needs a key. Search through a
real browser instead: the built-in browser pane, or Claude in Chrome. The video **files** on
`videos.pexels.com` download fine with ffmpeg.

## 1. Open any Pexels page in the browser

`https://www.pexels.com/search/videos/passport/`

## 2. Run this in the page (javascript tool) to search many queries at once

```js
window._px = {done: false, res: {}};
(async () => {
  const Q = {CITY: 'new york city', FLAG: 'american flag', MONEY: 'counting money', FAMILY: 'asian family airport',
             KIDS: 'children classroom', OFFICE: 'asian woman working laptop office', BOSS: 'asian businessman'};
  for (const [k, q] of Object.entries(Q)) {
    try {
      const h = await (await fetch('/search/videos/' + encodeURIComponent(q) + '/?orientation=portrait')).text();
      const d = JSON.parse(h.match(/<script id="__NEXT_DATA__"[^>]*>([\s\S]*?)<\/script>/)[1]);
      window._px.res[k] = (d.props.pageProps.initialData?.data || []).filter(x => x.type === 'video').map(x => {
        const a = x.attributes, fs = a.video?.video_files || [];
        const f = fs.find(v => v.width == 1080 && v.height == 1920) ||
                  fs.filter(v => Math.min(v.width, v.height) >= 1080).sort((p, q) => p.height - q.height)[0];
        return {id: a.id, year: (a.created_at || '').slice(0, 4), url: f?.link, title: a.title,
                desc: (a.description || '').slice(0, 80), thumb: a.video?.thumbnail?.small};
      }).filter(o => o.url && !/aigc/.test(o.url) && +o.year >= 2021).slice(0, 14);
    } catch (e) { window._px.res[k] = []; }
  }
  window._px.done = true;
})();
```

The javascript tool times out after about 45 s. Start the job without awaiting it, as above, then poll
`window._px.done`. Add `&page=2` for more results.

## 3. Look at the candidates

Read `title` and `desc` first. They catch wrong subjects (a "yuan" search returned Philippine pesos). Then view
thumbnails: replace the page body with a grid of `<img src=thumb>` labelled with ids and take a screenshot. You can
also grab one frame per clip with ffmpeg from the file URL, but that is slow for large files.

## 4. Download only what you use

Collect the chosen `url`s into a text file, one per line, and run:

```
python scripts/pexels_download.py chosen.txt WORK/clips --seconds 5 --jobs 4
```

Clips are saved as `WORK/clips/<id>.mp4` and fully decoded to make sure they are intact. Keep `--jobs` small on a
slow connection.

## Other sources

- **Wikimedia Commons** (`commons.wikimedia.org/w/api.php?action=query&list=search&srnamespace=6&srsearch=...`):
  public-domain government specimens, e.g. "2023 green card front.jpg" or "USA Visa specimen.jpg". Check the
  `LicenseShortName` in `prop=imageinfo&iiprop=url|extmetadata`.
- **Mixkit music** (`https://mixkit.co/free-stock-music/<tag>/`): free licence, no attribution. The track list is in
  the page's JSON-LD (`"url":"https://assets.mixkit.co/music/<n>/<n>.mp3"`). Mixkit videos only expose 720p
  landscape previews publicly, which is too soft for 9:16.
- Pixabay blocks automated access (403) and needs an API key.
- Do not use RMB banknote images in ads unless the user supplies them. China restricts the use of RMB designs.
