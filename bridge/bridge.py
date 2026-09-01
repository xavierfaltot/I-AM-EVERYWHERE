#!/usr/bin/env python3
import base64
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HOST = "127.0.0.1"
PORT = 8765
BASE = Path.home() / ".i-am-everywhere"
INPUTS = BASE / "inputs"
RAW = BASE / "raw"
OUTPUTS = BASE / "outputs"
SOURCE = BASE / "source.jpg"
for p in (BASE, INPUTS, RAW, OUTPUTS): p.mkdir(parents=True, exist_ok=True)

def find_facefusion():
    env_dir = os.environ.get("FACEFUSION_DIR")
    candidates = []
    if env_dir: candidates.append(Path(env_dir))
    candidates += [Path.home()/"pinokio/api/facefusion.git/app", Path.home()/"pinokio/api/facefusion/app", Path.home()/"pinokio/api/facefusion.git", Path.home()/"Pinokio/api/facefusion.git/app", Path.home()/"Pinokio/api/facefusion/app"]
    roots = [Path.home()/"pinokio/api", Path.home()/"Pinokio/api"]
    for r in roots:
        if r.exists():
            for p in r.glob("*facefusion*"): candidates += [p, p/"app"]
    checked=[]
    for d in candidates:
        checked.append(str(d)); script=d/"facefusion.py"
        if script.exists():
            pcs=[d/".env/bin/python",d/"venv/bin/python",d/"env/bin/python",d.parent/".env/bin/python",d.parent/"venv/bin/python",d.parent/"env/bin/python"]
            return d,script,next((p for p in pcs if p.exists()),Path(sys.executable)),checked
    for root in roots:
        if root.exists():
            for script in root.glob("**/facefusion.py"):
                d=script.parent
                pcs=[d/".env/bin/python",d/"venv/bin/python",d/"env/bin/python",d.parent/".env/bin/python",d.parent/"venv/bin/python",d.parent/"env/bin/python"]
                return d,script,next((p for p in pcs if p.exists()),Path(sys.executable)),checked
    return None,None,None,checked

FF_DIR,FF_SCRIPT,FF_PYTHON,CHECKED=find_facefusion()

def cors(h):
    h.send_header("Access-Control-Allow-Origin","*"); h.send_header("Access-Control-Allow-Methods","GET,POST,OPTIONS"); h.send_header("Access-Control-Allow-Headers","Content-Type")
def json_response(h,status,obj):
    payload=json.dumps(obj).encode(); h.send_response(status); h.send_header("Content-Type","application/json"); h.send_header("Content-Length",str(len(payload))); cors(h); h.end_headers(); h.wfile.write(payload)
def decode_data_url(u):
    head,b64=u.split(",",1); return base64.b64decode(b64),head.split(";")[0].replace("data:","") or "image/jpeg"
def normalize_image_bytes(data,digest):
    raw=RAW/f"{digest}.source"; jpg=INPUTS/f"{digest}.jpg"
    if jpg.exists() and jpg.stat().st_size>0: return jpg
    raw.write_bytes(data); last=""
    for cmd in [["ffmpeg","-hide_banner","-loglevel","error","-y","-i",str(raw),"-frames:v","1","-vf","format=rgb24","-q:v","2",str(jpg)],["ffmpeg","-hide_banner","-loglevel","error","-y","-i",str(raw),"-frames:v","1","-pix_fmt","yuvj420p","-q:v","2",str(jpg)]]:
        try:
            p=subprocess.run(cmd,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,timeout=60); last=p.stdout or ""
            if p.returncode==0 and jpg.exists() and jpg.stat().st_size>0:return jpg
        except Exception as e:last=repr(e)
    raise RuntimeError("Could not normalize image to JPEG.\n"+last[-3000:])
def normalize_source_bytes(data):
    normalized=normalize_image_bytes(data,"source-"+hashlib.sha1(data).hexdigest()); shutil.copyfile(normalized,SOURCE); return SOURCE

