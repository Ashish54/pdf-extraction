from pdf_extractor.outline import Section
from pdf_extractor.selector import compute_selection


def make_sections():
    return [
        Section("Introduction", 0, 2, 4),
        Section("Chapter 1", 0, 4, 8),
        Section("Section 1.1", 1, 5, 7),
        Section("Section 1.2", 1, 7, 8),
        Section("Chapter 2", 0, 8, 12),
        Section("Chapter 3", 0, 12, 16),
        Section("Appendix", 0, 16, 20),
    ]


def test_front_matter_and_kept_sections():
    sections = make_sections()
    kept = [sections[1]]  # Chapter 1: includes subsections 1.1, 1.2
    sel = compute_selection(sections, kept, 20, keep_back_matter=False)
    assert sel.pages == [0, 1, 4, 5, 6, 7]
    assert list(sel.front_matter) == [0, 1]


def test_no_front_matter():
    sections = make_sections()
    sel = compute_selection(
        sections, [sections[1]], 20, keep_front_matter=False, keep_back_matter=False
    )
    assert sel.pages == [4, 5, 6, 7]


def test_back_matter_kept_when_final_section_dropped():
    sections = make_sections()
    sel = compute_selection(sections, [sections[1]], 20)  # defaults keep both matters
    # Appendix (16-19) rides along as back matter despite being dropped
    assert sel.pages == [0, 1, 4, 5, 6, 7, 16, 17, 18, 19]
    assert sel.back_matter_section is sections[-1]
    assert list(sel.back_matter) == [16, 17, 18, 19]


def test_back_matter_disabled():
    sections = make_sections()
    sel = compute_selection(sections, [sections[1]], 20, keep_back_matter=False)
    assert sel.back_matter is None
    assert 16 not in sel.pages


def test_back_matter_irrelevant_when_final_section_kept():
    sections = make_sections()
    sel = compute_selection(sections, [sections[-1]], 20)
    assert sel.back_matter is None
    assert sel.pages == [0, 1, 16, 17, 18, 19]


def test_printed_toc_dropped_from_kept_pages():
    sections = [Section("Contents", 0, 1, 2)] + make_sections()
    sel = compute_selection(
        sections, [sections[2]], 20, toc_sections=[sections[0]]  # keep Chapter 1
    )
    assert 1 not in sel.pages
    assert sel.toc_dropped == [sections[0]]
    assert sel.pages[0] == 0  # remaining front matter page


def test_boundary_notes_flag_keep_status_flips():
    sections = make_sections()
    kept = [sections[4]]  # Chapter 2 only, pages 8-11
    sel = compute_selection(
        sections,
        kept,
        20,
        keep_front_matter=False,
        keep_back_matter=False,
    )
    flips = {(b.page, b.kept_after) for b in sel.boundaries}
    assert (8, True) in flips   # dropped Chapter 1 -> kept Chapter 2
    assert (12, False) in flips  # kept Chapter 2 -> dropped Chapter 3


def test_overlapping_kept_ranges_deduped():
    sections = make_sections()
    sel = compute_selection(
        sections,
        [sections[1], sections[2]],  # Chapter 1 and its subsection 1.1
        20,
        keep_back_matter=False,
    )
    assert sel.pages == sorted(set(sel.pages))
    assert sel.pages == [0, 1, 4, 5, 6, 7]
