#!/usr/bin/env python3
"""Tiny OpenAI-like HTTP surface for ReVerfyx AI. Standard library only."""
import json
import os
import subprocess
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BIN = Path(os.getenv("REAI_BIN", ROOT / "build" / "reai"))
TEXT_MODEL = Path(os.getenv("REAI_TEXT_MODEL", ROOT / "models" / "text.bin"))
IMAGE_MODEL = Path(os.getenv("REAI_IMAGE_MODEL", ROOT / "models" / "image.bin"))
OUT_DIR = Path(os.getenv("REAI_OUTPUT_DIR", ROOT / "outputs"))
OUT_DIR.mkdir(parents=True, exist_ok=True)

def run(*args, timeout=300):
    p = subprocess.run([str(BIN), *map(str, args)], capture_output=True, text=True, timeout=timeout)
    if p.returncode:
        raise RuntimeError((p.stderr or p.stdout).strip())
    return p.stdout

class Handler(BaseHTTPRequestHandler):
    server_version = "ReAI/0.1"

    def send_json(self, code, obj):
        body = json.dumps(obj, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/health":
            return self.send_json(200, {"ok": True, "engine": "reai-from-scratch"})
        self.send_json(404, {"error": "not found"})

    def do_POST(self):
        try:
            n = int(self.headers.get("content-length", "0"))
            data = json.loads(self.rfile.read(n) or b"{}")
            if self.path == "/v1/chat/completions":
                messages = data.get("messages") or []
                prompt = "\n".join(f"{m.get('role','user')}: {m.get('content','')}" for m in messages)
                tokens = int(data.get("max_tokens", 256))
                text = run("text-generate", TEXT_MODEL, prompt, tokens, data.get("temperature", 0.9), data.get("top_k", 40))
                generated = text[len(prompt):] if text.startswith(prompt) else text
                return self.send_json(200, {"object":"chat.completion","choices":[{"index":0,"message":{"role":"assistant","content":generated.strip()}}]})
            if self.path == "/v1/images/generations":
                prompt = str(data.get("prompt", ""))
                name = f"img-{os.urandom(8).hex()}.ppm"
                path = OUT_DIR / name
                run("image-generate", IMAGE_MODEL, prompt, path, int(data.get("steps", 24)))
                return self.send_json(200, {"created": True, "data":[{"path": str(path), "format":"ppm"}]})
            self.send_json(404, {"error":"not found"})
        except Exception as e:
            self.send_json(500, {"error": str(e)})

    def log_message(self, fmt, *args):
        print("[api]", fmt % args)

if __name__ == "__main__":
    host = os.getenv("REAI_HOST", "127.0.0.1")
    port = int(os.getenv("REAI_PORT", "8080"))
    print(f"ReAI API http://{host}:{port}")
    ThreadingHTTPServer((host, port), Handler).serve_forever()
