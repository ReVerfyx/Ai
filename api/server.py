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

VERSION = "0.0.3"
ROOT = Path(__file__).resolve().parents[1]
BIN = Path(os.getenv("REAI_BIN", ROOT / "build" / "reai"))
TEXT_MODEL = Path(os.getenv("REAI_TEXT_MODEL", ROOT / "models" / "text.bin"))
IMAGE_MODEL = Path(os.getenv("REAI_IMAGE_MODEL", ROOT / "models" / "image.bin"))
OUT_DIR = Path(os.getenv("REAI_OUTPUT_DIR", ROOT / "outputs")).resolve()
API_KEY = os.getenv("REAI_API_KEY", "")
API_KEYS_FILE = Path(os.getenv("REAI_API_KEYS_FILE", "/etc/reai-api-keys.json"))
TRUSTED_GATEWAY_IP = os.getenv("REAI_TRUSTED_GATEWAY_IP", "31.77.14.194").strip()
MOBILE_APP_KEY = os.getenv("REAI_MOBILE_APP_KEY", "reai-mobile-v1").strip()
OUT_DIR.mkdir(parents=True, exist_ok=True)
sys.path.insert(0, str(ROOT))
from policy.runtime import check_text, check_generated_text, public_error, control_prefix

def run(*args, timeout=600):
    # The byte-level model can temporarily emit arbitrary byte sequences while
    # undertrained. Capture raw bytes so one invalid UTF-8 byte cannot crash
    # the whole HTTP request with UnicodeDecodeError.
    p = subprocess.run([str(BIN), *map(str, args)], capture_output=True, timeout=timeout)
    stdout = (p.stdout or b"").decode("utf-8", errors="replace")
    stderr = (p.stderr or b"").decode("utf-8", errors="replace")
    if p.returncode:
        raise RuntimeError((stderr or stdout).strip())
    return stdout

def text_engine(model_path: Path):
    try:
        with model_path.open("rb") as fh:
            magic = fh.read(8)
        if magic == b"REAIUC51":
            return "unicode"
        return "sparse" if magic == b"REAISP21" else "text"
    except Exception:
        return "text"

def configured_keys():
    keys = set()
    if API_KEY:
        keys.add(API_KEY)
    try:
        data = json.loads(API_KEYS_FILE.read_text(encoding="utf-8"))
        for item in data.get("keys", []):
            value = str(item.get("key", "")).strip()
            if value:
                keys.add(value)
    except Exception:
        pass
    return keys

def message_text_and_images(content):
    """Return visible text and whether an OpenAI-style message contains images.

    Never stringify data: URLs/base64 into policy input or the text-model prompt.
    """
    if isinstance(content, str):
        return content, False
    if not isinstance(content, list):
        return "", False

    parts = []
    has_image = False
    for part in content:
        if not isinstance(part, dict):
            continue
        kind = str(part.get("type", "")).lower()
        if kind == "text":
            value = part.get("text", "")
            if isinstance(value, str) and value.strip():
                parts.append(value)
        elif kind in ("image_url", "input_image", "image"):
            has_image = True
    return "\n".join(parts), has_image

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
        if TRUSTED_GATEWAY_IP and self.client_address and self.client_address[0] == TRUSTED_GATEWAY_IP:
            return True
        keys = configured_keys()
        if not keys:
            return True
        supplied = self.headers.get("X-API-Key", "").strip()
        auth = self.headers.get("Authorization", "").strip()
        if auth.lower().startswith("bearer "):
            supplied = auth[7:].strip()
        if MOBILE_APP_KEY and supplied == MOBILE_APP_KEY:
            return True
        return supplied in keys

    def send_json(self, code, obj):
        body = json.dumps(obj, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/v1/models":
            if not self.authorized():
                return self.send_json(401, {"error": "unauthorized"})
            return self.send_json(200, {
                "object": "list",
                "data": [{
                    "id": "reverfyx-ai",
                    "object": "model",
                    "owned_by": "ReVerfyx"
                }]
            })

        if self.path == "/health":
            return self.send_json(200, {
                "ok": True,
                "engine": "reai-from-scratch",
                "text_engine": text_engine(TEXT_MODEL),
                "version": VERSION,
                "image_generation": True
            })
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

                # Only visible user text is policy-checked. Image data/base64
                # must never be stringified into either policy input or a text prompt.
                normalized = []
                has_images = False
                for m in messages:
                    role = str(m.get("role", "user"))
                    visible_text, message_has_image = message_text_and_images(m.get("content", ""))
                    has_images = has_images or message_has_image

                    if role == "user" and visible_text:
                        ok, rule = check_text(visible_text, "chat", detect_injection=True)
                        if not ok:
                            return self.send_json(400, public_error(rule))

                    if visible_text:
                        normalized.append(f"{role}: {visible_text}")
                    elif message_has_image:
                        normalized.append(f"{role}: [изображение прикреплено]")

                if has_images:
                    return self.send_json(422, {
                        "error": "vision_not_supported",
                        "message": "Текущая модель ReVerfyx AI пока не умеет анализировать изображения."
                    })

                user_prompt = "\n".join(normalized)
                engine = text_engine(TEXT_MODEL)

                # The tiny Unicode experiment is trained on dialogue turns.
                # Runtime policy is enforced outside the model, so do not drown
                # a sub-million-parameter model in a long hidden control prompt.
                if engine == "unicode":
                    # During the fast experiment, old assistant garbage in chat
                    # history is harmful training context. Condition only on the
                    # latest visible user turn and the exact dialogue marker used
                    # by the warm-up corpus.
                    latest_user = ""
                    for line in reversed(normalized):
                        if line.startswith("user:"):
                            latest_user = line[len("user:"):].strip()
                            break
                    prompt = f"user: {latest_user}\nassistant:"
                    temperature = min(float(data.get("temperature", 0.30)), 0.40)
                    top_k = min(max(1, int(data.get("top_k", 4))), 6)
                    tokens = max(1, min(int(data.get("max_tokens", 96)), 160))
                else:
                    prompt = control_prefix() + user_prompt
                    temperature = float(data.get("temperature", 0.9))
                    top_k = int(data.get("top_k", 40))
                    tokens = max(1, min(int(data.get("max_tokens", 256)), 4096))

                cmd = "unicode-generate" if engine == "unicode" else ("sparse-generate" if engine == "sparse" else "text-generate")
                text = run(cmd, TEXT_MODEL, prompt, tokens, temperature, top_k)
                generated = text[len(prompt):] if text.startswith(prompt) else text
                generated = generated.strip()
                if engine == "unicode":
                    # Do not let a tiny model invent the next conversation turn.
                    for marker in ("\nuser:", "\nassistant:"):
                        if marker in generated:
                            generated = generated.split(marker, 1)[0].strip()

                # Undertrained byte-level checkpoints can emit invalid UTF-8.
                # Do not surface replacement-character garbage as a successful reply.
                replacement_count = generated.count("\ufffd")
                control_count = sum(
                    1 for ch in generated
                    if ord(ch) < 32 and ch not in "\n\r\t"
                )
                if (
                    not generated
                    or replacement_count >= 2
                    or (generated and replacement_count / max(1, len(generated)) > 0.01)
                    or control_count > 0
                ):
                    return self.send_json(503, {
                        "error": "model_output_not_ready",
                        "message": "Модель ещё обучается: сгенерированный ответ не прошёл проверку текста."
                    })

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
