"""Exception hierarchy for pdf_extractor."""

from __future__ import annotations


class ExtractorError(Exception):
    """Base class for all pdf_extractor errors."""


class ConfigError(ExtractorError):
    """The config file is missing, unreadable, or invalid."""


class NoOutlineError(ExtractorError):
    """The PDF has no embedded outline (bookmarks) to locate sections with."""


class MissingSectionsError(ExtractorError):
    """Config entries matched nothing and on_missing=fail."""

    def __init__(self, missing: list[str]) -> None:
        self.missing = missing
        super().__init__(
            "Config sections not found in the outline: "
            + ", ".join(repr(m) for m in missing)
        )


class EmptySelectionError(ExtractorError):
    """The selection rules produced zero pages to keep."""


class OutputPathError(ExtractorError):
    """The output path is invalid (e.g. identical to the input path)."""
