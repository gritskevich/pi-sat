#!/usr/bin/env python3
"""Compare matching-algorithm variants on the full observed-failures dataset.

Loads:
  - tests/fixtures/observed_failures_2026-04-25.json (hand-curated + cluster-mined)
  - All clusters mined fresh from journalctl (cross-day, with --since "100 days ago")

Implements 6 ablations of the intent + music-library pipeline:
  V0  baseline                — pre-Stage-B FONEM, plain token_set_ratio
  V1  + homophone fold        — Stage B (mais/met/m'est → mets)
  V2  + LCS-stem boost        — Stage C (phonetic substring overlap bonus)
  V3  + word-boundary phonem  — encode each word separately, space-join
  V4  + retry penalty (state) — penalize songs the kid just rejected (cluster-aware)
  V5  + manual aliases        — catalog-side alias map for top-demand foreign songs
  V6  V2 + V3 + V4 + V5       — all stackable improvements

Reports for each variant:
  - intent classification pass rate
  - song top-1 accuracy
  - song top-3 accuracy
  - song top-5 accuracy

V0 is the reference; each Vi shows delta vs V0. Run with --verbose to see
per-case predictions.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from collections import OrderedDict, defaultdict
from copy import deepcopy
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

# Make pi-sat modules importable
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import config
from modules.intent_engine import IntentEngine
from modules.music_library import MusicLibrary
from modules.phonetic import PhoneticEncoder

FIXTURE_PATH = ROOT / "tests" / "fixtures" / "observed_failures_2026-04-25.json"


# ----------------------------------------------------------------------------
# Dataset construction
# ----------------------------------------------------------------------------

@dataclass
class Case:
    n: int
    text: str
    expected_intent: Optional[str]
    expected_song: Optional[str]
    cat: str
    source: str
    cluster_id: int = -1
    cluster_pos: int = 0


def load_hand_fixture() -> tuple[list[str], list[Case]]:
    fx = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    cases = []
    for c in fx["cases"]:
        cases.append(Case(
            n=c["n"], text=c["text"],
            expected_intent=c["intent"], expected_song=c["song"],
            cat=c["cat"], source="hand",
        ))
    for c in fx.get("cluster_mined_cases", []):
        cases.append(Case(
            n=c["n"], text=c["text"],
            expected_intent=c["intent"], expected_song=c["song"],
            cat=c["cat"], source="cluster:" + c.get("source", "?"),
        ))
    return fx["catalog"], cases


def load_intent_log_clusters(min_conf: float = 1.0) -> list[Case]:
    """Mine `logs/intent_log.jsonl` (+ .bak) for retry clusters across 15 dates.

    Each line is one wake/STT/intent record with ts, text, intent, matched_file.
    No song-match-confidence column, so the "anchor" is just any final entry in
    the cluster with matched_file != None and intent_confidence >= min_conf.
    """
    from datetime import datetime
    paths = [
        ROOT / "logs" / "intent_log.jsonl",
        ROOT / "logs" / "intent_log.jsonl.bak",
    ]
    records = []
    for p in paths:
        if not p.exists():
            continue
        for line in p.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                d = json.loads(line)
            except json.JSONDecodeError:
                continue
            ts = d.get("ts")
            if not ts:
                continue
            try:
                t = datetime.fromisoformat(ts).timestamp()
            except Exception:
                continue
            records.append({
                "ts": ts, "t": t,
                "text": d.get("text") or "",
                "intent": d.get("intent"),
                "intent_conf": float(d.get("intent_confidence") or 0),
                "matched_file": d.get("matched_file"),
            })
    records.sort(key=lambda r: r["t"])

    # Cluster by 60s gap
    clusters: list[list[dict]] = []
    cluster: list[dict] = []
    last_t = -10**12
    for r in records:
        if r["t"] - last_t <= 60:
            cluster.append(r)
        else:
            if cluster:
                clusters.append(cluster)
            cluster = [r]
        last_t = r["t"]
    if cluster:
        clusters.append(cluster)

    cases: list[Case] = []
    next_n = 1000
    for ci, cl in enumerate(clusters):
        anchor = None
        for r in reversed(cl):
            if r["matched_file"] and r["intent_conf"] >= min_conf:
                anchor = r
                break
        if anchor is None:
            continue
        for pos, r in enumerate(cl):
            text = r["text"].strip()
            if not text:
                continue
            cases.append(Case(
                n=next_n, text=text,
                expected_intent="play_music",
                expected_song=anchor["matched_file"],
                cat="MINED" if r is not anchor else "ANCHOR",
                source=f"intent_log_cluster_{ci}",
                cluster_id=10000 + ci,  # avoid collision with journalctl cluster ids
                cluster_pos=pos,
            ))
            next_n += 1
    return cases


def mine_extra_clusters(min_conf: float = 70.0) -> list[Case]:
    """Pull all of journalctl, cluster, return cases with cluster-final-high inferred labels.

    Returns Case objects with cluster_id and cluster_pos populated for stateful variants.
    """
    out = subprocess.run(
        ["journalctl", "--user-unit", "pi-sat.service", "--no-pager"],
        capture_output=True, text=True, check=False,
    ).stdout

    WAKE = re.compile(r'WAKE WORD:')
    TEXT = re.compile(r"TEXT: '(.+)'")
    SONG = re.compile(r"Search \(best\):.*?→ '([^']+)' \(([\d.]+)%\)")
    TS = re.compile(r'^\w+ \d+ (\d{2}:\d{2}:\d{2}) ')

    interactions = []
    cur = None
    for line in out.splitlines():
        m = TS.match(line)
        if not m:
            continue
        ts = m.group(1)
        if WAKE.search(line):
            if cur is not None:
                interactions.append(cur)
            cur = {'ts': ts, 't': _ts_to_sec(ts), 'text': '', 'song': None, 'conf': 0.0}
            continue
        if cur is None:
            continue
        tm = TEXT.search(line)
        if tm:
            cur['text'] = tm.group(1)
        sm = SONG.search(line)
        if sm:
            cur['song'] = sm.group(1)
            cur['conf'] = float(sm.group(2))
    if cur is not None:
        interactions.append(cur)

    # Cluster by 60s gap
    clusters = []
    cluster = []
    last_t = -10**9
    for ix in interactions:
        if ix['t'] - last_t <= 60:
            cluster.append(ix)
        else:
            if cluster:
                clusters.append(cluster)
            cluster = [ix]
        last_t = ix['t']
    if cluster:
        clusters.append(cluster)

    cases: list[Case] = []
    next_n = 100
    for ci, cl in enumerate(clusters):
        # Find the cluster anchor
        anchor = None
        for ix in reversed(cl):
            if ix['song'] and ix['conf'] >= min_conf:
                anchor = ix
                break
        if anchor is None:
            continue
        for pos, ix in enumerate(cl):
            if not ix['text'].strip():
                continue
            # Anchor itself: also include — it's a known-good case
            cases.append(Case(
                n=next_n, text=ix['text'],
                expected_intent="play_music",
                expected_song=anchor['song'],
                cat="MINED" if ix is not anchor else "ANCHOR",
                source=f"cluster_{ci}_anchor={anchor['conf']:.0f}%",
                cluster_id=ci,
                cluster_pos=pos,
            ))
            next_n += 1
    return cases


def _ts_to_sec(ts: str) -> int:
    h, m, s = map(int, ts.split(':'))
    return h * 3600 + m * 60 + s


def build_catalog_library(catalog: list[str], encoder: PhoneticEncoder) -> MusicLibrary:
    lib = MusicLibrary(library_path=None, fuzzy_threshold=50, debug=False)
    lib._phonetic_encoder = encoder
    lib.phonetic_enabled = encoder.is_available()
    cat = []
    metadata = []
    for fn in catalog:
        basename = os.path.splitext(os.path.basename(fn))[0]
        variants = lib._build_searchable_variants(basename)
        cat.append(fn)
        metadata.append((fn, variants))
    lib._catalog = cat
    lib._catalog_metadata = metadata
    lib._search_best_cache = OrderedDict()
    return lib


# ----------------------------------------------------------------------------
# Algorithm variants
# ----------------------------------------------------------------------------

class V0_baseline:
    """Pre-Stage-B: no homophone fold, no LCS boost, plain encoding."""
    name = "V0 baseline (pre-fix)"

    def __init__(self, catalog):
        # Patch encoder to disable Stage B fold
        self.encoder = PhoneticEncoder(algorithm="fonem")
        self._patch_encoder_no_fold(self.encoder)
        self.engine = self._build_engine(self.encoder)
        self.library = build_catalog_library(catalog, self.encoder)
        self._patch_library_no_lcs(self.library)

    def _patch_encoder_no_fold(self, encoder):
        # Bypass the homophone fold — use identity
        import unicodedata
        def _normalize_v0(text):
            if not text:
                return ""
            normalized = unicodedata.normalize('NFKD', text.lower())
            normalized = ''.join(ch for ch in normalized if not unicodedata.combining(ch))
            normalized = re.sub(r"[^a-z0-9]+", '', normalized).strip()
            return normalized
        encoder._normalize = _normalize_v0

    def _patch_library_no_lcs(self, library):
        # Replace _search_hybrid scoring with the pre-Stage-C version
        from thefuzz import fuzz
        original_compute_text_scores = library._compute_text_scores

        def _search_hybrid_v0(query):
            norm_query = library._normalize_variant(query)
            qph = library._phonetic_encoder.encode_query(query)
            if not qph:
                return library._search_text_only(query)
            best_score = 0
            best_file = None
            text_weight = 1.0 - library.phonetic_weight
            text_scores, per_file_variants = library._compute_text_scores(query, norm_query)
            top_candidates = sorted(text_scores, key=lambda x: x[1], reverse=True)[:10]
            cset = {x[0] for x in top_candidates}
            for fp, ts in text_scores:
                file_best = ts
                if fp in cset:
                    for variant in per_file_variants[fp]:
                        ph_str = library._phonetic_encoder.encode_pattern(variant)
                        ph_score = fuzz.token_set_ratio(qph, ph_str) if ph_str else 0
                        combined = (ts * text_weight) + (ph_score * library.phonetic_weight)
                        file_best = max(file_best, combined)
                if file_best > best_score:
                    best_score = file_best
                    best_file = fp
            if best_score < library.fuzzy_threshold:
                return None
            return (best_file, best_score / 100.0)

        library._search_hybrid = _search_hybrid_v0

    def _build_engine(self, encoder):
        engine = IntentEngine(fuzzy_threshold=50, language="fr", debug=False)
        engine._phonetic_encoder = encoder
        engine._phonetic_enabled = encoder.is_available()
        engine._phrase_entries = engine._build_phrase_entries(engine.language)
        return engine

    def predict(self, case: Case):
        intent = self.engine.classify(case.text)
        if intent is None:
            return None, None, []
        intent_name = intent.intent_type
        if intent_name != "play_music":
            return intent_name, None, []
        query = intent.parameters.get("query", "") or case.text
        # Production codepath: search_best uses _search_hybrid (the patched scoring).
        # rank_matches uses _rank_hybrid (separate code path, no LCS boost). Here
        # we use search_best for top-1 (production-accurate) and patch the rank
        # output by dropping search_best's pick and re-querying for top-3/top-5
        # via rank_matches as a best-effort fallback.
        best = self.library.search_best(query)
        if best is None:
            return intent_name, query, []
        ranked = self.library.rank_matches(query, limit=10)
        ordered = [best[0]] + [f for f, _ in ranked if f != best[0]]
        return intent_name, query, ordered[:5]

    def on_played(self, case, song):
        pass  # stateless


class V1_homophone(V0_baseline):
    name = "V1 + homophone fold (Stage B)"

    def _patch_encoder_no_fold(self, encoder):
        # Use the CURRENT (Stage B) encoder behavior — do nothing
        pass


class V2_lcs(V1_homophone):
    name = "V2 + LCS-stem boost (Stage C)"

    def _patch_library_no_lcs(self, library):
        # Use the CURRENT library scoring — do nothing
        pass


class V3_word_boundary(V2_lcs):
    """Encode words separately so token_set_ratio works on tokens."""
    name = "V3 + word-boundary phonetics"

    def _patch_encoder_no_fold(self, encoder):
        # Override _normalize to keep word boundaries (return space-separated words)
        import unicodedata
        from modules.phonetic import _FRENCH_HOMOPHONE_FOLD

        original_encode_text = encoder._encode_text

        def _normalize_v3(text):
            if not text:
                return ""
            normalized = unicodedata.normalize('NFKD', text.lower())
            normalized = ''.join(ch for ch in normalized if not unicodedata.combining(ch))
            normalized = normalized.replace("'", "").replace("’", "")
            words = [w for w in re.split(r"[^a-z0-9]+", normalized) if w]
            words = [_FRENCH_HOMOPHONE_FOLD.get(w, w) for w in words]
            # SPACE-JOIN instead of concatenating
            return ' '.join(words)

        def _encode_text_v3(text):
            # Encode each word separately with the FONEM matcher, then join with spaces
            if ' ' not in text:
                return original_encode_text(text)
            parts = []
            for word in text.split():
                if len(word) >= 3:
                    enc = original_encode_text(word)
                    if enc:
                        parts.append(enc)
                else:
                    parts.append(word.upper())
            return ' '.join(parts)

        encoder._normalize = _normalize_v3
        encoder._encode_text = _encode_text_v3


class V4_retry_penalty(V2_lcs):
    """In-session retry penalty: subtract score from songs the kid just rejected."""
    name = "V4 + retry penalty (stateful)"
    PENALTY = 20.0

    def __init__(self, catalog):
        super().__init__(catalog)
        self._cluster_recent_songs: dict[int, list[str]] = defaultdict(list)
        self._cluster_last_pos: dict[int, int] = {}

    def predict(self, case: Case):
        intent = self.engine.classify(case.text)
        if intent is None:
            return None, None, []
        intent_name = intent.intent_type
        if intent_name != "play_music":
            return intent_name, None, []
        query = intent.parameters.get("query", "") or case.text
        ranked = self.library.rank_matches(query, limit=10)

        # Apply penalty to recently-rejected songs in this cluster
        if case.cluster_id >= 0:
            recent = set(self._cluster_recent_songs.get(case.cluster_id, []))
            if recent:
                rescored = []
                for fp, score in ranked:
                    if fp in recent:
                        score = max(0, score - self.PENALTY / 100)
                    rescored.append((fp, score))
                rescored.sort(key=lambda x: x[1], reverse=True)
                ranked = rescored

        return intent_name, query, [f for f, _ in ranked[:5]]

    def on_played(self, case: Case, song: Optional[str]):
        # Track this attempt's top match as "potentially rejected"
        if case.cluster_id >= 0 and song is not None:
            self._cluster_recent_songs[case.cluster_id].append(song)


class V5_aliases(V2_lcs):
    """Catalog-side aliases for top-demand foreign songs (KISS: hardcoded)."""
    name = "V5 + manual aliases"

    ALIASES = {
        # Brazilian Portuguese rendered through French phonemes
        "NO BATIDÃO - ZXKAI.mp3": [
            "no batidao", "batidao", "no batidão", "no batido", "no bati",
            "bati dão", "bati dao", "non bati", "non bâti", "non batte",
            "no bate", "bati d eau", "bati dor", "non bati d eau",
            "non batte d eau",
        ],
    }

    def __init__(self, catalog):
        super().__init__(catalog)
        # Augment library catalog metadata with aliases
        for fp, variants in self.library._catalog_metadata:
            extra = self.ALIASES.get(os.path.basename(fp))
            if extra:
                variants.extend(extra)


class V6_combined(V2_lcs):
    """Stack V2 + V3 + V4 + V5."""
    name = "V6 V2+V3+V4+V5 stacked"
    PENALTY = 20.0

    def __init__(self, catalog):
        super().__init__(catalog)
        # V3 word-boundary patch
        V3_word_boundary._patch_encoder_no_fold(self, self.encoder)
        # Re-encode dictionary patterns with the new encoder behavior
        self.engine._phrase_entries = self.engine._build_phrase_entries(self.engine.language)
        # V5 catalog aliases
        for fp, variants in self.library._catalog_metadata:
            extra = V5_aliases.ALIASES.get(os.path.basename(fp))
            if extra:
                variants.extend(extra)
        # V4 stateful tracker
        self._cluster_recent_songs = defaultdict(list)

    def predict(self, case: Case):
        return V4_retry_penalty.predict(self, case)

    def on_played(self, case, song):
        return V4_retry_penalty.on_played(self, case, song)


class V7_no_retry(V2_lcs):
    """Drop V4 — penalty is harmful. Stack V2 + V3 + V5 only."""
    name = "V7 V2+V3+V5 (no retry penalty)"

    def __init__(self, catalog):
        super().__init__(catalog)
        # V3 word-boundary patch
        V3_word_boundary._patch_encoder_no_fold(self, self.encoder)
        self.engine._phrase_entries = self.engine._build_phrase_entries(self.engine.language)
        # V5 catalog aliases
        for fp, variants in self.library._catalog_metadata:
            extra = V5_aliases.ALIASES.get(os.path.basename(fp))
            if extra:
                variants.extend(extra)


# ----------------------------------------------------------------------------
# Eval runner
# ----------------------------------------------------------------------------

VARIANT_CLASSES = [
    V0_baseline, V1_homophone, V2_lcs, V3_word_boundary,
    V4_retry_penalty, V5_aliases, V6_combined, V7_no_retry,
]


@dataclass
class Result:
    name: str
    intent_pass: int = 0
    intent_total: int = 0
    song_top1: int = 0
    song_top3: int = 0
    song_top5: int = 0
    song_total: int = 0
    per_case: list[tuple[Case, str, list[str]]] = field(default_factory=list)


def evaluate(variant, cases: list[Case]) -> Result:
    res = Result(name=variant.name)
    # Sort by cluster_id, then cluster_pos to preserve session order for stateful variants
    cases = sorted(cases, key=lambda c: (c.cluster_id, c.cluster_pos, c.n))
    for case in cases:
        # Intent eval
        if case.expected_intent is not None or case.expected_song is None:
            res.intent_total += 1
        intent_name, query, top5 = variant.predict(case)
        # Intent correctness:
        if case.expected_intent is None:
            if intent_name is None:
                res.intent_pass += 1
        elif intent_name == case.expected_intent:
            res.intent_pass += 1

        # Song eval
        if case.expected_song is not None:
            res.song_total += 1
            if top5 and top5[0] == case.expected_song:
                res.song_top1 += 1
            if case.expected_song in top5[:3]:
                res.song_top3 += 1
            if case.expected_song in top5[:5]:
                res.song_top5 += 1
            res.per_case.append((case, top5[0] if top5 else "", top5[:3]))

        # Update stateful variant
        variant.on_played(case, top5[0] if top5 else None)
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--verbose", action="store_true")
    ap.add_argument("--variant", default=None, help="run only one variant by name prefix (e.g., V3)")
    args = ap.parse_args()

    catalog, hand_cases = load_hand_fixture()
    journal_mined = mine_extra_clusters()
    log_mined = load_intent_log_clusters()

    # Dedupe by text. Priority: hand > journal > log.
    seen_texts = set()
    cases: list[Case] = []
    for source_cases in (hand_cases, journal_mined, log_mined):
        for c in source_cases:
            if c.text in seen_texts:
                continue
            # Drop cases that reference songs not in our current catalog
            # (intent_log.jsonl spans 4 months — catalog has changed).
            if c.expected_song and c.expected_song not in catalog:
                continue
            seen_texts.add(c.text)
            cases.append(c)

    # Assign cluster_id to hand cases that don't have one (use cluster -1 == "solo")
    for c in cases:
        if c.cluster_id < 0:
            c.cluster_id = -c.n  # unique negative id keeps each as its own "cluster"

    n_hand = sum(1 for c in cases if c.source == "hand")
    n_journal = sum(1 for c in cases if c.source.startswith("cluster_"))
    n_log = sum(1 for c in cases if c.source.startswith("intent_log_cluster_"))
    print(f"Total cases: {len(cases)}  "
          f"(hand={n_hand}, journal-mined={n_journal}, intent-log-mined={n_log})")
    print(f"Catalog size: {len(catalog)}")
    print()

    selected = VARIANT_CLASSES
    if args.variant:
        selected = [v for v in VARIANT_CLASSES if v.__name__.startswith(args.variant) or v.name.startswith(args.variant)]
        if not selected:
            print(f"No variant matches {args.variant}", file=sys.stderr)
            sys.exit(1)

    results: list[Result] = []
    for cls in selected:
        # Reset config defaults (some variants patch global state)
        variant = cls(catalog)
        res = evaluate(variant, cases)
        results.append(res)
        print(f"{res.name:42s}  intent {res.intent_pass:3d}/{res.intent_total:3d}  "
              f"top1 {res.song_top1:3d}/{res.song_total:3d} ({res.song_top1/res.song_total*100 if res.song_total else 0:5.1f}%)  "
              f"top3 {res.song_top3:3d}/{res.song_total:3d}  "
              f"top5 {res.song_top5:3d}/{res.song_total:3d}")

    # Detailed comparison vs V0 baseline
    print()
    if results and results[0].name.startswith("V0"):
        b = results[0]
        print("Δ vs V0 baseline:")
        for r in results[1:]:
            di = r.intent_pass - b.intent_pass
            d1 = r.song_top1 - b.song_top1
            d3 = r.song_top3 - b.song_top3
            print(f"  {r.name:42s}  Δintent {di:+3d}  Δtop1 {d1:+3d}  Δtop3 {d3:+3d}")

    if args.verbose and results:
        # Show per-case best vs baseline
        print()
        print("Per-case top-1 (V0 / V_last):")
        b = results[0]
        last = results[-1]
        for (c, b_top, _), (_, l_top, _) in zip(b.per_case, last.per_case):
            mark_b = '✓' if b_top == c.expected_song else '✗'
            mark_l = '✓' if l_top == c.expected_song else '✗'
            change = '   ' if mark_b == mark_l else (' ↑ ' if mark_l == '✓' else ' ↓ ')
            print(f"  {mark_b}{change}{mark_l}  #{c.n:>3d} {c.cat:6s} {c.text[:50]:50s} → exp={c.expected_song[:35] if c.expected_song else '?':35s}")


if __name__ == "__main__":
    main()
