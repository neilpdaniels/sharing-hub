"""Optional integration check: pip install playwright; playwright install chromium.
Run with FFMPEG_BINARY set if ffmpeg is not on PATH.
"""
import base64
from functools import partial
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from threading import Thread
import shutil
import os
from pathlib import Path
import re
import subprocess
from tempfile import TemporaryDirectory

from playwright.sync_api import sync_playwright

binary = os.environ.get('FFMPEG_BINARY', 'ffmpeg')
script = Path(__file__).resolve().parents[1] / 'transaction/static/transaction/video-upload.js'
with TemporaryDirectory() as directory, sync_playwright() as playwright:
    class QuietHandler(SimpleHTTPRequestHandler):
        def log_message(self, *args):
            pass
    for name in ('video-upload.js', 'video-worker.js'):
        shutil.copyfile(script.parent / name, Path(directory) / name)
    (Path(directory) / 'index.html').write_text('<form><input type="file" accept="video/*"><button>Upload</button></form><script src="video-upload.js" data-worker-url="video-worker.js"></script>')
    server = ThreadingHTTPServer(('127.0.0.1', 0), partial(QuietHandler, directory=directory))
    Thread(target=server.serve_forever, daemon=True).start()
    browser = playwright.chromium.launch()
    page = browser.new_page()
    page.on('console', lambda message: print('Browser:', [arg.json_value() for arg in message.args]))
    cases = [('1920x1080', '1920x1080', 'webm'), ('1080x1920', '1080x1920', 'webm'), ('1920x1080', '1920x1080', 'mp4')]
    for dimensions, expected, container in cases:
        original = Path(directory) / ('original.' + container)
        codecs = (['-c:v', 'libvpx-vp9', '-lossless', '1', '-deadline', 'realtime', '-cpu-used', '8', '-c:a', 'libopus']
                  if container == 'webm' else ['-c:v', 'libx264', '-preset', 'ultrafast', '-crf', '18', '-c:a', 'aac'])
        subprocess.run([binary, '-nostdin', '-y', '-f', 'lavfi', '-i', f'testsrc2=size={dimensions}:rate=30',
                        '-f', 'lavfi', '-i', 'sine=frequency=440:sample_rate=44100', '-t', '2',
                        *codecs, '-threads', '2',
                        str(original)], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        page.goto(f'http://127.0.0.1:{server.server_port}/')
        page.evaluate('''() => {
            window.uploaded = null;
            document.querySelector('form').addEventListener('submit', async event => {
                event.preventDefault();
                const file = document.querySelector('input').files[0];
                const bytes = new Uint8Array(await file.arrayBuffer());
                let value = '';
                for (let i = 0; i < bytes.length; i += 8192) value += String.fromCharCode(...bytes.subarray(i, i + 8192));
                window.uploaded = {type: file.type, data: btoa(value)};
            });
        }''')
        page.locator('input').set_input_files(str(original))
        page.locator('button').click()
        try:
            page.wait_for_function('window.uploaded !== null || document.querySelector(".alert-danger")', timeout=60000)
        except Exception:
            print(page.locator('body').inner_text())
            raise
        result = page.evaluate('window.uploaded')
        if result is None and container == 'mp4':
            assert 'cannot preserve' in page.locator('body').inner_text()
            print('MP4 codecs unsupported by this Chromium build: upload safely rejected')
            continue
        assert result, page.locator('body').inner_text()
        compressed = Path(directory) / ('compressed.mp4' if result['type'].startswith('video/mp4') else 'compressed.webm')
        compressed.write_bytes(base64.b64decode(result['data']))
        metadata = subprocess.run([binary, '-i', str(compressed), '-af', 'volumedetect', '-f', 'null', '-'],
                                  stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, check=True).stderr.decode()
        assert expected in metadata, metadata
        frames = re.findall(r'frame=\s*(\d+)', metadata)
        assert frames and int(frames[-1]) >= 55, metadata
        volume = re.search(r'mean_volume: ([\-\d.]+) dB', metadata)
        assert volume and float(volume.group(1)) > -50, metadata
        assert compressed.stat().st_size < original.stat().st_size
        print(f'{dimensions}: {original.stat().st_size} -> {compressed.stat().st_size} bytes; audio preserved')
        page.close()
        page = browser.new_page()
    browser.close()
    server.shutdown()
    server.server_close()
