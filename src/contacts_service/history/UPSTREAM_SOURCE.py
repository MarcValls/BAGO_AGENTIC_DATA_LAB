"""Standalone contacts service. Python standard library only; no ADL imports."""
from __future__ import annotations

import argparse
import base64
import csv
import ctypes
import hashlib
import hmac
import io
import json
import os
from pathlib import Path
import re
import secrets
import sqlite3
import subprocess
import sys
import threading
import time
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlencode, urlparse
from urllib.request import Request, build_opener, HTTPRedirectHandler
from urllib.error import HTTPError, URLError

VERSION = "0.1.0"
SCOPE = "https://www.googleapis.com/auth/contacts.readonly"
AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
PEOPLE_URL = "https://people.googleapis.com/v1/people/me/connections"


def now():
    return datetime.now(timezone.utc).isoformat()


def canonical(obj):
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def digest(obj):
    return hashlib.sha256(canonical(obj).encode()).hexdigest()


class ServiceError(Exception):
    def __init__(self, code, message, status=400):
        super().__init__(message)
        self.code, self.status = code, status


def protect_directory(path):
    path.mkdir(parents=True, exist_ok=True)
    if os.name == "nt":
        result = subprocess.run(["whoami", "/user", "/fo", "csv", "/nh"], capture_output=True, check=True)
        sid = next(csv.reader(io.StringIO(result.stdout.decode(errors="replace"))))[1]
        if not re.fullmatch(r"S-1-[0-9-]+", sid):
            raise ServiceError("protection_failed", "Could not resolve current user SID", 503)
        result = subprocess.run(["icacls", str(path), "/inheritance:r", "/grant:r",
                                 f"*{sid}:(OI)(CI)F", "*S-1-5-18:(OI)(CI)F"], capture_output=True)
        if result.returncode:
            raise ServiceError("protection_failed", "Could not protect private data directory", 503)
    else:
        path.chmod(0o700)


def dpapi(data, decrypt=False):
    class Blob(ctypes.Structure):
        _fields_ = [("size", ctypes.c_ulong), ("data", ctypes.POINTER(ctypes.c_ubyte))]
    array = (ctypes.c_ubyte * len(data)).from_buffer_copy(data)
    source, target = Blob(len(data), array), Blob()
    function = ctypes.windll.crypt32.CryptUnprotectData if decrypt else ctypes.windll.crypt32.CryptProtectData
    if not function(ctypes.byref(source), None, None, None, None, 1, ctypes.byref(target)):
        raise ServiceError("secret_protection_failed", "Windows credential protection failed", 503)
    try:
        return ctypes.string_at(target.data, target.size)
    finally:
        ctypes.windll.kernel32.LocalFree(target.data)


class PrivateStore:
    def __init__(self, root):
        self.root = Path(root).resolve()
        protect_directory(self.root)

    def read(self, name):
        path = self.root / name
        if not path.exists():
            return None
        try:
            raw = path.read_bytes()
            if os.name == "nt":
                raw = dpapi(raw, True)
            return json.loads(raw)
        except ServiceError:
            raise
        except Exception:
            raise ServiceError("private_state_invalid", "Private state cannot be decoded", 503) from None

    def write(self, name, value):
        raw = canonical(value).encode()
        if os.name == "nt":
            raw = dpapi(raw)
        temporary = self.root / (name + "." + uuid.uuid4().hex + ".tmp")
        try:
            descriptor = os.open(temporary, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            with os.fdopen(descriptor, "wb") as handle:
                handle.write(raw)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, self.root / name)
        finally:
            temporary.unlink(missing_ok=True)

    def remove(self, name):
        (self.root / name).unlink(missing_ok=True)


