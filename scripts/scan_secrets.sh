#!/usr/bin/env bash
# Is there a credential anywhere in this repository, including its history?
#
#   ./scripts/scan_secrets.sh            # working tree + full history
#   ./scripts/scan_secrets.sh --staged   # only what is about to be committed (used by the hook)
#
# No dependency on gitleaks or trufflehog. Those are better tools with far larger rule sets,
# and if you have one, use it too. This exists so the check always runs: a scanner that has
# to be installed first is a scanner that is not installed on the machine where it matters.
#
# It matches on the SHAPE of a credential, not on variable names. `GROQ_API_KEY=` in an
# example file is documentation; `GROQ_API_KEY=gsk_live...` is an incident. Grepping for the
# name flags the first and misses the second, which is exactly backwards.
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
# justified — every entry is a place a real leak could hide.
EXCLUDE='^(.*\.lock|.*lock\.json|.*lock\.yaml|scripts/scan_secrets\.sh|\.githooks/pre-commit)$'

mode="${1:-all}"
findings=0

scan() {
  local label="$1" content_cmd="$2"
  for rule in "${RULES[@]}"; do
    local name="${rule%%|*}" pattern="${rule#*|}"
    local hits
    hits=$(eval "$content_cmd" | grep -InE "$pattern" 2>/dev/null | head -5)
    if [ -n "$hits" ]; then
      findings=$((findings + 1))
      echo "  [$label] $name"
      # Print the location but never the matched value — a scanner that echoes the secret
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
    files=$(git diff --cached --name-only --diff-filter=ACM | grep -vE "$EXCLUDE")
    [ -z "$files" ] && { echo "  nothing staged"; exit 0; }
    for f in $files; do
      scan "staged" "git show :\"$f\" 2>/dev/null"
    done
    ;;
  all)
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
  echo "clean — no credential-shaped strings found."
  exit 0
fi

cat <<'EOF'
FINDINGS ABOVE.

If any is real, rotating the key is the first step and rewriting history is the second —
in that order. Rewriting alone does not help: assume anything pushed to a public repo was
harvested within minutes, and hosts keep unreachable objects addressable by SHA for a
while after a force-push.
EOF
exit 1
