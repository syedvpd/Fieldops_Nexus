# M12 camera scanner - real-browser check (not part of pytest)

Drives real Chrome through the live scan page. The camera API is real: Chrome's fake capture device plays an MJPEG
video of the actual label QR rendered by the app (`--use-file-for-fake-video-capture`). It proves camera permission ->
live video -> QR detection -> server resolution -> asset page, and the failure paths. It does NOT replace a test with
a phone's physical camera.

1. Local scratch database (never Supabase): `createdb fieldops_e2e`, `DJANGO_SETTINGS_MODULE=config.settings.dev`,
   `python manage.py migrate`, then `python tests/e2e_camera/seed.py` (writes `e2e_seed.json`, creates Alpha / Beta orgs,
   technician, site-scoped user and QR labels).
2. `python manage.py runserver 8010`
3. In `tests/e2e_camera/vid/` (git-ignored): copy `e2e_seed.json`, run `python ../mkvideo.py` (writes the `*.mjpeg` files).
4. `npm i playwright-core` here, then `node run.js` (set `BASE` to test another host; Chrome path is in `run.js`).
