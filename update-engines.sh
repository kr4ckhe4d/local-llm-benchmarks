#!/usr/bin/env bash
# Update the two inference engines on this box, then restart what was running.
#
#   update-engines.sh status          what is behind upstream, changes nothing
#   update-engines.sh [all]           Strata, then llama.cpp
#   update-engines.sh strata | llama  one of them
#
# Strata: git pull --ff-only, then ./setup.sh --update ( engine rebuilt when its source changed, Python packages, model
# settings). The model files are not touched. strata-*.json is backed up first and any change is printed, because a
# setup run has dropped hand-tuned keys before (strata.md).
#
# llama.cpp: ~/llama.cpp runs branch `router` = upstream master + inkling2-strata-ideas (which is inkling2-speedups plus
# the Strata-inspired commits on top, since 2026-11-23), with the per-request thinking
# patch uncommitted on top. This follows the steps in the llama-router-branch memory:
#   1. ~/llama.cpp-inkling: fetch, stash its local edits, rebase $BRANCH onto origin/master, restore edits.
#   2. ~/llama.cpp: take the thinking patch off, `git reset --keep $BRANCH` with the models/ symlink moved
#      out of the way (llama-models-symlink memory), put the patch back (3-way), rebuild build/.
# Any conflict stops the script with the tree left as it is and says what to finish by hand. Nothing is pushed.
#
# Afterwards, before trusting a rebased llama.cpp: the KLD/llama-bench comparison and the 7-request per-request
# thinking check (see the memories). This script does not load models.
#
# Backups and logs: ~/.cache/update-engines/<timestamp>/
set -euo pipefail

BENCH="$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")"
SWITCH="$BENCH/switch-model.sh"
LLAMA="$HOME/llama.cpp"
WT="$HOME/llama.cpp-inkling"
# the branch the router builds (it carries inkling2-speedups underneath: rebasing it rebases both). The fork's own
# inkling2-speedups branch is no longer rebased by this script.
BRANCH="inkling2-strata-ideas"
STRATA="$HOME/code/Strata"
SAVED_PATCH="$BENCH/patches/llama-per-request-thinking.patch"
BK="$HOME/.cache/update-engines/$(date +%Y%m%d-%H%M%S)"

say()  { printf '\n==> %s\n' "$*"; }
die()  { printf '\nERROR: %s\n' "$*" >&2; exit 1; }

