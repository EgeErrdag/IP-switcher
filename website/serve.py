"""Tanıtım sitesini localhost'ta açar: python website/serve.py"""
import functools
import http.server
import os
import socketserver
import sys
import webbrowser

ROOT = os.path.dirname(os.path.abspath(__file__))
args = [a for a in sys.argv[1:] if a.isdigit()]
PORT = int(args[0]) if args else 8000

handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=ROOT)

for port in range(PORT, PORT + 20):
    try:
        httpd = socketserver.TCPServer(("127.0.0.1", port), handler)
        break
    except OSError:
        continue
else:
    sys.exit(f"{PORT}-{PORT + 19} arasında boş port bulunamadı.")

url = f"http://localhost:{port}"
print(f"Site açık: {url}  (durdurmak için Ctrl+C)")
if "--no-browser" not in sys.argv:
    webbrowser.open(url)
with httpd:
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nKapatıldı.")
