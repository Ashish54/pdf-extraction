import pytest
from pypdf import PdfReader

from pdf_extractor import extract, load_config
from pdf_extractor.cli import main
from pdf_extractor.errors import (
    EmptySelectionError,
    MissingSectionsError,
    NoOutlineError,
    OutputPathError,
)

from conftest import STANDARD_OUTLINE, outline_titles, page_ids


def test_extract_keeps_configured_sections(pdf_factory, config_factory, tmp_path):
    pdf = pdf_factory()
    config = load_config(
        config_factory(
            title="My Doc",
            sections=["Chapter 1", "Chapter 3"],
            keep_back_matter=False,
        )
    )
    out = tmp_path / "out.pdf"
    report = extract(config, pdf, out)

    # front matter (0-1) + Chapter 1 with subsections (4-7) + Chapter 3 (12-15)
    assert page_ids(out) == [0, 1, 4, 5, 6, 7, 12, 13, 14, 15]
    assert report.dropped_count == 20 - 10

    reader = PdfReader(str(out))
    assert reader.metadata.title == "My Doc"  # configured title stamps output
    titles = outline_titles(reader)
    assert ("Chapter 1", 0) in titles
    assert ("Section 1.1", 1) in titles  # nesting preserved
    assert ("Chapter 3", 0) in titles
    assert "Appendix" not in [t for t, _ in titles]


def test_back_matter_default_keeps_final_dropped_section(pdf_factory, config_factory, tmp_path):
    pdf = pdf_factory()
    config = load_config(config_factory(sections=["Chapter 1"]))
    out = tmp_path / "out.pdf"
    extract(config, pdf, out)
    # Appendix pages ride along as back matter
    assert page_ids(out) == [0, 1, 4, 5, 6, 7, 16, 17, 18, 19]


def test_match_all_keeps_every_occurrence(pdf_factory, config_factory, tmp_path):
    outline = [
        ("Chapter 1", 0, 2),
        ("Exercises", 1, 5),
        ("Chapter 2", 0, 8),
        ("Exercises", 1, 11),
    ]
    pdf = pdf_factory(num_pages=14, outline_spec=outline)
    config = load_config(
        config_factory(sections=["exercises"], keep_back_matter=False)
    )
    out = tmp_path / "out.pdf"
    extract(config, pdf, out)
    # front matter 0-1 + exercises ranges [5,8) and [11,14)
    assert page_ids(out) == [0, 1, 5, 6, 7, 11, 12, 13]


def test_dry_run_writes_nothing(pdf_factory, config_factory, tmp_path):
    pdf = pdf_factory()
    config = load_config(config_factory())
    out = tmp_path / "out.pdf"
    report = extract(config, pdf, out, dry_run=True)
    assert report.dry_run is True
    assert not out.exists()
    assert report.kept_pages  # selection still computed


def test_on_missing_fail_raises(pdf_factory, config_factory):
    pdf = pdf_factory()
    config = load_config(config_factory(sections=["Nope"], on_missing="fail"))
    with pytest.raises(MissingSectionsError):
        extract(config, pdf)


def test_no_outline_raises(pdf_factory, config_factory):
    pdf = pdf_factory(outline_spec=[])
    config = load_config(config_factory())
    with pytest.raises(NoOutlineError):
        extract(config, pdf)


def test_empty_selection_refused(pdf_factory, config_factory):
    pdf = pdf_factory()
    config = load_config(
        config_factory(
            sections=["Nope"],
            keep_front_matter=False,
            keep_back_matter=False,
        )
    )
    with pytest.raises(EmptySelectionError):
        extract(config, pdf)


def test_refuses_to_overwrite_input(pdf_factory, config_factory):
    pdf = pdf_factory()
    config = load_config(config_factory())
    with pytest.raises(OutputPathError):
        extract(config, pdf, pdf)


def test_no_bookmarks_option(pdf_factory, config_factory, tmp_path):
    pdf = pdf_factory()
    config = load_config(config_factory(keep_back_matter=False))
    out = tmp_path / "out.pdf"
    extract(config, pdf, out, keep_bookmarks=False)
    assert outline_titles(PdfReader(str(out))) == []


