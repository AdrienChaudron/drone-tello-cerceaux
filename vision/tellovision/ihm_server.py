"""
ihm_server.py : petit serveur HTTP de NOTRE PC pour l'IHM web (bibliotheque standard uniquement).

    GET /video.mjpeg  : video annotee par le CNN, en MJPEG (suite de JPEG ; une balise <img> suffit a l'afficher)
    GET /events       : etat de la vision en continu (Server-Sent Events, un message JSON par image traitee)
    GET /health       : {"status": "ok"}

La page web (dossier web/ du PC de controle) lit la telemetrie du drone sur le serveur Node du collegue,
et la vision directement ici : la video ne transite ni par le broker MQTT ni par son serveur.

Usage (dans vision_node.py) :
    srv = VisionWebServer(port=8080); srv.start()
    srv.publish_frame(jpeg_bytes); srv.publish_state(dict)
"""

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

BOUNDARY = "trame"


class VisionWebServer:
    def __init__(self, host="0.0.0.0", port=8080):
        self.host, self.port = host, port
        self._cond = threading.Condition()
        self._jpeg, self._state = None, None
        self._frame_id = self._state_id = 0          # compteurs : chaque client attend le suivant
        self._httpd = None

    # ---- appele par vision_node (fil principal) ----
    def publish_frame(self, jpeg: bytes):
        with self._cond:
            self._jpeg = jpeg
            self._frame_id += 1
            self._cond.notify_all()

    def publish_state(self, state: dict):
        with self._cond:
            self._state = json.dumps(state)
            self._state_id += 1
            self._cond.notify_all()

    def _wait(self, attr_id, last, timeout=2.0):
        """Attend une donnee plus recente que `last`. Renvoie (nouvel id, donnee) ou (last, None)."""
        with self._cond:
            self._cond.wait_for(lambda: getattr(self, attr_id) != last, timeout=timeout)
            cur = getattr(self, attr_id)
            if cur == last:
                return last, None
            return cur, (self._jpeg if attr_id == "_frame_id" else self._state)

    # ---- serveur ----
    def start(self):
        server = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):            # pas de ligne par requete dans le terminal
                pass

            def _headers(self, ctype):
                self.send_response(200)
                self.send_header("Content-Type", ctype)
                self.send_header("Cache-Control", "no-cache, no-store")
                self.send_header("Access-Control-Allow-Origin", "*")   # page servie par un autre PC / port
                self.send_header("Connection", "keep-alive")
                self.end_headers()

            def do_GET(self):
                path = self.path.split("?")[0]
                try:
                    if path == "/video.mjpeg":
                        self._headers(f"multipart/x-mixed-replace; boundary={BOUNDARY}")
                        last = -1
                        while True:
                            last, jpg = server._wait("_frame_id", last)
                            if jpg is None:
                                continue                       # pas d'image depuis 2 s : on attend encore
                            self.wfile.write(f"--{BOUNDARY}\r\nContent-Type: image/jpeg\r\n"
                                             f"Content-Length: {len(jpg)}\r\n\r\n".encode())
                            self.wfile.write(jpg + b"\r\n")
                            self.wfile.flush()
                    elif path == "/events":
                        self._headers("text/event-stream")
                        last = -1
                        while True:
                            last, st = server._wait("_state_id", last)
                            msg = f"data: {st}\n\n" if st is not None else ": attente\n\n"   # commentaire = garde la connexion
                            self.wfile.write(msg.encode())
                            self.wfile.flush()
                    elif path == "/health":
                        body = b'{"status": "ok"}'
                        self._headers("application/json")
                        self.wfile.write(body)
                    else:
                        self.send_error(404)
                except (BrokenPipeError, ConnectionResetError):
                    pass                                       # onglet ferme : fin normale

        self._httpd = ThreadingHTTPServer((self.host, self.port), Handler)
        self._httpd.daemon_threads = True
        threading.Thread(target=self._httpd.serve_forever, daemon=True).start()
        print(f"[ihm] video : http://{self.host}:{self.port}/video.mjpeg   etat : http://{self.host}:{self.port}/events")

    def stop(self):
        if self._httpd is not None:
            self._httpd.shutdown()
