#!/usr/bin/env python3
import base64
import hashlib
import json
import mimetypes
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HOST = "127.0.0.1"
PORT = 8765

BASE = Path.home() / ".i-am-everywhere"
INPUTS = BASE / "inputs"
RAW = BASE / "raw"
OUTPUTS = BASE / "outputs"
VIDEOS = BASE / "videos"
VIDEO_OUTPUTS = BASE / "video_outputs"
SOURCE = BASE / "source.jpg"

for p in (BASE, INPUTS, RAW, OUTPUTS, VIDEOS, VIDEO_OUTPUTS):
    p.mkdir(parents=True, exist_ok=True)

def find_facefusion():
    env_dir = os.environ.get("FACEFUSION_DIR")
    candidates = []
    if env_dir:
        candidates.append(Path(env_dir))
    candidates += [
        Path.home() / "pinokio/api/facefusion.git/app",
        Path.home() / "pinokio/api/facefusion/app",
        Path.home() / "pinokio/api/facefusion.git",
        Path.home() / "Pinokio/api/facefusion.git/app",
        Path.home() / "Pinokio/api/facefusion/app",
    ]
    pinokio_roots = [Path.home()/"pinokio/api", Path.home()/"Pinokio/api"]
    for r in pinokio_roots:
        if r.exists():
            try:
                for p in r.glob("*facefusion*"):
                    candidates += [p, p/"app"]
            except Exception:
                pass
    checked = []
    for d in candidates:
        checked.append(str(d))
        script = d / "facefusion.py"
        if script.exists():
            py_candidates = [
                d / ".env/bin/python", d / "venv/bin/python", d / "env/bin/python",
                d.parent / ".env/bin/python", d.parent / "venv/bin/python", d.parent / "env/bin/python",
            ]
            python_exe = next((p for p in py_candidates if p.exists()), Path(sys.executable))
            return d, script, python_exe, checked
    for root in pinokio_roots:
        if root.exists():
            try:
                for script in root.glob("**/facefusion.py"):
                    d = script.parent
                    py_candidates = [
                        d / ".env/bin/python", d / "venv/bin/python", d / "env/bin/python",
                        d.parent / ".env/bin/python", d.parent / "venv/bin/python", d.parent / "env/bin/python",
                    ]
                    python_exe = next((p for p in py_candidates if p.exists()), Path(sys.executable))
                    return d, script, python_exe, checked
            except Exception:
                pass
    return None, None, None, checked

FF_DIR, FF_SCRIPT, FF_PYTHON, CHECKED = find_facefusion()

def cors(handler):
    handler.send_header("Access-Control-Allow-Origin", "*")
    handler.send_header("Access-Control-Allow-Methods", "GET,POST,OPTIONS")
    handler.send_header("Access-Control-Allow-Headers", "Content-Type")

def json_response(handler, status, obj):
    payload = json.dumps(obj).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json")
    handler.send_header("Content-Length", str(len(payload)))
    cors(handler)
    handler.end_headers()
    handler.wfile.write(payload)

def decode_data_url(data_url):
    head, b64 = data_url.split(",", 1)
    mime = head.split(";")[0].replace("data:", "") or "image/jpeg"
    return base64.b64decode(b64), mime

def normalize_image_bytes(data, digest):
    raw_path = RAW / f"{digest}.source"
    jpg_path = INPUTS / f"{digest}.jpg"
    if jpg_path.exists() and jpg_path.stat().st_size > 0:
        return jpg_path
    raw_path.write_bytes(data)
    commands_to_try = [
        ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", str(raw_path), "-frames:v", "1", "-vf", "format=rgb24", "-q:v", "2", str(jpg_path)],
        ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", str(raw_path), "-frames:v", "1", "-pix_fmt", "yuvj420p", "-q:v", "2", str(jpg_path)]
    ]
    last_output = ""
    for cmd in commands_to_try:
        try:
            p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, timeout=60)
            last_output = p.stdout or ""
            if p.returncode == 0 and jpg_path.exists() and jpg_path.stat().st_size > 0:
                return jpg_path
        except Exception as e:
            last_output = repr(e)
    raise RuntimeError("Could not normalize webpage image to JPEG before FaceFusion.\n" + last_output[-3000:])

def normalize_source_bytes(data):
    digest = hashlib.sha1(data).hexdigest()
    normalized = normalize_image_bytes(data, "source-" + digest)
    shutil.copyfile(normalized, SOURCE)
    return SOURCE

def run_facefusion(target_path, output_path):
    global FF_DIR, FF_SCRIPT, FF_PYTHON
    if not FF_SCRIPT or not FF_SCRIPT.exists():
        FF_DIR, FF_SCRIPT, FF_PYTHON, _ = find_facefusion()
    if not FF_SCRIPT:
        raise RuntimeError("FaceFusion not found. Set FACEFUSION_DIR to the folder containing facefusion.py.")
    if not SOURCE.exists():
        raise RuntimeError("No source face loaded.")
    cmd = [str(FF_PYTHON), str(FF_SCRIPT), "headless-run", "--processors", "face_swapper", "--face-selector-mode", "many", "-s", str(SOURCE), "-t", str(target_path), "-o", str(output_path)]
    print("\n[I AM EVERYWHERE] FaceFusion command:")
    print(" ".join(cmd), flush=True)
    proc = subprocess.run(cmd, cwd=str(FF_DIR), stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, timeout=300)
    print(proc.stdout, flush=True)
    if proc.returncode != 0:
        raise RuntimeError("FaceFusion failed:\n" + proc.stdout[-4000:])
    if not output_path.exists():
        raise RuntimeError("FaceFusion finished but output file was not created.")