def test_drop_printed_toc(pdf_factory, config_factory, tmp_path):
    outline = [("Contents", 0, 1)] + [
        (t, lvl, p + 1 if p >= 1 else p) for t, lvl, p in STANDARD_OUTLINE
    ]
    pdf = pdf_factory(num_pages=21, outline_spec=outline)
    config = load_config(
        config_factory(
            sections=["Chapter 1"],
            keep_back_matter=False,
            drop_printed_toc=True,
        )
    )
    out = tmp_path / "out.pdf"
    extract(config, pdf, out)
    ids = page_ids(out)
    assert 1 not in ids  # printed TOC page dropped
    assert 0 in ids  # cover stays
    assert ids == [0, 5, 6, 7, 8]  # Chapter 1 shifted one page by the extra bookmark


def test_cli_end_to_end(pdf_factory, config_factory, tmp_path, capsys):
    pdf = pdf_factory()
    config = config_factory(sections=["Chapter 1"], keep_back_matter=False)
    out = tmp_path / "cli-out.pdf"
    rc = main([str(config), str(pdf), "-o", str(out)])
    assert rc == 0
    assert page_ids(out) == [0, 1, 4, 5, 6, 7]
    assert "Pages kept 6 / 20" in capsys.readouterr().out


def test_cli_dry_run(pdf_factory, config_factory, tmp_path, capsys):
    pdf = pdf_factory()
    config = config_factory()
    rc = main([str(config), str(pdf), "--dry-run", "-o", str(tmp_path / "x.pdf")])
    assert rc == 0
    assert not (tmp_path / "x.pdf").exists()
    assert "dry-run" in capsys.readouterr().out


def test_cli_exit_codes(pdf_factory, config_factory):
    no_outline_pdf = pdf_factory(outline_spec=[], name="bare.pdf")
    config = config_factory()
    assert main([str(config), str(no_outline_pdf)]) == 3

    fail_config = config_factory(sections=["Nope"], on_missing="fail")
    assert main([str(fail_config), str(pdf_factory())]) == 2


def _config_with_dirs(config_factory, in_dir, out_dir, **overrides):
    overrides.setdefault("input_dir", str(in_dir))
    overrides.setdefault("output_dir", str(out_dir))
    return config_factory(**overrides)


def test_filename_resolved_in_input_dir_default_output(pdf_factory, config_factory, tmp_path):
    in_dir, out_dir = tmp_path / "in", tmp_path / "out"
    in_dir.mkdir()
    pdf = pdf_factory(name="annual_report.pdf")
    pdf.rename(in_dir / "annual_report.pdf")

    config = load_config(
        _config_with_dirs(
            config_factory, in_dir, out_dir,
            sections=["Chapter 1"], keep_back_matter=False,
        )
    )
    report = extract(config, "annual_report.pdf")  # bare file name only

    out = out_dir / "annual_report_reduced.pdf"
    assert report.output_path == out
    assert page_ids(out) == [0, 1, 4, 5, 6, 7]
    # title fetched from the file name
    assert PdfReader(str(out)).metadata.title == "annual_report"


def test_config_title_overrides_file_name(pdf_factory, config_factory, tmp_path):
    in_dir = tmp_path / "in"
    in_dir.mkdir()
    pdf = pdf_factory(name="annual_report.pdf")
    pdf.rename(in_dir / "annual_report.pdf")

    config = load_config(
        _config_with_dirs(
            config_factory, in_dir, tmp_path / "out",
            title="Custom Title", keep_back_matter=False,
        )
    )
    report = extract(config, "annual_report.pdf")
    assert PdfReader(str(report.output_path)).metadata.title == "Custom Title"


def test_missing_input_error_mentions_input_dir(pdf_factory, config_factory, tmp_path):
    config = load_config(
        _config_with_dirs(config_factory, tmp_path / "in", tmp_path / "out")
    )
    with pytest.raises(FileNotFoundError, match="also tried"):
        extract(config, "ghost.pdf")


def test_cli_runs_with_bare_filename(pdf_factory, config_factory, tmp_path):
    in_dir, out_dir = tmp_path / "in", tmp_path / "out"
    in_dir.mkdir()
    pdf = pdf_factory(name="report.pdf")
    pdf.rename(in_dir / "report.pdf")
    config = _config_with_dirs(
        config_factory, in_dir, out_dir, sections=["Chapter 1"], keep_back_matter=False
    )
    assert main([str(config), "report.pdf"]) == 0
    assert page_ids(out_dir / "report_reduced.pdf") == [0, 1, 4, 5, 6, 7]