def run_facefusion(target,output):
    global FF_DIR,FF_SCRIPT,FF_PYTHON
    if not FF_SCRIPT or not FF_SCRIPT.exists(): FF_DIR,FF_SCRIPT,FF_PYTHON,_=find_facefusion()
    if not FF_SCRIPT: raise RuntimeError("FaceFusion not found.")
    if not SOURCE.exists(): raise RuntimeError("No source face loaded.")
    cmd=[str(FF_PYTHON),str(FF_SCRIPT),"headless-run","--processors","face_swapper","--face-selector-mode","many","-s",str(SOURCE),"-t",str(target),"-o",str(output)]
    print("\n[I AM EVERYWHERE] FaceFusion command:\n"+" ".join(cmd),flush=True)
    p=subprocess.run(cmd,cwd=str(FF_DIR),stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,timeout=300); print(p.stdout,flush=True)
    if p.returncode!=0: raise RuntimeError("FaceFusion failed:\n"+p.stdout[-4000:])
    if not output.exists(): raise RuntimeError("FaceFusion finished but output file was not created.")

class Handler(BaseHTTPRequestHandler):
    def log_message(self,fmt,*args): print("[bridge]",fmt%args)
    def do_OPTIONS(self): self.send_response(204); cors(self); self.end_headers()
    def do_GET(self):
        if self.path=="/health":
            json_response(self,200,{"ok":True,"facefusion_found":bool(FF_SCRIPT and FF_SCRIPT.exists()),"facefusion_path":str(FF_SCRIPT) if FF_SCRIPT else None,"facefusion_python":str(FF_PYTHON) if FF_PYTHON else None,"source_loaded":SOURCE.exists(),"python_exists":bool(FF_PYTHON and Path(FF_PYTHON).exists()),"bridge_version":"5.1"}); return
        json_response(self,404,{"ok":False})
    def do_POST(self):
        try:
            raw=self.rfile.read(int(self.headers.get("Content-Length","0"))); body=json.loads(raw.decode())
            if self.path=="/source":
                data,_=decode_data_url(body["data_url"]); normalize_source_bytes(data)
                for cached in OUTPUTS.glob("*.jpg"):
                    try: cached.unlink()
                    except OSError: pass
                json_response(self,200,{"ok":True,"message":"New active face loaded. Render cache reset."}); return
            if self.path=="/swap":
                data=base64.b64decode(body["image_b64"]); digest=hashlib.sha1(data).hexdigest(); target=normalize_image_bytes(data,digest)
                source_digest=hashlib.sha1(SOURCE.read_bytes()).hexdigest()[:16]
                output=OUTPUTS/f"{digest}-{source_digest}.jpg"
                if output.exists() and output.stat().st_size==0: output.unlink()
                if not output.exists(): run_facefusion(target,output)
                out=base64.b64encode(output.read_bytes()).decode("ascii"); json_response(self,200,{"ok":True,"data_url":f"data:image/jpeg;base64,{out}"}); return
            json_response(self,404,{"ok":False})
        except subprocess.TimeoutExpired: json_response(self,500,{"ok":False,"error":"FaceFusion timed out."})
        except Exception as e: print("[ERROR]",repr(e),flush=True); json_response(self,500,{"ok":False,"error":str(e)})

def main():
    print("\n==============================================\n I AM EVERYWHERE — FACEFUSION LOCAL BRIDGE\n==============================================")
    print(f" Bridge: http://{HOST}:{PORT}")
    print(f" FaceFusion: {FF_SCRIPT}\n Python:     {FF_PYTHON}" if FF_SCRIPT else " FaceFusion: NOT FOUND")
    print("\nKeep this window open while using the extension.\n")
    server=ThreadingHTTPServer((HOST,PORT),Handler)
    try: server.serve_forever()
    except KeyboardInterrupt: pass
if __name__=="__main__": main()
