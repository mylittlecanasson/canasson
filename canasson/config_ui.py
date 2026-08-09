"""Dashboard web de configuration — stdlib uniquement.

Sert le formulaire `config.html` et les endpoints JSON qui lisent/écrivent la
configuration sauvegardée dans `data/config.json`. Aucune dépendance externe :
`ThreadingHTTPServer` + `BaseHTTPRequestHandler`.

Routes :
- GET  /                  → formulaire (config.html)
- GET  /api/spec          → description des réglages (labels, bornes, choix)
- GET  /api/config        → réglages effectifs
- POST /api/config        → enregistre (400 + erreurs si invalide)
- POST /api/config/reset  → restaure les défauts (supprime le fichier)
"""
from __future__ import annotations

import json
import logging
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

from canasson import config

logger = logging.getLogger("canasson.config_ui")


class _Handler(BaseHTTPRequestHandler):
    def _send(self, code: int, body: bytes, ctype: str = "application/json") -> None:
        self.send_response(code)
        self.send_header("Content-Type", f"{ctype}; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _json(self, code: int, payload: dict) -> None:
        self._send(code, json.dumps(payload, ensure_ascii=False).encode("utf-8"))

    def _read_json(self) -> dict | None:
        length = int(self.headers.get("Content-Length", 0) or 0)
        raw = self.rfile.read(length).decode("utf-8") if length else "{}"
        try:
            body = json.loads(raw)
        except ValueError as exc:
            self._json(400, {"errors": [f"JSON invalide : {exc}"]})
            return None
        if not isinstance(body, dict):
            self._json(400, {"errors": ["Le corps doit être un objet JSON."]})
            return None
        return body

    def do_GET(self) -> None:  # noqa: N802 (API http.server)
        path = urlparse(self.path).path
        if path == "/api/spec":
            self._json(200, {"spec": config.spec_payload()})
        elif path == "/api/config":
            self._json(200, {"settings": config.current_settings()})
        elif path in ("/", "/index.html"):
            template = config.TEMPLATES_DIR / "config.html"
            self._send(200, template.read_text(encoding="utf-8").encode("utf-8"), "text/html")
        else:
            self._json(404, {"error": "introuvable"})

    def do_POST(self) -> None:  # noqa: N802 (API http.server)
        path = urlparse(self.path).path
        if path == "/api/config":
            payload = self._read_json()
            if payload is None:
                return
            try:
                saved = config.save_settings(payload)
            except ValueError as exc:
                self._json(400, {"errors": [str(exc)]})
                return
            self._json(200, {"saved": saved})
        elif path == "/api/config/reset":
            config.SETTINGS_FILE.unlink(missing_ok=True)
            self._json(200, {"settings": config.current_settings()})
        else:
            self._json(404, {"error": "introuvable"})

    def log_message(self, fmt: str, *args) -> None:
        logger.info("%s %s", self.address_string(), fmt % args)


def run(host: str = "0.0.0.0", port: int = 8090) -> None:
    """Démarre le dashboard (bloquant, Ctrl+C pour arrêter)."""
    config.ensure_dirs()
    server = ThreadingHTTPServer((host, port), _Handler)
    logger.info("Dashboard de configuration : http://%s:%d (Ctrl+C pour arrêter).", host, port)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        logger.info("Arrêt du dashboard.")
        server.server_close()
