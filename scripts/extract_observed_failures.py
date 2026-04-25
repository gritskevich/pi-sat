#!/usr/bin/env python3
"""Mine pi-sat journal logs for retry-clusters and propose ground-truth labels.

Self-supervised labeling: when the kid says "Alexa" multiple times in quick
succession (≤60s gap), she is retrying a previous failed match. The LAST
high-confidence song match in the cluster is the ground truth for *all*
attempts in the cluster.

Caveat: clusters that end without a confident match (≥70%) are unreliable —
the kid may have given up or switched intent. Only `cluster-final-high`
inferences are emitted as proposed test cases. Lower-confidence clusters are
listed for human review but not auto-added.

Usage:
    scripts/extract_observed_failures.py [--since today] [--gap 60] [--min-conf 70]

Output: prints a JSON snippet of new fixture cases ready for review and
appending to `tests/fixtures/observed_failures_*.json`.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from collections import Counter
from typing import Optional


WAKE_RE = re.compile(r'WAKE WORD:')
# Greedy: STT output may contain apostrophes ("d'eau", "n'oublie"); take
# everything up to the final closing quote on the line.
TEXT_RE = re.compile(r"TEXT: '(.+)'")
# The query side may contain apostrophes ("d'eau"), so be permissive: anchor
# on the trailing "→ 'SONG' (N%)" segment which is unambiguous.
SONG_RE = re.compile(r"Search \(best\):.*?→ '([^']+)' \(([\d.]+)%\)")
TS_RE = re.compile(r'^\w+ \d+ (\d{2}:\d{2}:\d{2}) ')


def to_sec(ts: str) -> int:
    h, m, s = map(int, ts.split(':'))
    return h * 3600 + m * 60 + s


def parse_journal(since: str) -> list[dict]:
    out = subprocess.run(
        ["journalctl", "--user-unit", "pi-sat.service", "--since", since, "--no-pager"],
        capture_output=True, text=True, check=False,
    ).stdout

    interactions: list[dict] = []
    cur: Optional[dict] = None
    for line in out.splitlines():
        m = TS_RE.match(line)
        if not m:
            continue
        ts = m.group(1)
        if WAKE_RE.search(line):
            if cur is not None:
                interactions.append(cur)
            cur = {'ts': ts, 't': to_sec(ts), 'text': '', 'song': None, 'conf': 0.0}
            continue
        if cur is None:
            continue
        tm = TEXT_RE.search(line)
        if tm:
            cur['text'] = tm.group(1)
            continue
        sm = SONG_RE.search(line)
        if sm:
            cur['song'] = sm.group(1)
            cur['conf'] = float(sm.group(2))

    if cur is not None:
        interactions.append(cur)
    return interactions


def cluster(interactions: list[dict], gap_s: int) -> list[list[dict]]:
    clusters: list[list[dict]] = []
    cur: list[dict] = []
    last_t = -10**9
    for ix in interactions:
        if ix['t'] - last_t <= gap_s:
            cur.append(ix)
        else:
            if cur:
                clusters.append(cur)
            cur = [ix]
        last_t = ix['t']
    if cur:
        clusters.append(cur)
    return clusters


def infer(clusters: list[list[dict]], min_conf: float) -> list[dict]:
    """Yield proposed (text, expected_song, confidence) tuples for review."""
    proposed: list[dict] = []
    for ci, cl in enumerate(clusters):
        # Find the last high-confidence match in the cluster
        anchor: Optional[dict] = None
        for ix in reversed(cl):
            if ix['song'] and ix['conf'] >= min_conf:
                anchor = ix
                break
        if anchor is None:
            # Cluster failed or ended low-confidence — skip (unreliable label)
            continue

        for ix in cl:
            # Skip the anchor itself (it's already the correct match)
            if ix is anchor:
                continue
            # Only include attempts that didn't already match the anchor song
            if ix['song'] == anchor['song']:
                continue
            # Empty texts give no test signal
            if not ix['text'].strip():
                continue
            proposed.append({
                'cluster': ci,
                'cluster_size': len(cl),
                'ts': ix['ts'],
                'text': ix['text'],
                'expected_song': anchor['song'],
                'anchor_text': anchor['text'],
                'anchor_conf': anchor['conf'],
                'own_match': ix['song'],
                'own_conf': ix['conf'],
            })
    return proposed


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--since', default='today', help="journalctl --since arg")
    ap.add_argument('--gap', type=int, default=60, help="cluster gap in seconds")
    ap.add_argument('--min-conf', type=float, default=70.0,
                    help="minimum confidence (%) to treat the cluster's final "
                         "match as ground truth (default 70)")
    args = ap.parse_args()

    interactions = parse_journal(args.since)
    if not interactions:
        print("No interactions parsed — is the service running and logging?", file=sys.stderr)
        sys.exit(1)

    clusters = cluster(interactions, args.gap)
    proposed = infer(clusters, args.min_conf)

    n_clusters = len(clusters)
    n_retries = sum(1 for c in clusters if len(c) >= 2)
    target_freq = Counter(p['expected_song'] for p in proposed)

    print(f"# pi-sat retry-cluster mining ({args.since})", file=sys.stderr)
    print(f"# {len(interactions)} interactions, {n_clusters} clusters, "
          f"{n_retries} with retries", file=sys.stderr)
    print(f"# {len(proposed)} candidate fixture cases (confidence ≥ {args.min_conf}%)",
          file=sys.stderr)
    print(f"# Top inferred targets:", file=sys.stderr)
    for song, n in target_freq.most_common(5):
        print(f"#   {n:2d}× {song}", file=sys.stderr)
    print(file=sys.stderr)

    json.dump(proposed, sys.stdout, ensure_ascii=False, indent=2)
    print()


if __name__ == "__main__":
    main()
