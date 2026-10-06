"""
Yerel geliştirme sunucusu.

Site temiz adresler kullanır (/makro, /dolabim, /tarif/mercimek-corbasi ...).
"python -m http.server" bu adresleri tanımadığı için sayfa yenilenince 404 verir.
Bu dosya, Vercel'deki vercel.json kurallarının yerel karşılığıdır:
uygulama adreslerini frontend/index.html'e yönlendirir, diğer dosyaları olduğu gibi sunar.

Kullanım:
    python serve.py          # http://localhost:8137
    python serve.py 9000     # farklı port
"""

from __future__ import annotations

import http.server
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
APP_PAGE = "/frontend/index.html"

# vercel.json "rewrites" ile aynı adresler
APP_ROUTES = re.compile(r"^/(?:|dolabim|makro|hakkinda|iletisim|tarif/[^/]+)$")
# vercel.json "redirects": eski /frontend/ adresi ana sayfaya yönlenir
OLD_PATHS = {"/frontend", "/frontend/", "/frontend/index.html"}


class Handler(http.server.SimpleHTTPRequestHandler):
    """Uygulama adreslerini tek sayfaya yönlendiren statik dosya sunucusu."""

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def _rewrite(self) -> bool:
        """Gerekirse yönlendirme yapar. Yanıt gönderildiyse True döner."""
        path, _, query = self.path.partition("?")
        if path in OLD_PATHS:
            self.send_response(301)
            self.send_header("Location", "/" + (f"?{query}" if query else ""))
            self.end_headers()
            return True
        if APP_ROUTES.match(path):
            self.path = APP_PAGE
        return False

    def do_GET(self) -> None:
        if not self._rewrite():
            super().do_GET()

    def do_HEAD(self) -> None:
        if not self._rewrite():
            super().do_HEAD()


def main() -> None:
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8137
    server = http.server.ThreadingHTTPServer(("127.0.0.1", port), Handler)
    print(f"sofra defteri yerelde çalışıyor: http://localhost:{port}  (durdurmak için Ctrl+C)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nSunucu durduruldu.")


if __name__ == "__main__":
    main()
