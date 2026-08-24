import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from generate_items import parse_args  # noqa: E402


def test_parse_args_defaults():
    args = parse_args([])
    assert args.model == "anthropic/claude-sonnet-4.5"
    assert args.samples_per_cell == 1
    assert args.limit is None
    assert args.dry_run is False
    assert args.overwrite is False
    assert args.max_retries == 3


def test_parse_args_overrides():
    args = parse_args(
        [
            "--model",
            "some-other-model",
            "--samples-per-cell",
            "5",
            "--limit",
            "10",
            "--dry-run",
            "--overwrite",
            "--max-retries",
            "1",
        ]
    )
    assert args.model == "some-other-model"
    assert args.samples_per_cell == 5
    assert args.limit == 10
    assert args.dry_run is True
    assert args.overwrite is True
    assert args.max_retries == 1
