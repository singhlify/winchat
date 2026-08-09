#!/usr/bin/env bash
# What is ACTUALLY configured in Supabase Auth, checked rather than remembered.
#
#   ./scripts/verify_supabase.sh
#
# Reads a Supabase Personal Access Token from backend/.env (gitignored) and asks the
# Management API for this project's auth configuration. Read-only: it issues one GET and
# changes nothing.
#
# Why this exists. Auth setup is a dozen toggles across several dashboard pages, and the
# only honest way to know the state is to read it back — a checklist someone ticked off is
# a record of intent, not of configuration. The public `/auth/v1/settings` endpoint shows
# providers and little else; site URL, the redirect allowlist and password rules are only
# visible here.
#
# To get a token: https://supabase.com/dashboard/account/tokens -> Generate new token.
# Then add to backend/.env (never committed):
#     SUPABASE_ACCESS_TOKEN=sbp_...
#     SUPABASE_PROJECT_REF=<your project ref>
#
# The token grants full management access to your projects, so treat it like a password:
# keep it in .env, never paste it into a chat, a ticket or a screenshot.

set -uo pipefail
cd "$(dirname "$0")/.." || exit 2

ENV_FILE="backend/.env"
[ -f "$ENV_FILE" ] || { echo "missing $ENV_FILE"; exit 2; }

TOKEN=$(grep -E '^SUPABASE_ACCESS_TOKEN=' "$ENV_FILE" | cut -d= -f2- | tr -d '"'"'"' \r')
REF=$(grep -E '^SUPABASE_PROJECT_REF=' "$ENV_FILE" | cut -d= -f2- | tr -d '"'"'"' \r')

# Fall back to deriving the ref from DATABASE_URL, so only the token has to be added.
if [ -z "${REF:-}" ]; then
  REF=$(grep -E '^DATABASE_URL=' "$ENV_FILE" | sed -E 's#.*://postgres\.([a-z0-9]+):.*#\1#')
fi

if [ -z "${TOKEN:-}" ]; then
  cat <<'EOF'
No SUPABASE_ACCESS_TOKEN in backend/.env.

  1. https://supabase.com/dashboard/account/tokens -> Generate new token
  2. Add to backend/.env:   SUPABASE_ACCESS_TOKEN=sbp_...

backend/.env is gitignored and the pre-commit scanner checks for leaks, so the token
stays on this machine.
EOF
  exit 2
fi

RESPONSE=$(curl -sS -m 30 -H "Authorization: Bearer $TOKEN" \
  "https://api.supabase.com/v1/projects/${REF}/config/auth")

if echo "$RESPONSE" | grep -q '"message"'; then
  # Never echo the response wholesale — an error body can contain request context.
  echo "Management API rejected the request. Check the token is valid and has access to ${REF}."
  exit 1
fi

SITE_URL="https://winchat.vercel.app" \
python3 - "$RESPONSE" <<'PY'
import json, os, sys

cfg = json.loads(sys.argv[1])
site = os.environ["SITE_URL"]

def show(ok, label, detail=""):
    print(f"  {'PASS' if ok else 'TODO'}  {label}" + (f"  ({detail})" if detail else ""))

print("\n  PROVIDERS")
show(cfg.get("external_email_enabled"), "email/password")
show(cfg.get("external_github_enabled"), "GitHub")
show(cfg.get("external_google_enabled"), "Google")

print("\n  SIGN-UP FLOW")
show(not cfg.get("disable_signup"), "new sign-ups allowed")
# autoconfirm true == "Confirm email" OFF. Wanted here because the built-in mailer allows
# only a couple of messages an hour, so confirmation makes sign-up look broken.
show(cfg.get("mailer_autoconfirm"), "email confirmation off",
     "on = sign-up waits for an email that may never arrive")
show(not cfg.get("external_anonymous_users_enabled"), "anonymous sign-ins off",
     "this is Supabase's own feature, not our guest mode")

print("\n  REDIRECTS  (a sign-in that returns to the wrong origin is a dead end)")
show(cfg.get("site_url") == site, "site URL", cfg.get("site_url") or "unset")
allow = [u for u in (cfg.get("uri_allow_list") or "").split(",") if u]
for needed in (f"{site}/auth/callback", f"{site}/auth/reset"):
    show(any(needed == u or u.endswith("/**") and needed.startswith(u[:-3]) for u in allow), needed)
show(bool(allow), "allowlist is non-empty",
     f"{len(allow)} entr{'y' if len(allow)==1 else 'ies'}")

print("\n  PASSWORDS")
length = cfg.get("password_min_length")
show(isinstance(length, int) and length >= 8, "minimum length >= 8", str(length))
# Pro-plan only; reported so the gap is visible rather than forgotten.
show(cfg.get("password_hibp_enabled"), "leaked-password check", "requires Pro; expected TODO on Free")
print()
PY