router_up() { pgrep -x llama-server >/dev/null 2>&1; }
strata_up() { curl -s --max-time 3 http://localhost:8095/health 2>/dev/null | grep -q '"service": *"strata"'; }
strata_pids() { pgrep -f 'code/Strata/(terminal/)?serve/server\.py' || true; }

# ---------------------------------------------------------------- status
status() {
  echo "Strata ($STRATA):"
  git -C "$STRATA" fetch -q origin
  echo "  at $(git -C "$STRATA" describe --tags --always HEAD), $(git -C "$STRATA" rev-list --count HEAD..@{u}) commits behind origin/main"
  echo "  server: $(strata_up && echo up on :8095 || echo down)"
  echo "llama.cpp:"
  git -C "$WT" fetch -q origin
  local behind; behind=$(git -C "$WT" rev-list --count "$BRANCH"..origin/master)
  echo "  $BRANCH: $(git -C "$WT" rev-list --count origin/master.."$BRANCH") local commits, upstream $behind commits ahead of its base"
  if [[ "$(git -C "$LLAMA" rev-parse HEAD)" == "$(git -C "$WT" rev-parse "$BRANCH")" ]]; then
    echo "  ~/llama.cpp: on $BRANCH's tip ($(git -C "$LLAMA" rev-parse --short HEAD))"
  else
    echo "  ~/llama.cpp: $(git -C "$LLAMA" rev-parse --short HEAD), NOT $BRANCH's tip $(git -C "$WT" rev-parse --short "$BRANCH")"
  fi
  echo "  thinking patch: $(git -C "$LLAMA" diff --quiet -- tools/server/ && echo NOT applied || echo applied)"
  echo "  router: $(router_up && echo running || echo down)"
}

# ---------------------------------------------------------------- Strata
update_strata() {
  say "Strata: backing up configs to $BK/strata"
  mkdir -p "$BK/strata"
  local f
  for f in "$STRATA"/strata-*.json "$STRATA"/terminal/strata-*.json; do
    [[ -f "$f" ]] && cp -p "$f" "$BK/strata/$(basename "$(dirname "$f")")-$(basename "$f")"
  done

  local pids; pids=$(strata_pids)
  if [[ -n "$pids" ]]; then
    say "Strata: stopping its server (pids $pids)"
    kill $pids 2>/dev/null || true
    for _ in $(seq 1 15); do [[ -z "$(strata_pids)" ]] && break; sleep 1; done
    [[ -z "$(strata_pids)" ]] || die "Strata's server did not stop"
  fi

  say "Strata: git pull + setup.sh --update (log: $BK/strata/update.log)"
  # update.sh (git pull + setup.sh --update) is gone since the 0.2.20 layout; do its two steps here
  if ! (cd "$STRATA" && git pull --ff-only && ./setup.sh --update --yes) > "$BK/strata/update.log" 2>&1; then
    tail -30 "$BK/strata/update.log" >&2
    die "Strata's update.sh failed, see $BK/strata/update.log"
  fi
  grep -E '^\s*\[(ok|!!|warn|error)\]' "$BK/strata/update.log" | sed 's/^ */    /' || true
  echo "    now at $(git -C "$STRATA" describe --tags --always HEAD)"

  say "Strata: config changes (paths moving is expected; a lost key is not)"
  local new changed=0
  for f in "$BK"/strata/*-strata-*.json; do
    [[ -e "$f" ]] || continue
    new="$STRATA/terminal/$(basename "$f" | sed 's/^[^-]*-//')"
    [[ -f "$new" ]] || new="$STRATA/$(basename "$f" | sed 's/^[^-]*-//')"
    if [[ ! -f "$new" ]]; then echo "    $(basename "$f"): no longer exists"; changed=1; continue; fi
    if ! diff -q "$f" "$new" >/dev/null; then
      changed=1; echo "    $new:"; diff "$f" "$new" | sed 's/^/      /' || true
    fi
  done
  (( changed )) || echo "    none"
}

# ---------------------------------------------------------------- llama.cpp
update_llama() {
  mkdir -p "$BK/llama"
  [[ -L "$LLAMA/models" ]] || die "$LLAMA/models is not the symlink to /mnt/fast/models; fix that first"

  say "llama.cpp: fetching upstream"
  git -C "$WT" fetch -q origin
  local upstream tip_before
  upstream=$(git -C "$WT" rev-parse origin/master)
  tip_before=$(git -C "$WT" rev-parse "$BRANCH")

  # 1. rebase the speedups branch in its worktree
  if [[ "$(git -C "$WT" merge-base "$BRANCH" origin/master)" == "$upstream" ]]; then
    echo "    $BRANCH already sits on origin/master ($(git -C "$WT" rev-parse --short origin/master))"
  else
    [[ "$(git -C "$WT" branch --show-current)" == "$BRANCH" ]] || die "$WT is not on $BRANCH"
    echo "    $(git -C "$WT" rev-list --count "$BRANCH"..origin/master) new upstream commits; rebasing $BRANCH ($tip_before)"
    echo "$tip_before" > "$BK/llama/$BRANCH.old-sha"
    local dirty; dirty=$(git -C "$WT" diff --name-only)
    if [[ -n "$dirty" ]]; then
      git -C "$WT" diff > "$BK/llama/inkling-worktree-edits.diff"
      # shellcheck disable=SC2086
      git -C "$WT" stash push -q -m "update-engines $(date +%F)" -- $dirty
    fi
    if ! git -C "$WT" rebase -q origin/master "$BRANCH"; then
      git -C "$WT" rebase --abort || true
      [[ -n "$dirty" ]] && git -C "$WT" stash pop -q || true
      die "rebase of $BRANCH onto origin/master conflicts. Nothing changed (aborted, edits restored). Rebase by hand in $WT."
    fi
    if [[ -n "$dirty" ]] && ! git -C "$WT" stash pop -q; then
      die "rebased, but restoring $WT's local edits conflicted; the stash is kept (git stash list). Copy: $BK/llama/inkling-worktree-edits.diff"
    fi
    echo "    rebased: $(git -C "$WT" rev-parse --short "$BRANCH") (old tip saved in $BK/llama/$BRANCH.old-sha)"
  fi

  local target; target=$(git -C "$WT" rev-parse "$BRANCH")
  if [[ "$(git -C "$LLAMA" rev-parse HEAD)" == "$target" ]] && ! git -C "$LLAMA" diff --quiet -- tools/server/; then
    echo "    ~/llama.cpp is already on $(git -C "$LLAMA" rev-parse --short HEAD) with the thinking patch: nothing to build"
    return 0
  fi

  # 2. move ~/llama.cpp (router build) to the new tip
  cd "$LLAMA"
  [[ "$(git branch --show-current)" == "router" ]] || die "$LLAMA is not on branch router"
  local patch="$BK/llama/thinking.patch"
  if git diff --quiet -- tools/server/; then
    echo "    thinking patch is not applied in ~/llama.cpp; using the saved copy"
    cp "$SAVED_PATCH" "$patch"
  else
    git diff -- tools/server/ > "$patch"
    git apply -R "$patch"
  fi
  local other; other=$(git status --porcelain --untracked-files=no | grep -v '^ D models/' || true)
  [[ -z "$other" ]] || { git apply --3way "$patch" >/dev/null 2>&1; git reset -q -- tools/server/;
                         die "~/llama.cpp has other tracked edits, not touching it:
$other"; }

  say "llama.cpp: ~/llama.cpp $(git rev-parse --short HEAD) -> $(git rev-parse --short "$target")"
  mv models models.symlink-tmp
  git sparse-checkout reapply
  if ! git reset -q --keep "$BRANCH"; then
    mv models.symlink-tmp models
    git apply --3way "$patch" >/dev/null 2>&1 && git reset -q -- tools/server/
    die "git reset --keep $BRANCH refused in ~/llama.cpp (patch put back, nothing else changed)"
  fi
  [[ -e models ]] && die "reset created a real models/ next to models.symlink-tmp; move it away and rename the symlink back by hand"
  mv models.symlink-tmp models
  [[ -L models ]] || die "models/ is not a symlink after the reset"

  if ! git apply --3way "$patch"; then
    die "the thinking patch no longer applies cleanly to tools/server/. Resolve the conflict markers there, then
       git -C ~/llama.cpp reset -q -- tools/server/  &&  git -C ~/llama.cpp diff -- tools/server/ > $SAVED_PATCH
       and rebuild: cmake --build ~/llama.cpp/build -j$(nproc). The patch as it was: $patch"
  fi
  git reset -q -- tools/server/
  git diff -- tools/server/ > "$SAVED_PATCH"
  echo "    thinking patch re-applied (saved copy refreshed: patches/$(basename "$SAVED_PATCH"))"

  # 3. rebuild with the router stopped (it spawns children from its own binary and libs)
  if router_up; then "$SWITCH" stop; fi
  say "llama.cpp: building build/ (log: $BK/llama/build.log)"
  if ! cmake --build build -j"$(nproc)" > "$BK/llama/build.log" 2>&1; then
    tail -30 "$BK/llama/build.log" >&2
    die "build failed, see $BK/llama/build.log"
  fi
  build/bin/llama-server --version 2>&1 | grep -E '^version' | sed 's/^/    /'
}

# ---------------------------------------------------------------- main
what="${1:-all}"
case "$what" in
  status) status; exit 0 ;;
  all|strata|llama) ;;
  *) echo "usage: $(basename "$0") [status|all|strata|llama]" >&2; exit 2 ;;
esac
mkdir -p "$BK"
exec > >(tee -a "$BK/update.log") 2>&1

ROUTER_WAS_UP=0; STRATA_WAS_UP=0
router_up && ROUTER_WAS_UP=1
strata_up && STRATA_WAS_UP=1

# Whatever happens, bring back what was serving before.
restore() {
  local rc=$?
  # a failure between the two mv's in update_llama leaves the models symlink renamed
  if [[ -L "$LLAMA/models.symlink-tmp" && ! -e "$LLAMA/models" ]]; then mv "$LLAMA/models.symlink-tmp" "$LLAMA/models"; fi
  if (( ROUTER_WAS_UP )) && ! router_up; then say "restarting the router"; "$SWITCH" start || true; fi
  if (( STRATA_WAS_UP || ROUTER_WAS_UP )) && ! strata_up; then "$SWITCH" strata || true; fi
  echo; echo "Log and backups: $BK"
  exit $rc
}
trap restore EXIT

[[ "$what" == all || "$what" == strata ]] && update_strata
[[ "$what" == all || "$what" == llama  ]] && update_llama

say "done"
if [[ "$what" != strata ]]; then
  echo "    Before trusting a rebased llama.cpp: KLD at -ub 512 and 1 plus llama-bench (Inkling, Qwen3.8, Gemma),"
  echo "    and the 7-request per-request thinking check on a Qwen3.8 preset."
fi
