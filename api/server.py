#!/usr/bin/env python3
"""ReVerfyx AI v0.0.2 HTTP API. Python standard library only."""
import json
import os
import struct
import subprocess
import sys
import zlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote

VERSION = "0.0.2"
ROOT = Path(__file__).resolve().parents[1]
BIN = Path(os.getenv("REAI_BIN", ROOT / "build" / "reai"))
TEXT_MODEL = Path(os.getenv("REAI_TEXT_MODEL", ROOT / "models" / "text.bin"))
IMAGE_MODEL = Path(os.getenv("REAI_IMAGE_MODEL", ROOT / "models" / "image.bin"))
OUT_DIR = Path(os.getenv("REAI_OUTPUT_DIR", ROOT / "outputs")).resolve()
API_KEY = os.getenv("REAI_API_KEY", "")
OUT_DIR.mkdir(parents=True, exist_ok=True)
sys.path.insert(0, str(ROOT))
from policy.runtime import check_text, check_generated_text, public_error, control_prefix

def run(*args, timeout=600):
    p = subprocess.run([str(BIN), *map(str, args)], capture_output=True, text=True, timeout=timeout)
    if p.returncode:
        raise RuntimeError((p.stderr or p.stdout).strip())
    return p.stdout

def _ppm_tokens(raw):
    i = 0
    tokens = []
    while len(tokens) < 4:
        while i < len(raw) and raw[i] in b" \t\r\n":
            i += 1
        if i < len(raw) and raw[i] == ord("#"):
            while i < len(raw) and raw[i] != ord("\n"):
                i += 1
            continue
        start = i
        while i < len(raw) and raw[i] not in b" \t\r\n":
            i += 1
        tokens.append(raw[start:i].decode("ascii"))
    while i < len(raw) and raw[i] in b" \t\r\n":
        i += 1
    return tokens, i

def ppm_to_png(ppm_path: Path, png_path: Path):
    raw = ppm_path.read_bytes()
    tokens, offset = _ppm_tokens(raw)
    magic, ws, hs, maxs = tokens
    if magic != "P6":
        raise RuntimeError("API PNG converter expects P6 PPM")
    w, h, maxv = int(ws), int(hs), int(maxs)
    if maxv != 255:
        raise RuntimeError("unsupported PPM range")
    pixels = raw[offset:offset + w * h * 3]
    if len(pixels) != w * h * 3:
        raise RuntimeError("truncated generated PPM")
    scan = b"".join(b"\x00" + pixels[y*w*3:(y+1)*w*3] for y in range(h))
    def chunk(kind, data):
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xffffffff)
    png = (
        b"\x89PNG\r\n\x1a\n" +
        chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0)) +
        chunk(b"IDAT", zlib.compress(scan, 9)) +
        chunk(b"IEND", b"")
    )
    png_path.write_bytes(png)

class Handler(BaseHTTPRequestHandler):
    server_version = f"ReAI/{VERSION}"

    def authorized(self):
        return not API_KEY or self.headers.get("X-API-Key", "") == API_KEY

    def send_json(self, code, obj):
        body = json.dumps(obj, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/health":
            return self.send_json(200, {"ok": True, "engine": "reai-from-scratch", "version": VERSION})
        if self.path.startswith("/outputs/"):
            if not self.authorized():
                return self.send_json(401, {"error": "unauthorized"})
            name = Path(unquote(self.path[len("/outputs/"):])).name
            path = (OUT_DIR / name).resolve()
            if path.parent != OUT_DIR or not path.is_file() or path.suffix.lower() != ".png":
                return self.send_json(404, {"error": "not found"})
            data = path.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "image/png")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
            return
        self.send_json(404, {"error": "not found"})

    def do_POST(self):
        if not self.authorized():
            return self.send_json(401, {"error": "unauthorized"})
        try:
            n = int(self.headers.get("content-length", "0"))
            if n > 2_000_000:
                return self.send_json(413, {"error": "request too large"})
            data = json.loads(self.rfile.read(n) or b"{}")

            if self.path == "/v1/chat/completions":
                messages = data.get("messages") or []

                # Security checks are outside the model and cannot be overridden by prompting.
                for m in messages:
                    content = str(m.get("content", ""))
                    ok, rule = check_text(
                        content,
                        "chat",
                        detect_injection=(str(m.get("role", "user")) == "user")
                    )
                    if not ok:
                        return self.send_json(400, public_error(rule))

                user_prompt = "\n".join(
                    f"{m.get('role','user')}: {m.get('content','')}" for m in messages
                )
                prompt = control_prefix() + user_prompt
                tokens = max(1, min(int(data.get("max_tokens", 256)), 4096))
                text = run("text-generate", TEXT_MODEL, prompt, tokens,
                           data.get("temperature", 0.9), data.get("top_k", 40))
                generated = text[len(prompt):] if text.startswith(prompt) else text
                generated = generated.strip()

                ok, rule = check_generated_text(generated, user_prompt, "chat")
                if not ok:
                    generated = "Не могу помочь с этим запросом."

                return self.send_json(200, {
                    "object": "chat.completion",
                    "model": f"reai-{VERSION}",
                    "choices": [{"index": 0, "message": {"role": "assistant", "content": generated}}]
                })

            if self.path == "/v1/images/generations":
                prompt = str(data.get("prompt", ""))[:4000]
                ok, rule = check_text(prompt, "image_generation", detect_injection=True)
                if not ok:
                    return self.send_json(400, public_error(rule))
                token = os.urandom(8).hex()
                ppm = OUT_DIR / f"img-{token}.ppm"
                png = OUT_DIR / f"img-{token}.png"
                run("image-generate", IMAGE_MODEL, prompt, ppm, int(data.get("steps", 24)))
                ppm_to_png(ppm, png)
                ppm.unlink(missing_ok=True)
                return self.send_json(200, {
                    "created": True,
                    "data": [{"url": f"/outputs/{png.name}", "format": "png"}]
                })

            self.send_json(404, {"error": "not found"})
        except Exception as e:
            self.send_json(500, {"error": str(e)})

    def log_message(self, fmt, *args):
        print("[api]", fmt % args)

if __name__ == "__main__":
    host = os.getenv("REAI_HOST", "127.0.0.1")
    port = int(os.getenv("REAI_PORT", "8080"))
    print(f"ReAI {VERSION} API http://{host}:{port}")
    ThreadingHTTPServer((host, port), Handler).serve_forever()
