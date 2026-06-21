# Security

This document covers how secrets are protected, what to back up, and the checklist to run before going public with this repo.

## Threat model

We assume the operator:

- runs the app on a single host (or a single Docker container) under their control
- is the only person with shell access to that host
- wants to keep API keys out of source control, shell history, and accidental screenshots

We explicitly **do not** protect against:

- a hostile actor with shell access to the host (they can read `.master_key` and the DB)
- a hostile authenticated user (the built-in Basic auth is single-user, not RBAC)
- a leaked database dump that also includes `.master_key` (the encryption is moot)

If you need multi-user or remote access, put the app behind an authenticated reverse proxy (e.g. Caddy + oauth2-proxy) **before** exposing port 9060.

## How secrets are stored

| Asset | Where | How |
|-------|-------|-----|
| MiniMax API keys | `key_providers.api_key_encrypted` | Fernet ciphertext (AES-128-CBC + HMAC-SHA256) |
| App-level secrets | `app_secrets.value_encrypted` | Fernet ciphertext |
| Master key | `.master_key` (mode `0600`) at the project root | URL-safe base64-encoded 32-byte key |
| Master key (alt) | `MASTER_KEY` env var | Same format; takes precedence over the file |

Successful request history is recursively redacted before it is written to
PostgreSQL. Authorization, cookies, passwords, tokens and API-key-shaped fields
are replaced with `[REDACTED]`; startup also cleans rows written by older releases.

### Master key auto-generation

On first run, if neither `.master_key` nor `MASTER_KEY` is set, the backend generates a fresh Fernet key, writes it to `.master_key`, and refuses to log the value. This is loud — if you copy `.master_key` somewhere safe right after, you'll never be locked out.

### Encryption is symmetric

A single master key encrypts all stored secrets. If you lose it, the database entries are unrecoverable. **There is no "reset password" flow.**

## Backups

You need **both** of these to recover from a total disk loss:

1. **`.master_key`** — without it, the DB is opaque
2. **PostgreSQL dump** of the `minimax_tool` database
3. **`config/database.yaml`** — so a fresh host knows how to reach the DB
   (only required if the password is baked in; if you use
   `${DB_PASSWORD}` in the YAML, the env var is part of your secret
   manager's restore process)

For Docker (with an external Postgres reachable from the host):

```bash
# Read host/port/user/db straight from the YAML so the backup
# script and the app can never disagree about where the DB lives.
DB_HOST=$(yq '.database.host' config/database.yaml)
DB_PORT=$(yq '.database.port' config/database.yaml)
DB_USER=$(yq '.database.user' config/database.yaml)
DB_NAME=$(yq '.database.name' config/database.yaml)

pg_dump -h "$DB_HOST" -p "${DB_PORT:-5432}" -U "$DB_USER" "$DB_NAME" > backup-$(date +%F).sql
cp .master_key master-key.bak                        # separate, encrypted location
cp config/database.yaml config-database.bak          # same or different — your call
```

For local dev (where the YAML's host is `localhost`):

```bash
pg_dump -h localhost -U postgres minimax_tool > backup-$(date +%F).sql
cp .master_key master-key.bak
```

Store the artifacts in **different** places (e.g. DB dump in S3, master
key in 1Password). If they're in the same tarball and that tarball
leaks, an attacker has everything they need.

## Configuration secrets

The application reads its database connection from
`config/database.yaml` (no `.env` is used). To keep the password out
of the file itself, reference it as a `${DB_PASSWORD}` placeholder and
export the variable in the shell, or use a Docker secret mounted at
`/run/secrets/db_password`. The YAML example file shows all three
patterns.

## Master-key rotation

Rotating the master key is a 5-step process. The brief version:

1. Generate a new key: `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`
2. Start a temporary second instance of the app pointed at the **old** master key. Re-decrypt and re-encrypt every row under the new key.
3. Update the `MASTER_KEY` env var (or replace `.master_key`) on all running instances.
4. Restart everything.
5. Destroy the temporary instance.

The codebase does **not** ship an automated rotation tool — it's a one-off `for row in api_configs: decrypt with old, encrypt with new, update`. A future improvement would be to add a `scripts/rotate_master_key.py` helper.

## Pre-public checklist

Before pushing to a public repo (GitHub, GitLab, Gitea…), verify:

- [ ] `.master_key` is **not** tracked (`git status` shows it ignored)
- [ ] `.env` is **not** tracked (and `.env.example` is **not** in the repo)
- [ ] `config/database.yaml` is **not** tracked (only `database.yaml.example` is)
- [ ] `uploads/` is **not** tracked (or, if you do want examples committed, scrub them first)
- [ ] No real API keys in any committed file — run `git grep -E 'sk-[a-z0-9]{20,}'` to be sure
- [ ] No production passwords in any committed file (the YAML example uses `${DB_PASSWORD}`; grep for plain passwords just in case)
- [ ] `LICENSE` is in place
- [ ] README and SECURITY link to each other

You can run most of the above in one go:

```bash
# 1. Confirm .master_key, .env, config/database.yaml, uploads/ are ignored
git check-ignore -v .master_key .env config/database.yaml uploads/ 2>&1

# 2. Hunt for accidental MiniMax key prefixes
git grep -nE 'sk-(cp-)?[a-zA-Z0-9]{20,}' || echo "no plaintext keys found"

# 3. Hunt for accidental password-like patterns
git grep -nE '(password|passwd|pwd)\s*[:=]\s*[\x27"][^\x27"]{6,}' || echo "no plaintext passwords found"
```

## Reporting a vulnerability

Open a GitHub issue with the `security` label, or email the maintainer directly (see repo description). Please don't disclose publicly until we've shipped a fix.