def ext_for_video_mime(mime):
    mime = (mime or "").lower()
    if "webm" in mime: return ".webm"
    if "quicktime" in mime or "mov" in mime: return ".mov"
    return ".mp4"

def run_facefusion_video(target_path, output_path):
    global FF_DIR, FF_SCRIPT, FF_PYTHON
    if not FF_SCRIPT or not FF_SCRIPT.exists():
        FF_DIR, FF_SCRIPT, FF_PYTHON, _ = find_facefusion()
    if not FF_SCRIPT:
        raise RuntimeError("FaceFusion not found.")
    if not SOURCE.exists():
        raise RuntimeError("No source face loaded.")
    cmd = [str(FF_PYTHON), str(FF_SCRIPT), "headless-run", "--processors", "face_swapper", "--face-selector-mode", "many", "-s", str(SOURCE), "-t", str(target_path), "-o", str(output_path)]
    print("\n[I AM EVERYWHERE] VIDEO FaceFusion command:")
    print(" ".join(cmd), flush=True)
    proc = subprocess.run(cmd, cwd=str(FF_DIR), stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, timeout=3600)
    print(proc.stdout, flush=True)
    if proc.returncode != 0:
        raise RuntimeError("FaceFusion video failed (exit code %s)\n\n%s" % (proc.returncode, proc.stdout[-8000:]))
    if not output_path.exists():
        raise RuntimeError("FaceFusion finished but video output was not created.")

class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        print("[bridge]", fmt % args)
    def do_OPTIONS(self):
        self.send_response(204); cors(self); self.end_headers()
    def do_GET(self):
        if self.path.startswith("/media/"):
            name = self.path.split("/media/", 1)[1]
            safe = Path(name).name
            path = VIDEO_OUTPUTS / safe
            if not path.exists():
                self.send_response(404); cors(self); self.end_headers(); return
            data = path.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "video/mp4")
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Accept-Ranges", "bytes")
            self.send_header("Cache-Control", "no-store")
            cors(self); self.end_headers(); self.wfile.write(data); return
        if self.path == "/health":
            json_response(self, 200, {"ok": True, "facefusion_found": bool(FF_SCRIPT and FF_SCRIPT.exists()), "facefusion_path": str(FF_SCRIPT) if FF_SCRIPT else None, "facefusion_python": str(FF_PYTHON) if FF_PYTHON else None, "source_loaded": SOURCE.exists(), "python_exists": bool(FF_PYTHON and Path(FF_PYTHON).exists()), "bridge_version": "4.1"})
            return
        json_response(self, 404, {"ok":False})
    def do_POST(self):
        try:
            length = int(self.headers.get("Content-Length", "0"))
            raw = self.rfile.read(length)
            body = json.loads(raw.decode("utf-8"))
            if self.path == "/source":
                data, mime = decode_data_url(body["data_url"])
                normalize_source_bytes(data)
                json_response(self, 200, {"ok":True, "message":"Source face normalized to JPEG and loaded."}); return
            if self.path == "/swap":
                data = base64.b64decode(body["image_b64"])
                digest = hashlib.sha1(data).hexdigest()
                target = normalize_image_bytes(data, digest)
                output = OUTPUTS / f"{digest}.jpg"
                if output.exists() and output.stat().st_size == 0: output.unlink()
                if not output.exists(): run_facefusion(target, output)
                out_b64 = base64.b64encode(output.read_bytes()).decode("ascii")
                json_response(self, 200, {"ok":True, "data_url":f"data:image/jpeg;base64,{out_b64}"}); return
            if self.path == "/swap-video":
                mime = body.get("mime", "video/mp4").split(";")[0]
                data = base64.b64decode(body["video_b64"])
                digest = hashlib.sha1(data).hexdigest()
                ext = ext_for_video_mime(mime)
                target = VIDEOS / f"{digest}{ext}"
                output = VIDEO_OUTPUTS / f"{digest}.mp4"
                if not target.exists(): target.write_bytes(data)
                if output.exists() and output.stat().st_size == 0: output.unlink()
                if not output.exists(): run_facefusion_video(target, output)
                json_response(self, 200, {"ok": True, "media_url": f"http://127.0.0.1:{PORT}/media/{output.name}"}); return
            json_response(self, 404, {"ok":False})
        except subprocess.TimeoutExpired:
            json_response(self, 500, {"ok":False,"error":"FaceFusion timed out."})
        except Exception as e:
            print("[ERROR]", repr(e), flush=True)
            json_response(self, 500, {"ok":False,"error":str(e)})

def main():
    print("\n==============================================")
    print(" I AM EVERYWHERE — FACEFUSION LOCAL BRIDGE")
    print("==============================================")
    print(f" Bridge: http://{HOST}:{PORT}")
    if FF_SCRIPT:
        print(f" FaceFusion: {FF_SCRIPT}\n Python:     {FF_PYTHON}")
    else:
        print(" FaceFusion: NOT FOUND\n")
        print(' FACEFUSION_DIR="/path/to/facefusion" python3 bridge.py')
    print("\nKeep this window open while using the extension.\n")
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    try: server.serve_forever()
    except KeyboardInterrupt: pass

if __name__ == "__main__":
    main()
