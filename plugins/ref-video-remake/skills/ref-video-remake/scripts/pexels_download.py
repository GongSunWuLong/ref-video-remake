"""Download the first seconds of Pexels clips (free licence) without fetching whole 4K files.

    python pexels_download.py LIST.txt OUT_DIR [--seconds 5] [--jobs 4]

LIST.txt: one clip per line, either a direct file URL
    https://videos.pexels.com/video-files/39593842/16877196_1080_1920_60fps.mp4
or "ID FILENAME" (FILENAME as in that URL). Lines starting with # are ignored.
Files are saved as OUT_DIR/<ID>.mp4, re-tried on network errors, and fully decoded afterwards so a truncated
or corrupt download is caught (and deleted) instead of turning up as glitches in the final video.
Find IDs/URLs with references/pexels-search.md (Pexels blocks plain HTTP clients; search through a browser).
"""
import argparse
import os
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor

ap = argparse.ArgumentParser()
ap.add_argument('list'); ap.add_argument('out'); ap.add_argument('--seconds', type=float, default=5); ap.add_argument('--jobs', type=int, default=4)
a = ap.parse_args()
os.makedirs(a.out, exist_ok=True)
jobs = []
for line in open(a.list, encoding='utf-8'):
    line = line.strip()
    if not line or line.startswith('#'):
        continue
    if line.startswith('http'):
        vid = line.split('/video-files/')[1].split('/')[0]
        jobs.append((vid, line))
    else:
        vid, name = line.split()[:2]
        name = name if name.endswith('.mp4') else name + '.mp4'
        jobs.append((vid, f'https://videos.pexels.com/video-files/{vid}/{name}'))


def ok(p):
    if not os.path.exists(p) or os.path.getsize(p) < 10000:
        return False
    r = subprocess.run(['ffmpeg', '-v', 'error', '-i', p, '-f', 'null', '-'], capture_output=True, text=True, errors='replace')
    return r.returncode == 0 and not r.stderr.strip()


def fetch(job):
    vid, url = job
    out = os.path.join(a.out, f'{vid}.mp4')
    if ok(out):
        return f'skip {vid}'
    tmp = out + '.part.mp4'
    for i in range(5):
        subprocess.run(['ffmpeg', '-v', 'error', '-y', '-rw_timeout', '30000000', '-t', str(a.seconds), '-i', url,
                        '-an', '-c:v', 'copy', '-movflags', '+faststart', tmp], capture_output=True)
        if ok(tmp):
            os.replace(tmp, out)
            return f'ok   {vid}'
        time.sleep(3 * (i + 1))
    if os.path.exists(tmp):
        os.remove(tmp)
    return f'FAIL {vid} {url}'


with ThreadPoolExecutor(a.jobs) as ex:
    for r in ex.map(fetch, jobs):
        print(r, flush=True)
