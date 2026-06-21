# MiniMax Tool

> A local web UI for the [MiniMax](https://platform.minimaxi.com) AI platform — **image / voice / music / video** generation in one place, with your **API keys encrypted at rest**.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.13](https://img.shields.io/badge/python-3.13-blue.svg)](https://www.python.org/downloads/)
[![React 18](https://img.shields.io/badge/react-18-61dafb.svg)](https://react.dev)
[![FastAPI](https://img.shields.io/badge/fastapi-0.115-009688.svg)](https://fastapi.tiangolo.com)

Calling MiniMax's generation APIs from a terminal works, but the moment you want to A/B compare, remember which model worked, replay a call with a small tweak, or keep your keys out of shell history — you end up writing a tiny UI. That's what this is. One port, one database, and your keys are Fernet-encrypted before they touch disk.

---

## 1. Install

**Prerequisites**: Docker Engine 20.10+ (with the `docker compose` v2 plugin), and a PostgreSQL 16+ instance you can reach.

```bash
git clone <repo-url> minimax-tool
cd minimax-tool
cp config/database.yaml.example config/database.yaml
$EDITOR config/database.yaml     # set host / port / user / password / name
touch .master_key && chmod 600 .master_key
docker compose up -d --build
```

Verify it's up:

```bash
docker compose ps                  # STATUS = healthy
curl http://localhost:9060/api/health
# → {"status":"ok","db":true,"version":"0.2.0"}
```

Open <http://localhost:9060>. The app auto-creates the database and seeds 4 default module configs on first run.

**No Docker?** Run the backend and frontend separately — see [docs/DEPLOY.md § Local development](docs/DEPLOY.md#local-development).

**Production / hardening / backups / secret rotation** → [docs/DEPLOY.md](docs/DEPLOY.md) and [docs/SECURITY.md](docs/SECURITY.md).

---

## 2. Configure

The first thing to do in the UI is paste your MiniMax API key for each module you want to use. Keys are Fernet-encrypted into the database the moment you save — after that, the plaintext lives only in process memory for the duration of a request.

1. Open <http://localhost:9060>.
2. Left sidebar → **Config Center**.
3. Click **Image** (or Voice / Music / Video) → paste your API key → **Save**.
4. The status badge turns green. You're ready to generate.

Other things you can configure in **Config Center**:

- **Model** — switch the flagship (e.g. video: `MiniMax-Hailuo-02` → `MiniMax-Hailuo-2.3-Fast`).
- **Base URL** — point at a proxy or alternate region.
- **Request template** — JSON body sent to MiniMax (placeholders like `{{prompt}}`, `{{api_key}}`).
- **Default params** — values the form pre-fills on first load.
- Edit each module's model, endpoint, template and defaults from one place.
- **Test** button — sends a no-op request to verify connectivity without burning quota.

Reusable values shared across templates (e.g. a `WEBHOOK_SIGNING_KEY`) live in **Secrets** (sidebar) and are referenced as `{{secrets.NAME}}` in any template body.

---

## 3. Use

> Pick the scenario that sounds like you. Each one is end-to-end: open the app, do the steps, see the result.

### 🎨 Generate images

1. **Studio → Image**.
2. Type a prompt (e.g. *"a tabby cat wearing a spacesuit, retro sci-fi poster style"*).
3. Pick **Aspect ratio** (1:1, 16:9, 9:16, …) and **Number of images** (1-4).
4. Hit **Generate Image** — variants appear as tiles.
5. Click a tile for full-size, download from the same panel. Files are also saved under `uploads/image/YYYY/MM/DD/`.

Want to iterate? Tweak the prompt, re-run, then open **History** (sidebar) to inspect prior calls and their redacted request/response payloads.

### 🗣 Generate voice

1. **Studio → Voice**.
2. Pick a voice (20+ built-in presets grouped by language; pick **Custom voice_id…** to enter any voice from the MiniMax voices API).
3. Drag the **Speed / Volume / Pitch** sliders.
4. Paste your text into **Prompt**.
5. **Generate Voice** — the result plays inline; download as `.mp3` / `.wav` / `.pcm` / `.flac`.

### 🎵 Generate music

1. **Studio → Music**.
2. Type a **music prompt** describing style / mood / instruments.
3. Fill in **Lyrics**. The default `[Instrumental]` is fine for a backing track. For a song, use section markers:
   ```
   [Intro]
   (instrumental)

   [Verse]
   City lights are calling out my name

   [Chorus]
   We are the fire, we are the flame
   ```
4. **Generate Music** — typical 30-60s for a short song, up to 4 min.

> Got `base_resp.code=2013`? You submitted empty lyrics. Either fill them in or use the `[Instrumental]` placeholder.

### 🎬 Generate video

Video calls are **async** — expect 30-180s per call.

**Three sub-modes**, picked from the **Sub-mode** dropdown at the top of the Video form:

- **T2V** (text-only) — cheapest, just write a prompt. Good for "what would this look like as video?" ideation.
- **I2V** (image → video) — upload a **First frame image** (URL or drag-drop, ≤ 20 MB, JPG/PNG/WebP), add a motion prompt.
- **FL2V** (first + last frame) — supply **both** a first and a last frame image, the model interpolates the in-between. Only `MiniMax-Hailuo-02` supports this.

You can embed **camera-control directives** in the prompt in `[…]` brackets, e.g.

> A man picks up a book [推进, 上升], then reads [固定].

Pick **Duration** (6s or 10s) and **Resolution** — the form auto-clamps to what your chosen model supports.

### 🧪 Compare model settings

Record the current model in History, change the module model in Config Center,
then run the same prompt again. History keeps both results for comparison.

Module-by-module parameter reference → [docs/USAGE.md](docs/USAGE.md).

---

## Contributing

PRs welcome. See [CONTRIBUTING.md](CONTRIBUTING.md) for the local dev loop, the smoke test, and the change-log convention.

## License

[MIT](LICENSE) © 2026 MiniMax Tool contributors.
