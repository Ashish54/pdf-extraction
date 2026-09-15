import pytest
from pypdf import PdfReader

from pdf_extractor.errors import NoOutlineError
from pdf_extractor.outline import OutlineSource


def test_flatten_and_ranges(pdf_factory):
    path = pdf_factory()
    reader = PdfReader(str(path))
    sections = OutlineSource().load(reader)

    by_title = {s.title: s for s in sections}
    assert by_title["Introduction"].level == 0
    assert (by_title["Introduction"].start_page, by_title["Introduction"].end_page) == (2, 4)
    assert (by_title["Chapter 1"].start_page, by_title["Chapter 1"].end_page) == (4, 8)
    # Nested subsections: range ends at next same-or-higher level bookmark
    assert (by_title["Section 1.1"].start_page, by_title["Section 1.1"].end_page) == (5, 7)
    assert (by_title["Section 1.2"].start_page, by_title["Section 1.2"].end_page) == (7, 8)
    assert (by_title["Chapter 2"].start_page, by_title["Chapter 2"].end_page) == (8, 12)
    # Last section runs to end of document
    assert (by_title["Appendix"].start_page, by_title["Appendix"].end_page) == (16, 20)


def test_no_outline_raises(pdf_factory):
    path = pdf_factory(outline_spec=[])
    reader = PdfReader(str(path))
    with pytest.raises(NoOutlineError):
        OutlineSource().load(reader)


def test_document_order_preserved(pdf_factory):
    path = pdf_factory()
    reader = PdfReader(str(path))
    sections = OutlineSource().load(reader)
    titles = [s.title for s in sections]
    assert titles == [
        "Introduction",
        "Chapter 1",
        "Section 1.1",
        "Section 1.2",
        "Chapter 2",
        "Chapter 3",
        "Appendix",
    ]
