from pdf_extractor.matcher import (
    find_printed_toc,
    match_sections,
    normalize,
)
from pdf_extractor.outline import Section


def test_normalize_case_and_whitespace():
    assert normalize("  Chapter   2:  Architecture\n") == "chapter 2: architecture"


def test_normalize_unicode_casefold():
    assert normalize("Étude") == normalize("étude")
    assert normalize("STRASSE") == normalize("strasse")


def test_match_is_normalized_exact():
    sections = [Section("Chapter 2: Architecture", 0, 8, 12)]
    result = match_sections(["chapter 2:  architecture"], sections)
    assert result.matched["chapter 2:  architecture"] == sections
    assert result.unmatched == []


def test_match_all_duplicate_titles():
    sections = [
        Section("Exercises", 1, 7, 8),
        Section("Chapter 2", 0, 8, 12),
        Section("Exercises", 1, 11, 12),
    ]
    result = match_sections(["exercises"], sections)
    hits = result.matched["exercises"]
    assert {s.start_page for s in hits} == {7, 11}


def test_unmatched_entries_reported():
    result = match_sections(["Nope"], [Section("Chapter 1", 0, 4, 8)])
    assert result.unmatched == ["Nope"]
    assert result.matched == {}


def test_sections_property_unique_and_ordered():
    s1 = Section("Part", 0, 4, 12)
    s2 = Section("Part", 0, 12, 16)
    result = match_sections(["Part", " part "], [s1, s2])
    assert result.sections == [s1, s2]  # deduplicated despite two config entries


def test_find_printed_toc():
    sections = [
        Section("Table of Contents", 0, 1, 2),
        Section("Chapter 1", 0, 4, 8),
        Section("contents", 0, 2, 3),
    ]
    hits = find_printed_toc(sections)
    assert {s.title for s in hits} == {"Table of Contents", "contents"}
