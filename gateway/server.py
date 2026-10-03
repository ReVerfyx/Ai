#!/usr/bin/env python3
"""ReVerfyx AI application gateway.

Runs on the client/user server (default public host: 31.77.14.194).
The Android app talks only to this gateway. The gateway stores users/chats/files
and forwards model work to the private AI backend (default 2.26.85.86:8080).
"""
import base64
import hashlib
import hmac
import json
import mimetypes
import os
import secrets
import sqlite3
import sys
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from policy.runtime import check_text, check_generated_text, public_error, wrap_untrusted, control_prefix

VERSION = "0.0.2"
LISTEN_HOST = os.getenv("REAI_GATEWAY_HOST", "0.0.0.0")
LISTEN_PORT = int(os.getenv("REAI_GATEWAY_PORT", "8090"))
AI_BASE = os.getenv("REAI_AI_BASE", "http://2.26.85.86:8080").rstrip("/")
AI_KEY = os.getenv("REAI_AI_KEY", "")
DB_PATH = Path(os.getenv("REAI_GATEWAY_DB", ROOT / "data" / "gateway.sqlite3"))
FILES_DIR = Path(os.getenv("REAI_GATEWAY_FILES", ROOT / "data" / "gateway-files"))
MEDIA_DIR = Path(os.getenv("REAI_GATEWAY_MEDIA", ROOT / "data" / "gateway-media"))
MAX_UPLOAD = int(os.getenv("REAI_MAX_UPLOAD_BYTES", str(12 * 1024 * 1024)))
SESSION_DAYS = int(os.getenv("REAI_SESSION_DAYS", "30"))

DB_PATH.parent.mkdir(parents=True, exist_ok=True)
FILES_DIR.mkdir(parents=True, exist_ok=True)
MEDIA_DIR.mkdir(parents=True, exist_ok=True)

def db():
    c = sqlite3.connect(DB_PATH, timeout=30)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA foreign_keys=ON")
    c.execute("PRAGMA journal_mode=WAL")
    return c

def init_db():
    with db() as c:
        c.executescript("""
        CREATE TABLE IF NOT EXISTS users(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE COLLATE NOCASE,
            password_hash BLOB NOT NULL,
            salt BLOB NOT NULL,
            created_at INTEGER NOT NULL
        );
        CREATE TABLE IF NOT EXISTS sessions(
            token_hash TEXT PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            expires_at INTEGER NOT NULL
        );
        CREATE TABLE IF NOT EXISTS chats(
            id TEXT PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            title TEXT NOT NULL,
            created_at INTEGER NOT NULL,
            updated_at INTEGER NOT NULL
        );
        CREATE TABLE IF NOT EXISTS messages(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id TEXT NOT NULL REFERENCES chats(id) ON DELETE CASCADE,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            created_at INTEGER NOT NULL
        );
        CREATE TABLE IF NOT EXISTS files(
            id TEXT PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            chat_id TEXT REFERENCES chats(id) ON DELETE SET NULL,
            name TEXT NOT NULL,
            mime TEXT NOT NULL,
            path TEXT NOT NULL,
            size INTEGER NOT NULL,
            created_at INTEGER NOT NULL
        );
        CREATE TABLE IF NOT EXISTS media(
            id TEXT PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            path TEXT NOT NULL,
            mime TEXT NOT NULL,
            created_at INTEGER NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_chats_user_updated ON chats(user_id, updated_at DESC);
        CREATE INDEX IF NOT EXISTS idx_messages_chat_id ON messages(chat_id, id);
        """)

def password_hash(password, salt):
    return hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 240000)

def token_hash(token):
    return hashlib.sha256(token.encode()).hexdigest()

