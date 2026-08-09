#!/usr/bin/env bash
# Is there a credential anywhere in this repository, including its history?
#
#   ./scripts/scan_secrets.sh            # working tree + full history
#   ./scripts/scan_secrets.sh --staged   # only what is about to be committed (used by the hook)
#
# Two layers, and the second is not redundant:
#
#   1. gitleaks, when installed, ~170 provider rules plus Shannon-entropy detection, which
#      catches high-randomness strings no fixed pattern anticipates (a Supabase service-role
#      JWT, a random signing secret). Measured here: it caught a 45-character vendor-less
#      secret that layer 2 missed completely. Config in `.gitleaks.toml`.
#   2. The built-in rules below, always, because a scanner that has to be installed first
#      is a scanner that is absent on the machine where it matters. This keeps the check
#      meaningful on a fresh clone or a teammate's laptop.
#
# Both must pass. Install the better layer with:
#   V=$(curl -s https://api.github.com/repos/gitleaks/gitleaks/releases/latest \
#       | grep -oP '"tag_name":\s*"\K[^"]+'); mkdir -p ~/.local/bin
#   curl -sL "https://github.com/gitleaks/gitleaks/releases/download/${V}/gitleaks_${V#v}_linux_x64.tar.gz" \
#       | tar -xz -C ~/.local/bin gitleaks
#
# Both layers match on the SHAPE of a credential, not on variable names. `GROQ_API_KEY=` in
# an example file is documentation; `GROQ_API_KEY=gsk_live...` is an incident. Grepping for
# the name flags the first and misses the second, which is exactly backwards.
#
# Neither replaces GitHub's server-side push protection, and it does not replace these: push
# protection does not cover Postgres connection strings, Supabase secret keys or self-signed
# JWT secrets, most of this project's real risk surface, and a pusher can bypass it. Local
# hooks are bypassable too (`--no-verify`), which is why CI runs this as well. Layers, not a gate.
#
# Exit codes: 0 clean, 1 findings, 2 usage error.

set -uo pipefail
cd "$(dirname "$0")/.." || exit 2

# Each rule is  name|regex . Anchored on the token shape so example files stay quiet.
RULES=(
  "Groq API key|gsk_[A-Za-z0-9]{20,}"
  "OpenAI-style key|sk-[A-Za-z0-9_-]{20,}"
  "Cohere API key|[A-Za-z0-9]{40}\.co-[A-Za-z0-9]{10,}"
  "AWS access key|AKIA[0-9A-Z]{16}"
  "Google API key|AIza[0-9A-Za-z_-]{35}"
  "Slack token|xox[baprs]-[0-9A-Za-z-]{10,}"
  "GitHub token|gh[pousr]_[A-Za-z0-9]{36,}"
  "JWT (3 segments)|eyJ[A-Za-z0-9_-]{10,}\.eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}"
  "Postgres URL with password|postgres(ql)?://[^ \"':]+:[^ \"'@]{6,}@"
  "Private key block|-----BEGIN [A-Z ]*PRIVATE KEY-----"
)

# Files that legitimately contain credential-shaped strings. Keep this list short and
# justified. Every entry is a place a real leak could hide.
EXCLUDE='^(.*\.lock|.*lock\.json|.*lock\.yaml|scripts/scan_secrets\.sh|\.gitleaks\.toml|\.githooks/pre-commit)$'

mode="${1:-all}"
findings=0

# ~/.local/bin is on PATH in a login shell but not always inside a git hook's environment.
command -v gitleaks >/dev/null 2>&1 || PATH="$HOME/.local/bin:$PATH"