def validate_contact(data):
    if not isinstance(data, dict):
        raise ServiceError("invalid_contact", "Contact must be an object")
    if any(data.get(key) is not None and not isinstance(data[key], str) for key in ("name", "phone", "email")):
        raise ServiceError("invalid_contact", "Contact fields must be strings")
    name, phone, email = ((data.get(key) or "").strip() for key in ("name", "phone", "email"))
    if not name or len(name) > 200 or any(ord(c) < 32 for c in name):
        raise ServiceError("invalid_name", "Name must contain 1–200 printable characters")
    if phone:
        phone = re.sub(r"[\s().-]", "", phone)
        if not re.fullmatch(r"\+[1-9]\d{6,14}", phone):
            raise ServiceError("invalid_phone", "Phone must include an explicit E.164 country prefix")
    if email:
        if len(email) > 254 or not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email):
            raise ServiceError("invalid_email", "Invalid email")
        email = email.casefold()
    if not phone and not email:
        raise ServiceError("missing_destination", "Phone or email is required")
    return {"name": name, "phone": phone, "email": email}


class Contacts:
    def __init__(self, root):
        self.private = PrivateStore(root)
        self.root = self.private.root
        with self.connect() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS contacts (
                  id TEXT PRIMARY KEY,name TEXT NOT NULL,phone TEXT NOT NULL,email TEXT NOT NULL,
                  source TEXT NOT NULL,source_id TEXT NOT NULL,revision TEXT NOT NULL,
                  created_at TEXT NOT NULL,updated_at TEXT NOT NULL);
                CREATE UNIQUE INDEX IF NOT EXISTS phone_unique ON contacts(phone) WHERE phone <> '';
                CREATE UNIQUE INDEX IF NOT EXISTS email_unique ON contacts(email) WHERE email <> '';
                CREATE UNIQUE INDEX IF NOT EXISTS origin_unique ON contacts(source,source_id) WHERE source_id <> '';
                CREATE TABLE IF NOT EXISTS previews (id TEXT PRIMARY KEY, revision TEXT NOT NULL,
                  expires REAL NOT NULL, payload TEXT NOT NULL);
            """)

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.root / "contacts.sqlite3", timeout=15)
        db.row_factory = sqlite3.Row
        try:
            with db:
                yield db
        finally:
            db.close()

    def list(self, query=""):
        if len(query) > 200:
            raise ServiceError("invalid_query", "Query too long")
        with self.connect() as db:
            return {"contacts": [dict(row) for row in db.execute("SELECT * FROM contacts ORDER BY name COLLATE NOCASE,id")
                                 if query.casefold() in " ".join((row["name"], row["phone"], row["email"])).casefold()]}

    def get(self, identity):
        with self.connect() as db:
            row = db.execute("SELECT * FROM contacts WHERE id=?", (identity,)).fetchone()
        if row is None:
            raise ServiceError("not_found", "Contact does not exist", 404)
        return dict(row)

    @staticmethod
    def duplicates(db, record, exclude=""):
        return [dict(row) for row in db.execute("SELECT id,name FROM contacts WHERE id != ? AND "
                "((phone != '' AND phone=?) OR (email != '' AND email=?) OR "
                "(source_id != '' AND source=? AND source_id=?))",
                (exclude, record.get("phone", ""), record.get("email", ""), record.get("source", ""), record.get("source_id", "")))]

    def _insert(self, db, data, source="local", source_id=""):
        record = dict(validate_contact(data), source=source, source_id=source_id)
        if self.duplicates(db, record):
            raise ServiceError("duplicate", "Phone, email or origin already exists; review existing contact", 409)
        record.update(id="contact_" + uuid.uuid4().hex, revision=uuid.uuid4().hex, created_at=now(), updated_at=now())
        db.execute("INSERT INTO contacts VALUES (:id,:name,:phone,:email,:source,:source_id,:revision,:created_at,:updated_at)", record)
        return record

    def add(self, data):
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            return self._insert(db, data)

    def update(self, identity, data):
        record = validate_contact(data)
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            old = db.execute("SELECT * FROM contacts WHERE id=?", (identity,)).fetchone()
            if old is None:
                raise ServiceError("not_found", "Contact does not exist", 404)
            if not data.get("expected_revision") or old["revision"] != data["expected_revision"]:
                raise ServiceError("revision_conflict", "Contact changed; reload before editing", 409)
            if self.duplicates(db, record, identity):
                raise ServiceError("duplicate", "Phone or email already exists", 409)
            record.update(id=identity, revision=uuid.uuid4().hex, updated_at=now())
            db.execute("UPDATE contacts SET name=:name,phone=:phone,email=:email,revision=:revision,updated_at=:updated_at WHERE id=:id", record)
            result = dict(old)
            result.update(record)
            return result

    def delete(self, identity, data):
        if data.get("confirmed") is not True:
            raise ServiceError("confirmation_required", "Explicit local deletion confirmation is required")
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT revision FROM contacts WHERE id=?", (identity,)).fetchone()
            if row is None:
                raise ServiceError("not_found", "Contact does not exist", 404)
            if row["revision"] != data.get("expected_revision"):
                raise ServiceError("revision_conflict", "Contact changed; reload before deleting", 409)
            db.execute("DELETE FROM contacts WHERE id=?", (identity,))
        return {"deleted": True, "id": identity}

    def preview_people(self, people, source="fixture"):
        if source not in ("google", "fixture") or not isinstance(people, list):
            raise ServiceError("invalid_preview", "Expected People API connections array")
        rows = []
        seen = set()
        with self.connect() as db:
            for person in people:
                if not isinstance(person, dict):
                    raise ServiceError("invalid_person", "Invalid People API record")
                resource = person.get("resourceName", "")
                names = person.get("names") or []
                name = str(names[0].get("displayName", "") if names else "").strip()
                for kind, values in (("phone", person.get("phoneNumbers", [])), ("email", person.get("emailAddresses", []))):
                    for value in values:
                        raw = value.get("canonicalForm") or value.get("value", "")
                        candidate = {"name": name, "phone": raw if kind == "phone" else "", "email": raw if kind == "email" else ""}
                        warnings = []
                        try:
                            candidate = validate_contact(candidate)
                        except ServiceError as exc:
                            warnings.append(exc.code)
                        origin = resource + ":" + digest({"kind": kind, "value": raw})[:20]
                        selection_id = "selection_" + digest({"source": source, "origin": origin})[:32]
                        if selection_id in seen:
                            continue
                        seen.add(selection_id)
                        candidate.update(selection_id=selection_id, source_id=origin, warnings=warnings)
                        candidate["duplicates"] = self.duplicates(db, dict(candidate, source=source)) if not warnings else []
                        rows.append(candidate)
            payload = {"preview_id": "preview_" + uuid.uuid4().hex, "source": source, "created_at": now(),
                       "expires_at": datetime.fromtimestamp(time.time() + 1800, timezone.utc).isoformat(), "contacts": rows}
            payload["revision"] = digest(payload)
            db.execute("INSERT INTO previews VALUES (?,?,?,?)", (payload["preview_id"], payload["revision"],
                       datetime.fromisoformat(payload["expires_at"]).timestamp(), canonical(payload)))
        return payload

    def import_selected(self, data):
        selected = data.get("selected_ids")
        if not isinstance(selected, list) or not selected or not all(isinstance(x, str) for x in selected) or len(selected) != len(set(selected)):
            raise ServiceError("invalid_selection", "Select one or more unique preview IDs")
        if data.get("duplicate_policy") != "skip":
            raise ServiceError("invalid_duplicate_policy", "Only explicit skip policy is supported")
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT * FROM previews WHERE id=?", (data.get("preview_id"),)).fetchone()
            if row is None:
                raise ServiceError("preview_not_found", "Preview does not exist", 404)
            payload = json.loads(row["payload"])
            actual = dict(payload)
            actual.pop("revision", None)
            if digest(actual) != row["revision"] or payload.get("revision") != row["revision"]:
                raise ServiceError("preview_integrity", "Preview integrity check failed", 409)
            if data.get("expected_revision") != row["revision"]:
                raise ServiceError("revision_conflict", "Preview revision does not match", 409)
            if row["expires"] <= time.time():
                raise ServiceError("preview_expired", "Preview expired; fetch again", 409)
            index = {item["selection_id"]: item for item in payload["contacts"]}
            if any(key not in index for key in selected):
                raise ServiceError("selection_not_found", "Selection contains IDs outside this preview")
            if any(index[key]["warnings"] for key in selected):
                raise ServiceError("invalid_selected_contact", "Selected contact has validation warnings; correct source or add manually")
            imported, skipped = [], []
            for key in selected:
                item = index[key]
                if self.duplicates(db, dict(item, source=payload["source"])):
                    skipped.append({"selection_id": key, "reason": "duplicate"})
                else:
                    imported.append(self._insert(db, item, payload["source"], item["source_id"]))
        return {"imported": imported, "skipped": skipped, "preview_id": payload["preview_id"]}


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *_args, **_kwargs):
        return None


def request_json(url, data=None, token=None):
    headers = {"Accept": "application/json"}
    if token:
        headers["Authorization"] = "Bearer " + token
    encoded = urlencode(data).encode() if data is not None else None
    if encoded is not None:
        headers["Content-Type"] = "application/x-www-form-urlencoded"
    try:
        with build_opener(NoRedirect()).open(Request(url, data=encoded, headers=headers), timeout=30) as response:
            raw = response.read(8 * 1024 * 1024 + 1)
            if len(raw) > 8 * 1024 * 1024:
                raise ServiceError("google_response_too_large", "Google response exceeded limit", 503)
            return json.loads(raw)
    except HTTPError as exc:
        raise ServiceError("google_http_error", f"Google rejected request (HTTP {exc.code}); review consent or reconnect", 503) from None
    except (URLError, ValueError, TimeoutError):
        raise ServiceError("google_unavailable", "Google request failed; no contacts were imported", 503) from None


class Google:
    def __init__(self, contacts, transport=request_json):
        self.contacts, self.private, self.transport = contacts, contacts.private, transport
        self.listeners = []
        self.lock = threading.RLock()

    def status(self):
        config = self.private.read("google-client.bin")
        token = self.private.read("google-token.bin")
        observation = self.private.read("google-observation.bin") or {}
        connected = bool(token and (token.get("expires_at", 0) > time.time() or token.get("refresh_token")))
        return {"configured": bool(config), "connected": connected,
                "state": "connected" if connected else "disconnected", "scope": SCOPE,
                "live_verified": bool(observation.get("success") and observation.get("at", 0) > time.time() - 300),
                "last_error": observation.get("last_error")}

    def configure(self, data):
        path = Path(str(data.get("client_json_path", "")))
        if not path.is_absolute() or not path.is_file():
            raise ServiceError("client_file_required", "An absolute external Desktop OAuth JSON path is required")
        try:
            if path.stat().st_size > 65536:
                raise ValueError()
            config = json.loads(path.read_text(encoding="utf-8-sig"))["installed"]
            if not isinstance(config.get("client_id"), str) or not config["client_id"].endswith(".apps.googleusercontent.com"):
                raise ValueError()
            if config.get("auth_uri", AUTH_URL) != AUTH_URL or config.get("token_uri", TOKEN_URL) != TOKEN_URL:
                raise ValueError()
        except (ValueError, KeyError, TypeError):
            raise ServiceError("invalid_oauth_client", "Expected Google Desktop OAuth client JSON with official endpoints") from None
        with self.lock:
            self.private.write("google-client.bin", {"client_id": config["client_id"], "client_secret": config.get("client_secret", "")})
            for name in ("google-token.bin", "google-observation.bin", "google-pending.bin"):
                self.private.remove(name)
        return self.status()

    def begin(self):
        with self.lock:
            config = self.private.read("google-client.bin")
            if not config:
                raise ServiceError("google_not_configured", "Configure a Desktop OAuth client first", 503)
            owner = self

            class Callback(BaseHTTPRequestHandler):
                def do_GET(self):
                    parsed = urlparse(self.path)
                    if parsed.path != "/oauth/callback":
                        self.send_error(404)
                        return
                    query = parse_qs(parsed.query)
                    try:
                        owner.callback(query.get("state", [""])[0], query.get("code", [""])[0], query.get("error", [""])[0])
                        body = b"Google contacts connected. You can close this window."
                        code = 200
                    except ServiceError:
                        body, code = b"Connection was not completed. Return to the application and reconnect.", 400
                    self.send_response(code)
                    self.send_header("Content-Type", "text/plain; charset=utf-8")
                    self.send_header("Cache-Control", "no-store")
                    self.send_header("Content-Length", str(len(body)))
                    self.end_headers()
                    self.wfile.write(body)

                def log_message(self, *_args):
                    pass  # Authorization codes and state must never appear in logs.

            server = ThreadingHTTPServer(("127.0.0.1", 0), Callback)
            uri = f"http://127.0.0.1:{server.server_address[1]}/oauth/callback"
            verifier = secrets.token_urlsafe(64)
            pending = {"state": secrets.token_urlsafe(32), "verifier": verifier, "redirect_uri": uri, "expires_at": time.time() + 300}
            try:
                self.private.write("google-pending.bin", pending)
            except Exception:
                server.server_close()
                raise
            threading.Thread(target=server.serve_forever, daemon=True).start()
            self.listeners.append(server)
            def expire():
                server.shutdown()
                server.server_close()
            timer = threading.Timer(305, expire)
            timer.daemon = True
            timer.start()
            challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip("=")
            url = AUTH_URL + "?" + urlencode({"client_id": config["client_id"], "redirect_uri": uri,
                      "response_type": "code", "scope": SCOPE, "state": pending["state"], "code_challenge": challenge,
                      "code_challenge_method": "S256", "access_type": "offline", "prompt": "consent"})
            return {"authorization_url": url, "callback_uri": uri,
                    "expires_at": datetime.fromtimestamp(pending["expires_at"], timezone.utc).isoformat()}

    def callback(self, state, code, error=""):
        with self.lock:
            pending = self.private.read("google-pending.bin")
            if not pending or not hmac.compare_digest(pending["state"], state) or pending["expires_at"] <= time.time():
                raise ServiceError("oauth_state_invalid", "OAuth state is invalid or expired")
            self.private.remove("google-pending.bin")  # Consume once, even on provider denial.
            if error or not code:
                raise ServiceError("oauth_denied", "Google consent was denied or incomplete")
            config = self.private.read("google-client.bin")
            token = self.transport(TOKEN_URL, data={"client_id": config["client_id"], "client_secret": config["client_secret"],
                     "code": code, "code_verifier": pending["verifier"], "redirect_uri": pending["redirect_uri"], "grant_type": "authorization_code"})
            self._save_token(token)
        return self.status()

    def _save_token(self, token, previous=None):
        if not isinstance(token, dict) or not token.get("access_token") or str(token.get("token_type", "")).casefold() != "bearer":
            raise ServiceError("invalid_google_token", "Google returned an invalid token", 503)
        if previous and "scope" not in token:
            token = dict(token, scope=previous.get("scope", ""))
        if SCOPE not in str(token.get("scope", "")).split():
            raise ServiceError("missing_google_scope", "Google did not grant read-only contacts permission", 503)
        try:
            ttl = int(token["expires_in"])
            if ttl <= 0 or ttl > 86400:
                raise ValueError()
        except (KeyError, ValueError, TypeError):
            raise ServiceError("invalid_google_expiry", "Google returned an invalid token expiry", 503) from None
        stored = dict(token, expires_at=time.time() + ttl)
        if previous and not stored.get("refresh_token"):
            stored["refresh_token"] = previous.get("refresh_token")
        self.private.write("google-token.bin", stored)

    def _token(self):
        token = self.private.read("google-token.bin")
        if not token:
            raise ServiceError("google_not_connected", "Connect Google contacts first", 503)
        if token.get("expires_at", 0) <= time.time() + 30:
            if not token.get("refresh_token"):
                raise ServiceError("google_token_expired", "Reconnect Google contacts", 503)
            config = self.private.read("google-client.bin")
            renewed = self.transport(TOKEN_URL, data={"grant_type": "refresh_token", "refresh_token": token["refresh_token"],
                       "client_id": config["client_id"], "client_secret": config["client_secret"]})
            self._save_token(renewed, token)
            token = self.private.read("google-token.bin")
        return token["access_token"]

    def preview(self):
        with self.lock:
            try:
                token = self._token()
                people, page, seen = [], "", set()
                for _ in range(100):
                    query = {"personFields": "names,emailAddresses,phoneNumbers", "pageSize": 1000,
                             "sources": "READ_SOURCE_TYPE_CONTACT"}
                    if page:
                        query["pageToken"] = page
                    response = self.transport(PEOPLE_URL + "?" + urlencode(query), token=token)
                    if not isinstance(response, dict) or not isinstance(response.get("connections", []), list):
                        raise ServiceError("invalid_google_response", "Invalid People API response", 503)
                    people.extend(response.get("connections", []))
                    page = response.get("nextPageToken", "")
                    if not page:
                        break
                    if not isinstance(page, str) or page in seen:
                        raise ServiceError("google_pagination_invalid", "Invalid Google page token", 503)
                    seen.add(page)
                else:
                    raise ServiceError("google_preview_limit", "Too many Google pages; no preview created", 503)
                preview = self.contacts.preview_people(people, "google")
                self.private.write("google-observation.bin", {"success": True, "at": time.time(), "last_error": None})
                return preview
            except ServiceError as exc:
                self.private.write("google-observation.bin", {"success": False, "at": time.time(), "last_error": exc.code})
                raise

    def disconnect(self, data):
        if data.get("confirmed") is not True:
            raise ServiceError("confirmation_required", "Confirm local disconnection")
        with self.lock:
            for name in ("google-token.bin", "google-pending.bin", "google-observation.bin"):
                self.private.remove(name)
        return self.status()

    def close(self):
        for server in self.listeners:
            server.shutdown()
            server.server_close()


class API:
    """Framework-neutral dispatch. ADL adapter may provide its existing auth boundary."""
    def __init__(self, contacts, google=None):
        self.contacts = contacts
        self.google = google or Google(contacts)

    def dispatch(self, method, path, data=None):
        if data is not None and not isinstance(data, dict):
            raise ServiceError("invalid_body", "Expected JSON object")
        data = data or {}
        parsed = urlparse(path)
        prefix = "/api/contacts/v1"
        if not parsed.path.startswith(prefix + "/"):
            raise ServiceError("not_found", "Unknown API route", 404)
        route = parsed.path[len(prefix):].rstrip("/")
        if route == "/contacts":
            if method == "GET":
                return 200, self.contacts.list(parse_qs(parsed.query).get("q", [""])[0])
            if method == "POST":
                return 201, self.contacts.add(data)
        if route.startswith("/contacts/"):
            identity = route.split("/")[-1]
            if route != "/contacts/" + identity or not re.fullmatch(r"contact_[0-9a-f]{32}", identity):
                raise ServiceError("not_found", "Contact does not exist", 404)
            if method == "GET":
                return 200, self.contacts.get(identity)
            if method == "PUT":
                return 200, self.contacts.update(identity, data)
            if method == "DELETE":
                return 200, self.contacts.delete(identity, data)
        handlers = {("GET", "/google/status"): lambda: self.google.status(),
                    ("POST", "/google/configure"): lambda: self.google.configure(data),
                    ("POST", "/google/connect"): lambda: self.google.begin(),
                    ("POST", "/google/disconnect"): lambda: self.google.disconnect(data),
                    ("POST", "/google/preview"): lambda: self.google.preview(),
                    ("POST", "/imports/selected"): lambda: self.contacts.import_selected(data)}
        handler = handlers.get((method, route))
        if handler:
            return 200, handler()
        raise ServiceError("not_found", "Unknown API route or method", 404)


def serve(api, port=0):
    key = secrets.token_urlsafe(32)

    class Handler(BaseHTTPRequestHandler):
        def request(self):
            try:
                if not hmac.compare_digest(self.headers.get("X-Contacts-Key", ""), key):
                    raise ServiceError("unauthorized", "Local service key required", 401)
                if self.headers.get("Origin"):
                    raise ServiceError("origin_rejected", "Cross-origin browser requests are not allowed", 403)
                raw_length = self.headers.get("Content-Length", "0")
                if not raw_length.isdecimal() or int(raw_length) > 1048576:
                    raise ServiceError("invalid_body", "Body is invalid or too large")
                body = self.rfile.read(int(raw_length))
                data = json.loads(body) if body else {}
                if not isinstance(data, dict):
                    raise ServiceError("invalid_body", "Expected JSON object")
                status, payload = api.dispatch(self.command, self.path, data)
            except ServiceError as exc:
                status, payload = exc.status, {"error": {"code": exc.code, "message": str(exc)}}
            except (ValueError, TypeError):
                status, payload = 400, {"error": {"code": "invalid_json", "message": "Invalid JSON body"}}
            except Exception:
                status, payload = 503, {"error": {"code": "service_failed", "message": "Operation failed; inspect local service state"}}
            raw = canonical(payload).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(raw)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(raw)

        do_GET = do_POST = do_PUT = do_DELETE = request

        def log_message(self, *_args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    return server, key


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True, help="Private data directory; never use a repository")
    commands = parser.add_subparsers(dest="command", required=True)
    listing = commands.add_parser("list"); listing.add_argument("--query", default="")
    for command in ("add", "update"):
        child = commands.add_parser(command)
        child.add_argument("--name", required=True); child.add_argument("--phone", default=""); child.add_argument("--email", default="")
        if command == "update":
            child.add_argument("--id", required=True); child.add_argument("--expected-revision", required=True)
    child = commands.add_parser("delete")
    child.add_argument("--id", required=True); child.add_argument("--expected-revision", required=True); child.add_argument("--confirmed", action="store_true")
    commands.add_parser("google-status")
    child = commands.add_parser("google-configure"); child.add_argument("--client-json", required=True)
    commands.add_parser("google-connect")
    commands.add_parser("google-preview")
    child = commands.add_parser("google-disconnect"); child.add_argument("--confirmed", action="store_true")
    child = commands.add_parser("fixture-preview"); child.add_argument("--file", required=True)
    child = commands.add_parser("import-selected")
    child.add_argument("--preview-id", required=True); child.add_argument("--expected-revision", required=True)
    child.add_argument("--selected-id", action="append", required=True); child.add_argument("--duplicate-policy", choices=["skip"], required=True)
    child = commands.add_parser("serve"); child.add_argument("--port", type=int, default=0)
    args = parser.parse_args(argv)
    google = None
    try:
        contacts = Contacts(args.root)
        google = Google(contacts)
        command = args.command
        if command == "list":
            result = contacts.list(args.query)
        elif command == "add":
            result = contacts.add(vars(args))
        elif command == "update":
            result = contacts.update(args.id, dict(vars(args), expected_revision=args.expected_revision))
        elif command == "delete":
            result = contacts.delete(args.id, {"expected_revision": args.expected_revision, "confirmed": args.confirmed})
        elif command == "google-status":
            result = google.status()
        elif command == "google-configure":
            result = google.configure({"client_json_path": args.client_json})
        elif command == "google-connect":
            print(canonical(google.begin()), flush=True)
            # Keep the loopback listener alive while the user grants or denies consent.
            until = time.time() + 300
            while time.time() < until and contacts.private.read("google-pending.bin"):
                time.sleep(0.2)
            result = google.status()
        elif command == "google-disconnect":
            result = google.disconnect({"confirmed": args.confirmed})
        elif command == "google-preview":
            result = google.preview()
        elif command == "fixture-preview":
            payload = json.loads(Path(args.file).read_text(encoding="utf-8-sig"))
            result = contacts.preview_people(payload["connections"], "fixture")
        elif command == "import-selected":
            result = contacts.import_selected({"preview_id": args.preview_id, "expected_revision": args.expected_revision,
                     "selected_ids": args.selected_id, "duplicate_policy": args.duplicate_policy})
        else:
            server, key = serve(API(contacts, google), args.port)
            print(canonical({"url": f"http://127.0.0.1:{server.server_address[1]}", "key": key, "private": True}), flush=True)
            try:
                server.serve_forever()
            finally:
                server.server_close()
            return 0
        print(canonical(result))
        return 0
    except ServiceError as exc:
        print(canonical({"error": {"code": exc.code, "message": str(exc)}}))
        return 2
    except (OSError, sqlite3.Error, ValueError, KeyError):
        print(canonical({"error": {"code": "operation_failed", "message": "Operation failed; no success is claimed"}}))
        return 3
    finally:
        if google:
            google.close()


if __name__ == "__main__":
    raise SystemExit(main())