def ai_request(path, payload=None, binary=False):
    data = None if payload is None else json.dumps(payload, ensure_ascii=False).encode()
    req = Request(AI_BASE + path, data=data)
    if payload is not None:
        req.add_header("Content-Type", "application/json; charset=utf-8")
    if AI_KEY:
        req.add_header("X-API-Key", AI_KEY)
    try:
        with urlopen(req, timeout=600) as r:
            body = r.read()
            return body if binary else json.loads(body.decode("utf-8"))
    except HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        try:
            detail = json.loads(body)
        except Exception:
            detail = {"error": body or f"AI backend HTTP {e.code}"}
        raise RuntimeError(json.dumps(detail, ensure_ascii=False))

def valid_username(s):
    return 3 <= len(s) <= 32 and all(ch.isalnum() or ch in "._-" for ch in s)

def chat_title(text):
    compact = " ".join(text.strip().split())
    return (compact[:42] + ("…" if len(compact) > 42 else "")) or "Новый чат"

def now():
    return int(time.time())

def text_attachment(path, name, mime):
    ext = Path(name).suffix.lower()
    text_ext = {
        ".txt",".md",".json",".xml",".html",".css",".js",".ts",".jsx",".tsx",
        ".py",".java",".kt",".kts",".c",".cc",".cpp",".h",".hpp",".cs",".go",
        ".rs",".php",".rb",".sh",".sql",".yaml",".yml",".toml",".ini",".gradle"
    }
    if mime.startswith("text/") or ext in text_ext or mime in {"application/json","application/xml"}:
        raw = Path(path).read_bytes()[:300_000]
        return raw.decode("utf-8", errors="replace")
    return None