run_gitleaks() {
  local scope="$1" # staged | history
  if ! command -v gitleaks >/dev/null 2>&1; then
    echo "  gitleaks not installed, running built-in rules only (see the header to install)."
    return 0
  fi

  # -v prints WHERE each finding is (file, line, rule, entropy); --redact keeps the value
  # itself out of the output. Location without exposure.
  local args=(git --no-banner --redact -v -c .gitleaks.toml)
  if [ "$scope" = "staged" ]; then
    args+=(--staged)
  else
    # Explicit, though 8.30 already walks every ref: a history scan that silently covered
    # only the checked-out branch would report "clean" while missing an entire branch.
    args+=(--log-opts=--all)
  fi

  local output status
  output=$(gitleaks "${args[@]}" . 2>&1)
  status=$?

  if [ "$status" -ne 0 ]; then
    findings=$((findings + 1))
    echo "  [gitleaks] leaks found:"
    # Strip ANSI colour FIRST, then drop progress lines. The other order fails: gitleaks
    # wraps the level in escape codes, so `INF` sits inside `\e[32mINF\e[0m` and a
    # word-boundary match never fires, which is why the first version printed the noise.
    echo "$output" \
      | sed -E 's/\x1b\[[0-9;]*[mGKH]//g' \
      | grep -vE "(INF|WRN) " \
      | grep -vE "^\s*$" \
      | sed 's/^/      /'
  fi
}

scan() {
  local label="$1" content_cmd="$2"
  for rule in "${RULES[@]}"; do
    local name="${rule%%|*}" pattern="${rule#*|}"
    local hits
    hits=$(eval "$content_cmd" | grep -InE "$pattern" 2>/dev/null | head -5)
    if [ -n "$hits" ]; then
      findings=$((findings + 1))
      echo "  [$label] $name"
      # Print the location but never the matched value, a scanner that echoes the secret
      # into a terminal, a CI log or a screenshot has just leaked it a second time.
      #
      # Two output shapes to redact, which is how the first version of this leaked a key:
      # `git grep` over files emits `path:line:content`, but a single-file `git show | grep`
      # emits only `line:content`. A pattern written for the first silently passes the
      # second straight through. Cut at the FIRST colon-number-colon or leading number.
      echo "$hits" \
        | sed -E -e 's/^([^:]*:)?([0-9]+):.*/\1\2:  <redacted match>/' \
        | sed 's/^/      /'
    fi
  done
}

case "$mode" in
  --staged)
    echo "scanning staged changes..."
    run_gitleaks staged
    files=$(git diff --cached --name-only --diff-filter=ACM | grep -vE "$EXCLUDE")
    if [ -z "$files" ]; then
      echo "  nothing further staged for the built-in rules"
    else
      for f in $files; do
        scan "staged" "git show :\"$f\" 2>/dev/null"
      done
    fi
    ;;
  all)
    echo "scanning full history with gitleaks..."
    run_gitleaks history

    echo "scanning working tree..."
    scan "worktree" "git grep -Ih '' -- . ':(exclude)*.lock' ':(exclude)*lock.json' ':(exclude)*lock.yaml' 2>/dev/null"

    echo "scanning full history ($(git rev-list --all --count) commits)..."
    scan "history" "git grep -Ih '' \$(git rev-list --all) -- 2>/dev/null"

    echo "checking for tracked env files..."
    tracked_env=$(git log --all --name-only --format="" | sort -u \
      | grep -E '(^|/)\.env' | grep -v '\.env\.example' || true)
    if [ -n "$tracked_env" ]; then
      findings=$((findings + 1))
      echo "  [history] an .env file was committed at some point:"
      echo "$tracked_env" | sed 's/^/      /'
    fi
    ;;
  *)
    echo "usage: $0 [--staged]" >&2
    exit 2
    ;;
esac

echo
if [ "$findings" -eq 0 ]; then
  echo "clean, no credential-shaped strings found."
  exit 0
fi

cat <<'EOF'
FINDINGS ABOVE.

If any is real, ROTATE THE KEY FIRST. Rewriting history second, and only if you want the
repo tidy. It is not remediation. GitHub's own guidance calls history scrubbing
"time-intensive and often unnecessary if you've already revoked the credential", and it is
unreliable anyway: commits survive in forks, in other people's clones, via SHA in cached
views, and through pull requests. Only GitHub Support can purge cached copies.

Assume anything pushed to a public repo was harvested within minutes. GitGuardian found 70%
of secrets leaked in 2022 were still valid three years later, because nobody rotated them.
EOF
exit 1
