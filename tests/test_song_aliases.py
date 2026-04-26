"""Test that config.SONG_ALIASES is merged into MusicLibrary searchable variants.

Aliases capture the kid's actual pronunciation patterns mined from retry
clusters. They flow into the same scoring path as filename + ID3 tag variants
so the existing fuzzy + phonetic + LCS-stem stack uses them automatically.
"""
from __future__ import annotations

import os
from collections import OrderedDict
from pathlib import Path

import pytest

import config
from modules.music_library import MusicLibrary


@pytest.fixture
def test_catalog():
    return [
        "NO BATIDÃO - ZXKAI.mp3",
        "Jour 1.mp3",
        "Les dormantes.mp3",
        "Mais je t'aime.mp3",
    ]


@pytest.fixture
def aliases_for_test(monkeypatch):
    aliases = {
        "NO BATIDÃO - ZXKAI.mp3": ["batidao", "no bati", "non bati", "bati dao"],
        "Jour 1.mp3": ["jour un", "jen", "joue jour"],
    }
    monkeypatch.setattr(config, "SONG_ALIASES", aliases, raising=False)
    return aliases


def _build_library(catalog, debug=False):
    lib = MusicLibrary(library_path=None, fuzzy_threshold=50, debug=debug)
    cat = []
    metadata = []
    for fn in catalog:
        basename = os.path.splitext(os.path.basename(fn))[0]
        variants = lib._build_searchable_variants(basename, file_path=fn)
        cat.append(fn)
        metadata.append((fn, variants))
    lib._catalog = cat
    lib._catalog_metadata = metadata
    lib._search_best_cache = OrderedDict()
    if lib._phonetic_encoder:
        lib._phonetic_encoder.clear_cache()
    return lib


class TestAliasesPickedUpByLibrary:
    def test_aliases_become_variants_for_their_song(self, test_catalog, aliases_for_test):
        lib = _build_library(test_catalog)
        # Find the variants for NO BATIDÃO and check the aliases are in there
        for fp, variants in lib._catalog_metadata:
            if fp == "NO BATIDÃO - ZXKAI.mp3":
                joined = " | ".join(v.lower() for v in variants)
                for alias in ("batidao", "no bati", "non bati", "bati dao"):
                    assert alias in joined, f"alias {alias!r} not in variants: {variants}"
                break
        else:
            pytest.fail("NO BATIDÃO not found in catalog")

    def test_aliases_unlock_search_for_kid_pronunciations(self, test_catalog, aliases_for_test):
        """Search queries that are alias-shaped should now resolve to the right song."""
        lib = _build_library(test_catalog)
        # "non bati" was a documented kid pronunciation that V0 missed
        result = lib.search_best("non bati")
        assert result is not None
        assert result[0] == "NO BATIDÃO - ZXKAI.mp3"

    def test_no_aliases_means_no_change(self, test_catalog, monkeypatch):
        """Songs without aliases keep their original variants (regression guard)."""
        monkeypatch.setattr(config, "SONG_ALIASES", {}, raising=False)
        lib = _build_library(test_catalog)
        for fp, variants in lib._catalog_metadata:
            if fp == "Mais je t'aime.mp3":
                # Should have basename + parts split on " - " etc., but no alias text
                joined = " | ".join(v.lower() for v in variants)
                assert "batidao" not in joined  # alias of another song
                break

    def test_alias_for_missing_song_is_silently_ignored(self, test_catalog, monkeypatch):
        """Aliases for songs no longer in the catalog should not crash."""
        monkeypatch.setattr(
            config,
            "SONG_ALIASES",
            {"DELETED.mp3": ["nonsense"], "NO BATIDÃO - ZXKAI.mp3": ["batidao"]},
            raising=False,
        )
        lib = _build_library(test_catalog)  # must not raise
        assert lib._catalog_metadata  # library is built
        # The valid alias still applied
        for fp, variants in lib._catalog_metadata:
            if fp == "NO BATIDÃO - ZXKAI.mp3":
                assert any("batidao" in v.lower() for v in variants)
