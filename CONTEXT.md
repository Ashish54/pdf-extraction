# PDF Section Extractor

A tool that keeps only the configured sections of a large PDF and drops the rest, locating each section's pages through the document's own navigation structure and copying surviving pages verbatim into a new PDF.

## Language

**Section**:
A titled entry in the PDF's embedded outline (bookmarks), together with all content belonging to it. Sections nest: a Section owns every Section below it in the outline hierarchy.
_Avoid_: chapter, heading, bookmark (a bookmark is only the pointer; the Section is what it points to)

**Section Range**:
The pages a Section occupies: from its start page up to (but excluding) the start page of the next outline entry at the same or higher level. A Section Range always contains the ranges of its subsections.

**Front Matter**:
All pages before the first outline entry's start page (cover, title page, printed TOC, preface). Kept by default regardless of the config's section list.

**Back Matter**:
All pages from the last outline entry's start page to the end of the document. Kept by default even when that final Section is dropped, because page granularity makes its tail (colophon, back cover) inseparable from the Section's own content.

**Boundary Page**:
A page where one Section's content ends and another's begins without a clean page break. Kept/dropped status flips across a Boundary Page, so it may visibly contain content of a dropped Section — an accepted, reported limitation of page-granular extraction.

**Kept Set**:
The sorted, deduplicated list of original page indexes that survive: Front Matter + Back Matter + every matched Section Range, minus any dropped printed-TOC pages. Output pages appear in original document order.

**Printed TOC**:
A table of contents printed on document pages (as opposed to the embedded outline). When kept verbatim in the Front Matter it becomes stale: it lists dropped Sections and original page numbers.
_Avoid_: outline (that term is reserved for the embedded bookmark tree)

**Matched Section**:
A Section whose normalized title equals a normalized config entry. Matching is match-all: one config entry keeps every Section with that title.
