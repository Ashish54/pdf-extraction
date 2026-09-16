import logging

import pytest

from pdf_extractor.config import load_config
from pdf_extractor.errors import ConfigError


def test_defaults(config_factory):
    config = load_config(config_factory())
    assert config.sections == ["Chapter 1"]
    assert config.title is None
    assert config.on_missing == "warn"
    assert config.keep_front_matter is True
    assert config.keep_back_matter is True
    assert config.drop_printed_toc is False
    assert config.input_dir == "."
    assert config.output_dir == "."


def test_full_config(config_factory):
    config = load_config(
        config_factory(
            title="My Doc",
            on_missing="fail",
            keep_front_matter=False,
            keep_back_matter=False,
            drop_printed_toc=True,
            sections=["A", "B"],
        )
    )
    assert config.title == "My Doc"
    assert config.on_missing == "fail"
    assert config.keep_front_matter is False
    assert config.keep_back_matter is False
    assert config.drop_printed_toc is True
    assert config.sections == ["A", "B"]


def test_missing_sections_key_raises(tmp_path):
    path = tmp_path / "bad.yaml"
    path.write_text("title: nope\n", encoding="utf-8")
    with pytest.raises(ConfigError):
        load_config(path)


def test_bad_on_missing_raises(config_factory):
    with pytest.raises(ConfigError):
        load_config(config_factory(on_missing="shrug"))


def test_non_list_sections_raises(config_factory):
    with pytest.raises(ConfigError):
        load_config(config_factory(sections="Chapter 1"))


def test_duplicate_sections_deduped(config_factory, caplog):
    with caplog.at_level(logging.WARNING):
        config = load_config(config_factory(sections=["Ch 1", "ch  1", "Ch 2"]))
    assert config.sections == ["Ch 1", "Ch 2"]


def test_unknown_key_warns(config_factory, caplog):
    with caplog.at_level(logging.WARNING):
        load_config(config_factory(frobnicate=True))
    assert any("frobnicate" in r.message for r in caplog.records)


def test_missing_file_raises(tmp_path):
    with pytest.raises(ConfigError):
        load_config(tmp_path / "nope.yaml")


def test_dirs_parsed(config_factory):
    config = load_config(
        config_factory(input_dir="/data/pdfs/in", output_dir="/data/pdfs/out")
    )
    assert config.input_dir == "/data/pdfs/in"
    assert config.output_dir == "/data/pdfs/out"


def test_bad_dir_value_raises(config_factory):
    with pytest.raises(ConfigError):
        load_config(config_factory(input_dir=123))
    with pytest.raises(ConfigError):
        load_config(config_factory(output_dir=""))
