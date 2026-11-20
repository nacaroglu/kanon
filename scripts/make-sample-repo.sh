#!/usr/bin/env bash
# Build the sample procedure repository from fixtures/sample-procedures.
#
# Usage: scripts/make-sample-repo.sh <destination-directory>
#
# The result is deterministic: author, committer, dates, messages and file
# contents are fixed, so every run produces the same commit hashes. Prints the
# HEAD commit hash on stdout.
set -euo pipefail

if [ "$#" -ne 1 ]; then
  echo "usage: $0 <destination-directory>" >&2
  exit 2
fi

src="$(cd "$(dirname "${BASH_SOURCE[0]}")/../fixtures/sample-procedures" && pwd)"
dest="$1"

if [ -e "$dest" ] && [ -n "$(ls -A "$dest")" ]; then
  echo "error: $dest exists and is not empty" >&2
  exit 1
fi
mkdir -p "$dest"
dest="$(cd "$dest" && pwd)"

# Ignore the caller's Git configuration (signing, hooks, autocrlf, templates).
export GIT_CONFIG_GLOBAL=/dev/null
export GIT_CONFIG_SYSTEM=/dev/null
export GIT_CONFIG_NOSYSTEM=1
export GIT_AUTHOR_NAME="Kanon Sample" GIT_AUTHOR_EMAIL="sample@kanon.invalid"
export GIT_COMMITTER_NAME="Kanon Sample" GIT_COMMITTER_EMAIL="sample@kanon.invalid"

git -C "$dest" init --quiet --initial-branch=main --template=

commit() {  # commit <iso-date> <message> <file>...
  local date="$1" message="$2"
  shift 2
  for file in "$@"; do
    mkdir -p "$dest/$(dirname "$file")"
    cp "$src/$file" "$dest/$file"
    git -C "$dest" add -- "$file"
  done
  GIT_AUTHOR_DATE="$date" GIT_COMMITTER_DATE="$date" \
    git -C "$dest" commit --quiet --no-gpg-sign --no-verify -m "$message"
}

commit "2026-01-05T09:00:00+0000" "Add expense reports procedure" \
  README.md procedures/index.txt procedures/expense-reports.md
commit "2026-02-10T10:30:00+0000" "Add remote work procedure" procedures/remote-work.md
commit "2026-03-16T14:15:00+0000" "Add incident response procedure" procedures/incident-response.md

git -C "$dest" rev-parse HEAD
