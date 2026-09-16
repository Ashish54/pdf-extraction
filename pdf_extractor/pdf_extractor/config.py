"""YAML config loading and validation."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

import yaml

from .errors import ConfigError
from .matcher import normalize

logger = logging.getLogger(__name__)

KNOWN_KEYS = frozenset(
    {
        "title",
        "sections",
        "on_missing",
        "keep_front_matter",
        "keep_back_matter",
        "drop_printed_toc",
        "input_dir",
        "output_dir",
    }
)

ON_MISSING_MODES = ("warn", "fail")


@dataclass(frozen=True)
class ExtractConfig:
    """Validated extraction settings."""

    sections: list[str]
    title: str | None = None  # output /Title override; default is the input file name
    on_missing: str = "warn"  # warn | fail
    keep_front_matter: bool = True
    keep_back_matter: bool = True
    drop_printed_toc: bool = False
    input_dir: str = "."  # bare file names are resolved inside this directory
    output_dir: str = "."  # default output location: <output_dir>/<name>_reduced.pdf


def load_config(path: str | Path) -> ExtractConfig:
    path = Path(path)
    if not path.is_file():
        raise ConfigError(f"Config file not found: {path}")
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ConfigError(f"Invalid YAML in {path}: {exc}") from exc
    if not isinstance(raw, dict):
        raise ConfigError(f"Config root must be a mapping, got {type(raw).__name__}")

    for key in raw:
        if key not in KNOWN_KEYS:
            logger.warning(
                "Unknown config key %r ignored (known keys: %s)", key, sorted(KNOWN_KEYS)
            )

    sections_raw = raw.get("sections")
    if not isinstance(sections_raw, list) or not sections_raw:
        raise ConfigError("Config key 'sections' must be a non-empty list of titles")
    sections: list[str] = []
    seen: set[str] = set()
    for item in sections_raw:
        if not isinstance(item, str) or not item.strip():
            raise ConfigError(f"Section titles must be non-empty strings, got {item!r}")
        key = normalize(item)
        if key in seen:
            logger.warning("Duplicate section %r (after normalization) ignored", item)
            continue
        seen.add(key)
        sections.append(item.strip())

    title = raw.get("title")
    if title is not None and not isinstance(title, str):
        raise ConfigError(f"Config key 'title' must be a string, got {title!r}")

    on_missing = raw.get("on_missing", "warn")
    if on_missing not in ON_MISSING_MODES:
        raise ConfigError(
            f"on_missing must be one of {ON_MISSING_MODES}, got {on_missing!r}"
        )

    def _flag(name: str, default: bool) -> bool:
        value = raw.get(name, default)
        if not isinstance(value, bool):
            raise ConfigError(f"{name} must be true/false, got {value!r}")
        return value

    def _dir(name: str, default: str) -> str:
        value = raw.get(name, default)
        if not isinstance(value, str) or not value.strip():
            raise ConfigError(f"{name} must be a directory path string, got {value!r}")
        return value

    return ExtractConfig(
        sections=sections,
        title=title.strip() if isinstance(title, str) and title.strip() else None,
        on_missing=on_missing,
        keep_front_matter=_flag("keep_front_matter", True),
        keep_back_matter=_flag("keep_back_matter", True),
        drop_printed_toc=_flag("drop_printed_toc", False),
        input_dir=_dir("input_dir", "."),
        output_dir=_dir("output_dir", "."),
    )
