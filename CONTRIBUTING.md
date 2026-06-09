# Contributing

Thanks for your interest in MiniMax Tool! This is a small project; the rules below exist to keep PRs easy to review.

## Local dev loop

Two terminals, both rooted at the project root.

```bash
# Terminal 1 — backend (auto-reload on file change)
cd backend
uv sync
uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 9060

# Terminal 2 — frontend (HMR)
cd frontend
npm install
npm run dev    # opens on :5173, proxies /api → :9060
```

When you're ready to verify the production layout (single-port), build the frontend and let FastAPI serve it:

```bash
cd frontend && npm run build    # writes to ../backend/static/
cd ..                            # back to project root
# backend already serving from there
```

## Before you push a PR

- [ ] Smoke test passes: `uv run python scripts/smoke.py`
- [ ] Frontend builds: `cd frontend && npm run build`
- [ ] If you touched the video template or response parsers, also run:
      `uv run python backend/scripts/check_video_template_render.py`
- [ ] Update `CHANGELOG.md` under the `Unreleased` section
- [ ] If you added a config field, update `docs/USAGE.md` and the seed in `backend/app/models.py`

## Code style

- **Python**: 4-space indent, type hints on public functions, f-strings, no print-debug (use `logger = logging.getLogger(__name__)`).
- **TypeScript / React**: function components + hooks, no class components; prefer named exports for shared utilities.
- **CSS**: edit `frontend/src/styles/index.css` only. No CSS-in-JS, no preprocessor, no Tailwind. Use the existing CSS variables (`--accent`, `--bg-soft`, etc.) before introducing new ones.
- **No component libraries** (antd / mui / shadcn are deliberately absent). If you need a new primitive, hand-roll it in the same file or in the stylesheet.

## Commit messages

We follow the [Conventional Commits](https://www.conventionalcommits.org/) spec, e.g.:

```
feat(video): add FL2V last-frame image field
fix(generator): coerce fast_pretreatment to bool in post-hook
docs(README): add docker-compose quick start
chore(deps): bump vite to 4.5.14
```

## Project layout conventions

- One-shot fix scripts go in `backend/scripts/`. They take no args and print a clear before/after diff.
- Daily-use dev scripts go in `scripts/` (root).
- A new module requires: `SEED_CONFIGS` entry + form in `configForms/` + entry in `App.tsx` + smoke-test assertion.
- A new response parser requires: a branch in `services/generator.py` + a doc paragraph in `docs/ARCHITECTURE.md` under "Response parsers".

## Reporting bugs

Open a GitHub issue. Include:

- The exact URL + payload of the failing call (from History → "Detail" panel)
- The relevant `upstream_body` snippet from the response
- Your `MiniMax Tool` version (sidebar footer) and Python/Node versions

## License

By contributing, you agree that your contributions will be licensed under the project's [MIT License](LICENSE).
