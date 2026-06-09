# Usage Guide

This walks through every screen and every module, in the order a new user will encounter them. The first three sections are about *what* the buttons do; the last two are about *why* things are the way they are.

## 1. The four screens

| Screen | What it's for |
|--------|---------------|
| **Studio** | Run generations, see results inline |
| **Config Center** | Edit / add / delete module configs and API keys |
| **History** | Audit every call, replay payloads, re-run from a row |
| **Secrets** | Store reusable secret values (e.g. a `WEBHOOK_SIGNING_KEY`) once, reference by name in templates |

The left sidebar groups **Studio** as a parent with 4 children (Image / Voice / Music / Video) — the rest are flat.

## 2. First-run: paste your API key

You need a MiniMax API key from <https://platform.minimaxi.com/user-center/basic-information/interface-key>.

1. Open **Config Center**
2. Click on the **Image** row → **Edit**
3. In the **Common** tab, paste your key into the **API key** field
4. Click **Save**

Repeat for the other 3 modules if you plan to use them. Each module can have a different key (e.g. if you have separate accounts for image vs. video).

The "✓ saved" / "not set" tag in the top-right of the Edit modal reflects the state in the database. The key itself is **encrypted with Fernet** before it touches Postgres — only the running backend can decrypt it for an upstream call.

To clear a key: open Edit, hit the **Clear** button (it appears next to the field once a key is saved), then Save.

## 3. Studio — Image

1. Left sidebar → **Studio → Image**
2. Type a prompt
3. (Optional) tweak **Aspect ratio**, **Number of images**, **Optimizer**, **Watermark** in the Parameters pane
4. **Generate Image**

Results appear on the right as tiles. Click any image to view full-size; the file is also on disk at `uploads/image/YYYY/MM/DD/...`.

## 4. Studio — Voice

1. **Studio → Voice**
2. Pick a voice (the dropdown has ~20 built-in presets; the **Custom voice_id…** option reveals a text input for any voice returned by `POST /v1/audio/minimax/voices/list`)
3. Drag the **Speed / Volume / Pitch** sliders
4. Paste the text to synthesize into the **Prompt** field
5. **Generate Voice**

The result is a `.mp3` (or `.wav` / `.pcm` / `.flac` if you change **Format**) in the right pane with an inline audio player.

> Under the hood, `speech-2.6-turbo` returns a JSON envelope `{"data": {"audio": "<hex>"}}`; the backend decodes the hex and writes the binary to disk.

## 5. Studio — Music

1. **Studio → Music**
2. Type a music prompt (style / mood / instruments)
3. Fill in **Lyrics** (required by `music-2.0`):
   - For an instrumental track, leave the default placeholder `[Instrumental]`
   - For a song, use MiniMax's section markers: `[Intro]`, `[Verse]`, `[Chorus]`, `[Bridge]`, `[Outro]`
4. **Generate Music**

> Submitting empty lyrics returns `base_resp.code=2013`. The placeholder pre-fill is intentional so first-run "just works".

## 6. Studio — Video (T2V / I2V / FL2V)

The video module supports three sub-modes that hit the same endpoint, just with different required fields:

| Sub-mode | Required inputs | Common use |
|----------|----------------|------------|
| **T2V**  | `prompt` only | Pure text-to-video |
| **I2V**  | `prompt` + `first_frame_image` | Animate a still |
| **FL2V** | `prompt` + `first_frame_image` + `last_frame_image` | Interpolate between two frames |

1. **Studio → Video** (the parent entry)
2. Pick a sub-mode from the **Sub-mode** segmented control
3. The form updates:
   - **T2V**: just the prompt + common params
   - **I2V**: shows the **First frame image** field
   - **FL2V**: shows **First** and **Last frame** fields
4. **First frame image** accepts either:
   - A public **URL** (e.g. one you uploaded to a CDN), or
   - A local **file** — drag-and-drop or click to pick. Anything ≤ 20 MB; JPG / PNG / WebP
5. The **Model** dropdown filters to models that support your chosen sub-mode. Switching sub-modes auto-clamps the model to a valid one.
6. **Duration** and **Resolution** are constrained by the model's official matrix. The form auto-clamps to the highest valid value if your pick is out of range.
7. (Optional) toggle **Optimize prompt**, **Fast pretreatment** (T2V/I2V only), **AIGC watermark**
8. (Optional) supply a **Callback URL** if you want MiniMax to push status updates to your server instead of polling
9. **Generate Video** — the call is async; you'll see a result in 30-180s depending on duration × resolution

### Camera-control directives

You can embed motion directives in the prompt using bracket syntax, e.g.:

> A man picks up a book [推进, 上升], then reads [固定].

Available directives: `[左移]` `[右移]` `[左摇]` `[右摇]` `[推进]` `[拉远]` `[上升]` `[下降]` `[上摇]` `[下摇]` `[变焦推近]` `[变焦拉远]` `[晃动]` `[跟随]` `[固定]`. Multiple directives in one `[...]` are combined (up to 3 recommended).

## 7. Config Center

The Config Center manages **module-level** config: API key, base URL, endpoint path, model name, request template, response parser, default params. **Per-call** parameters (aspect ratio, voice, lyrics, etc.) live in the **Studio** screen.

### Common tab

- **API key** — paste, save, or clear
- **Base URL** — defaults to `https://api.minimaxi.com`
- **Endpoint path** — e.g. `/v1/image_generation`
- **Model** — pre-filled with the current flagship; you can override

### Advanced tab

- **Request template** — the JSON shape sent to the upstream. Edit `headers` and `body`. Placeholders like `{{api_key}}`, `{{prompt}}`, `{{voice_id}}` get substituted at call time (see [ARCHITECTURE.md](ARCHITECTURE.md#placeholder-syntax))
- **Response parser** — how to pull outputs out of the upstream's response
- **Default params** — pre-fill values shown in Studio when this config is selected

### What's a config, really?

A config is a row in the `api_configs` table. You can have **multiple configs per module** (e.g. one for `image-01` and one for an experimental model). The **Studio** screen lets you pick which one to use per call.

> Pre-flight connectivity check: hit the **Test** button (⚡) on any config row to send a tiny dry-run request and confirm auth + endpoint reachability.

## 8. History

Every successful or failed generation lands in `generation_history` with:

- Module + config_id
- Prompt (truncated to 1 KB)
- Full request payload (truncated to depth 6 / list 20 for legibility)
- Full response payload
- List of output files (with relative URL `/api/media/...`)
- Status, error message, duration

Click any row to expand. To free disk, **Delete** removes the row but **leaves the file on disk** (you can prune `uploads/` manually if you want).

## 9. Secrets

If you find yourself repeating a value (e.g. a webhook signing key, an internal proxy URL) in many configs, put it in **Secrets** once, then reference it in templates with `{{secrets.WEBHOOK_SIGNING_KEY}}` syntax (the template renderer resolves the `secrets.*` prefix against the secrets table).

This is a power-user feature; you can ignore it for first-run usage.

## 10. Tips & gotchas

- **Hard-reload after a backend change** — `index.html` is served `Cache-Control: no-store` but the browser's service worker / DevTools "disable cache" can still cause confusion. `Cmd+Shift+R` is the safest.
- **Quota issues** — `usage limit exceeded (3/3 used)` means your MiniMax plan's daily allowance is tapped. Resets at 00:00 UTC+8.
- **The same prompt can succeed with one model and fail with another.** Use **History** to compare what each call actually sent.
- **Lost `.master_key`?** All stored API keys become unreadable. Back it up.