class Handler(BaseHTTPRequestHandler):
    server_version = f"ReAIGateway/{VERSION}"

    def json(self, code, obj):
        raw = json.dumps(obj, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def body_json(self, limit=2_000_000):
        n = int(self.headers.get("Content-Length", "0"))
        if n < 0 or n > limit:
            raise ValueError("request too large")
        return json.loads(self.rfile.read(n) or b"{}")

    def current_user(self):
        auth = self.headers.get("Authorization", "")
        if not auth.startswith("Bearer "):
            return None
        th = token_hash(auth[7:].strip())
        with db() as c:
            row = c.execute("""
                SELECT u.id,u.username FROM sessions s
                JOIN users u ON u.id=s.user_id
                WHERE s.token_hash=? AND s.expires_at>?
            """, (th, now())).fetchone()
        return dict(row) if row else None

    def require_user(self):
        user = self.current_user()
        if not user:
            self.json(401, {"error":"unauthorized"})
            return None
        return user

    def owned_chat(self, user_id, chat_id):
        with db() as c:
            return c.execute("SELECT * FROM chats WHERE id=? AND user_id=?", (chat_id, user_id)).fetchone()

    def do_GET(self):
        if self.path == "/health":
            return self.json(200, {
                "ok": True,
                "version": VERSION,
                "role": "application-gateway",
                "capabilities": {
                    "accounts": True,
                    "chat_history": True,
                    "chat": True,
                    "image_generation": True,
                    "text_code_files": True,
                    "image_understanding": False,
                    "video_understanding": False,
                    "voice": False
                }
            })

        user = self.require_user()
        if not user:
            return

        if self.path == "/v1/me":
            return self.json(200, {"id": user["id"], "username": user["username"]})

        if self.path == "/v1/chats":
            with db() as c:
                rows = c.execute(
                    "SELECT id,title,created_at,updated_at FROM chats WHERE user_id=? ORDER BY updated_at DESC",
                    (user["id"],)
                ).fetchall()
            return self.json(200, {"data":[dict(r) for r in rows]})

        if self.path.startswith("/v1/chats/") and self.path.endswith("/messages"):
            parts = self.path.split("/")
            if len(parts) == 5:
                cid = parts[3]
                if not self.owned_chat(user["id"], cid):
                    return self.json(404, {"error":"chat_not_found"})
                with db() as c:
                    rows = c.execute(
                        "SELECT id,role,content,created_at FROM messages WHERE chat_id=? ORDER BY id",
                        (cid,)
                    ).fetchall()
                return self.json(200, {"data":[dict(r) for r in rows]})

        if self.path.startswith("/v1/media/"):
            media_id = self.path.rsplit("/", 1)[-1]
            with db() as c:
                row = c.execute("SELECT path,mime FROM media WHERE id=? AND user_id=?", (media_id, user["id"])).fetchone()
            if not row:
                return self.json(404, {"error":"media_not_found"})
            p = Path(row["path"])
            if not p.is_file():
                return self.json(404, {"error":"media_missing"})
            raw = p.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", row["mime"])
            self.send_header("Cache-Control", "private, no-store")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)
            return

        return self.json(404, {"error":"not_found"})

    def do_POST(self):
        try:
            if self.path == "/v1/auth/register":
                data = self.body_json()
                username = str(data.get("username","")).strip()
                password = str(data.get("password",""))
                if not valid_username(username):
                    return self.json(400, {"error":"username must be 3-32 chars: letters, digits, . _ -"})
                if len(password) < 8 or len(password) > 200:
                    return self.json(400, {"error":"password must be 8-200 chars"})
                salt = os.urandom(16)
                ph = password_hash(password, salt)
                try:
                    with db() as c:
                        cur = c.execute(
                            "INSERT INTO users(username,password_hash,salt,created_at) VALUES(?,?,?,?)",
                            (username, ph, salt, now())
                        )
                        uid = cur.lastrowid
                except sqlite3.IntegrityError:
                    return self.json(409, {"error":"username_taken"})
                return self._new_session(uid, username)

            if self.path == "/v1/auth/login":
                data = self.body_json()
                username = str(data.get("username","")).strip()
                password = str(data.get("password",""))
                with db() as c:
                    row = c.execute("SELECT * FROM users WHERE username=?", (username,)).fetchone()
                if not row or not hmac.compare_digest(row["password_hash"], password_hash(password, row["salt"])):
                    return self.json(401, {"error":"invalid_credentials"})
                return self._new_session(row["id"], row["username"])

            user = self.require_user()
            if not user:
                return

            if self.path == "/v1/auth/logout":
                auth = self.headers.get("Authorization", "")
                if auth.startswith("Bearer "):
                    with db() as c:
                        c.execute("DELETE FROM sessions WHERE token_hash=?", (token_hash(auth[7:].strip()),))
                return self.json(200, {"ok":True})

            if self.path == "/v1/chats":
                data = self.body_json()
                title = str(data.get("title","Новый чат")).strip()[:80] or "Новый чат"
                cid = uuid.uuid4().hex
                ts = now()
                with db() as c:
                    c.execute("INSERT INTO chats(id,user_id,title,created_at,updated_at) VALUES(?,?,?,?,?)",
                              (cid,user["id"],title,ts,ts))
                return self.json(201, {"id":cid,"title":title,"created_at":ts,"updated_at":ts})

            if self.path.startswith("/v1/chats/") and self.path.endswith("/messages"):
                parts = self.path.split("/")
                if len(parts) != 5:
                    return self.json(404, {"error":"not_found"})
                cid = parts[3]
                chat = self.owned_chat(user["id"], cid)
                if not chat:
                    return self.json(404, {"error":"chat_not_found"})
                data = self.body_json(limit=4_000_000)
                content = str(data.get("content","")).strip()
                file_ids = data.get("file_ids") or []
                if not content and not file_ids:
                    return self.json(400, {"error":"empty_message"})

                extra = []
                if file_ids:
                    with db() as c:
                        qmarks = ",".join("?" for _ in file_ids)
                        rows = c.execute(
                            f"SELECT * FROM files WHERE user_id=? AND id IN ({qmarks})",
                            [user["id"], *file_ids]
                        ).fetchall() if qmarks else []
                    for r in rows:
                        txt = text_attachment(r["path"], r["name"], r["mime"])
                        if txt is not None:
                            ok, rule = check_text(txt, "file_analysis")
                            if not ok:
                                return self.json(400, public_error(rule))
                            extra.append(wrap_untrusted(txt, f"file {r['name']}"))
                        else:
                            extra.append(f"\n\n[ATTACHMENT {r['name']}: stored, binary analysis is not available in 0.0.2]")

                attachment_names = [r["name"] for r in rows] if file_ids else []
                visible_user_content = content
                if attachment_names:
                    visible_user_content += ("\n" if visible_user_content else "") + "📎 " + ", ".join(attachment_names)
                full_user_content = content + "".join(extra)
                ok, rule = check_text(content, "chat", detect_injection=True)
                if not ok:
                    return self.json(400, public_error(rule))
                ok, rule = check_text(full_user_content, "chat")
                if not ok:
                    return self.json(400, public_error(rule))

                with db() as c:
                    c.execute("INSERT INTO messages(chat_id,role,content,created_at) VALUES(?,?,?,?)",
                              (cid,"user",visible_user_content,now()))
                    if chat["title"] == "Новый чат" and content:
                        c.execute("UPDATE chats SET title=?,updated_at=? WHERE id=?",
                                  (chat_title(content),now(),cid))
                    else:
                        c.execute("UPDATE chats SET updated_at=? WHERE id=?", (now(),cid))
                    history = c.execute(
                        "SELECT role,content FROM messages WHERE chat_id=? ORDER BY id DESC LIMIT 30",
                        (cid,)
                    ).fetchall()
                messages = [dict(r) for r in reversed(history)]
                if extra:
                    messages[-1]["content"] = full_user_content
                messages.insert(0, {"role":"system","content":control_prefix()})
                result = ai_request("/v1/chat/completions", {
                    "messages": messages,
                    "max_tokens": max(1,min(int(data.get("max_tokens",512)),4096)),
                    "temperature": float(data.get("temperature",0.85)),
                    "top_k": int(data.get("top_k",40))
                })
                answer = result["choices"][0]["message"]["content"]
                ok, rule = check_generated_text(answer, full_user_content, "chat")
                if not ok:
                    answer = "Не могу помочь с этим запросом."
                with db() as c:
                    cur = c.execute("INSERT INTO messages(chat_id,role,content,created_at) VALUES(?,?,?,?)",
                                    (cid,"assistant",answer,now()))
                    c.execute("UPDATE chats SET updated_at=? WHERE id=?", (now(),cid))
                    mid = cur.lastrowid
                return self.json(200, {"id":mid,"role":"assistant","content":answer,"chat_id":cid})

            if self.path == "/v1/files":
                data = self.body_json(limit=18_000_000)
                name = Path(str(data.get("name","file.bin"))).name[:180] or "file.bin"
                mime = str(data.get("mime") or mimetypes.guess_type(name)[0] or "application/octet-stream")
                encoded = str(data.get("data_base64",""))
                try:
                    raw = base64.b64decode(encoded, validate=True)
                except Exception:
                    return self.json(400, {"error":"invalid_base64"})
                if len(raw) > MAX_UPLOAD:
                    return self.json(413, {"error":"file_too_large","max_bytes":MAX_UPLOAD})
                fid = uuid.uuid4().hex
                path = FILES_DIR / fid
                path.write_bytes(raw)
                cid = data.get("chat_id")
                if cid and not self.owned_chat(user["id"], str(cid)):
                    path.unlink(missing_ok=True)
                    return self.json(404, {"error":"chat_not_found"})
                with db() as c:
                    c.execute("INSERT INTO files(id,user_id,chat_id,name,mime,path,size,created_at) VALUES(?,?,?,?,?,?,?,?)",
                              (fid,user["id"],cid,name,mime,str(path),len(raw),now()))
                return self.json(201, {"id":fid,"name":name,"mime":mime,"size":len(raw)})

            if self.path == "/v1/images/generations":
                data = self.body_json()
                prompt = str(data.get("prompt","")).strip()
                ok, rule = check_text(prompt, "image_generation", detect_injection=True)
                if not ok:
                    return self.json(400, public_error(rule))
                result = ai_request("/v1/images/generations", {
                    "prompt": prompt,
                    "steps": max(2,min(int(data.get("steps",32)),128))
                })
                remote = result["data"][0]["url"]
                raw = ai_request(remote, payload=None, binary=True)
                media_id = uuid.uuid4().hex
                path = MEDIA_DIR / f"{media_id}.png"
                path.write_bytes(raw)
                media_url = f"/v1/media/{media_id}"
                with db() as c:
                    c.execute("INSERT INTO media(id,user_id,path,mime,created_at) VALUES(?,?,?,?,?)",
                              (media_id,user["id"],str(path),"image/png",now()))
                    cid = str(data.get("chat_id","")).strip()
                    if cid and self.owned_chat(user["id"], cid):
                        c.execute("INSERT INTO messages(chat_id,role,content,created_at) VALUES(?,?,?,?)",
                                  (cid,"user","Создай изображение: " + prompt,now()))
                        c.execute("INSERT INTO messages(chat_id,role,content,created_at) VALUES(?,?,?,?)",
                                  (cid,"assistant","[image:" + media_url + "]",now()))
                        c.execute("UPDATE chats SET updated_at=? WHERE id=?", (now(),cid))
                return self.json(200, {"created":True,"data":[{"url":media_url,"format":"png"}]})

            return self.json(404, {"error":"not_found"})
        except ValueError as e:
            return self.json(413, {"error":str(e)})
        except Exception as e:
            return self.json(500, {"error":"gateway_error","detail":str(e)})

    def do_PATCH(self):
        user = self.require_user()
        if not user:
            return
        if self.path.startswith("/v1/chats/"):
            cid = self.path.rsplit("/",1)[-1]
            if not self.owned_chat(user["id"], cid):
                return self.json(404, {"error":"chat_not_found"})
            try:
                data = self.body_json()
                title = str(data.get("title","")).strip()[:80]
                if not title:
                    return self.json(400, {"error":"empty_title"})
                with db() as c:
                    c.execute("UPDATE chats SET title=?,updated_at=? WHERE id=? AND user_id=?",
                              (title,now(),cid,user["id"]))
                return self.json(200, {"id":cid,"title":title})
            except Exception as e:
                return self.json(400, {"error":str(e)})
        return self.json(404, {"error":"not_found"})

    def do_DELETE(self):
        user = self.require_user()
        if not user:
            return
        if self.path.startswith("/v1/chats/"):
            cid = self.path.rsplit("/",1)[-1]
            with db() as c:
                cur = c.execute("DELETE FROM chats WHERE id=? AND user_id=?", (cid,user["id"]))
            if not cur.rowcount:
                return self.json(404, {"error":"chat_not_found"})
            return self.json(200, {"ok":True})
        return self.json(404, {"error":"not_found"})

    def _new_session(self, uid, username):
        token = secrets.token_urlsafe(32)
        expiry = now() + SESSION_DAYS * 86400
        with db() as c:
            c.execute("DELETE FROM sessions WHERE expires_at<=?", (now(),))
            c.execute("INSERT INTO sessions(token_hash,user_id,expires_at) VALUES(?,?,?)",
                      (token_hash(token),uid,expiry))
        return self.json(200, {"token":token,"expires_at":expiry,"user":{"id":uid,"username":username}})

    def log_message(self, fmt, *args):
        print("[gateway]", fmt % args)

if __name__ == "__main__":
    init_db()
    print(f"ReAI gateway {VERSION} listening on {LISTEN_HOST}:{LISTEN_PORT}; AI backend={AI_BASE}")
    ThreadingHTTPServer((LISTEN_HOST, LISTEN_PORT), Handler).serve_forever()
