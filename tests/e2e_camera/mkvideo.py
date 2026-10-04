# ruff: noqa  (stand-alone helper for the real-browser camera check, see README.md)
import io, json, django
django.setup()
import segno
from PIL import Image
from apps.identification import services as idn
seed = json.load(open("e2e_seed.json"))
BASE = "http://localhost:8010"
def frame_bytes(text):
    buf = io.BytesIO(); segno.make(text, error="m").save(buf, kind="png", scale=8, border=4); buf.seek(0)
    qr = Image.open(buf).convert("RGB")
    canvas = Image.new("RGB", (640, 480), "white")
    canvas.paste(qr.resize((360, 360)), (140, 60))
    out = io.BytesIO(); canvas.save(out, "JPEG", quality=92); return out.getvalue()
def write(name, text):
    data = frame_bytes(text)
    open(f"{name}.mjpeg", "wb").write(data * 45)
write("valid_alpha", idn.scan_url(seed["a"]["token"], BASE))
write("valid_other_site", idn.scan_url(seed["a"]["token_other_site"], BASE))
write("cross_tenant_beta", idn.scan_url(seed["b"]["token"], BASE))
write("invalid_text", "hello this is not a fieldops label")
write("unknown_token", idn.scan_url("Zk3pQ9vLm2XcRt7YbN4HwA", BASE))
print("videos ok", idn.scan_url(seed["a"]["token"], BASE)[:50])
