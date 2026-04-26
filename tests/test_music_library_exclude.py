"""MusicLibrary.search_best with an exclusion set.

The DENY loop adds the rejected song to a per-cluster exclusion set, then
re-runs the same query. The library must skip the excluded files and return
the next best match (or None when the pool empties).
"""
from __future__ import annotations

import os
from collections import OrderedDict
from typing import Iterable

import pytest

from modules.music_library import MusicLibrary


@pytest.fixture
def library():
    lib = MusicLibrary(library_path=None, fuzzy_threshold=50, debug=False)
    catalog = [
        "Mais je t'aime.mp3",
        "Les dormantes.mp3",
        "Mélodie hongroise.mp3",
        "NO BATIDÃO - ZXKAI.mp3",
        "Jour 1.mp3",
    ]
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


class TestExcludeBasic:
    def test_no_exclude_returns_top_match(self, library):
        result = library.search_best("mais")
        assert result is not None
        assert result[0] == "Mais je t'aime.mp3"

    def test_exclude_top_returns_next_best(self, library):
        result = library.search_best("mais", exclude={"Mais je t'aime.mp3"})
        # Should return something OTHER than Mais je t'aime
        assert result is not None
        assert result[0] != "Mais je t'aime.mp3"

    def test_empty_exclude_works_as_no_exclude(self, library):
        a = library.search_best("mais")
        b = library.search_best("mais", exclude=set())
        c = library.search_best("mais", exclude=None)
        assert a == b == c

    def test_exclude_list_works_too(self, library):
        # Should accept any iterable
        result = library.search_best("mais", exclude=["Mais je t'aime.mp3"])
        assert result is not None
        assert result[0] != "Mais je t'aime.mp3"


class TestExcludeMultiple:
    def test_two_excluded(self, library):
        result = library.search_best(
            "mais",
            exclude={"Mais je t'aime.mp3", "Les dormantes.mp3"},
        )
        # Top two excluded — should still return something else
        assert result is not None
        assert result[0] not in {"Mais je t'aime.mp3", "Les dormantes.mp3"}

    def test_all_excluded_returns_none(self, library):
        # Drop the entire catalog into exclusion
        all_files = {fp for fp, _ in library._catalog_metadata}
        result = library.search_best("mais", exclude=all_files)
        assert result is None


class TestExcludeAndCache:
    def test_cache_does_not_leak_across_exclusions(self, library):
        # Without exclude
        a = library.search_best("mais")
        # With exclude — must NOT return the cached result
        b = library.search_best("mais", exclude={"Mais je t'aime.mp3"})
        assert a != b

    def test_exclude_then_no_exclude_again(self, library):
        # Same query, exclude, then unexclude — should restore top match
        library.search_best("mais", exclude={"Mais je t'aime.mp3"})
        result = library.search_best("mais")
        assert result is not None
        assert result[0] == "Mais je t'aime.mp3"
