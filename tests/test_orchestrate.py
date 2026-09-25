import json

import openai

from vignette_gen.client import GenerationError
from vignette_gen.orchestrate import RunOptions, generate_one, run

CONFIG = {
    "stated_aims": [
        {
            "id": "aim_a",
            "text": "Compute the average of a list of numbers.",
            "contract": "Returns the arithmetic mean. Returns None for an empty list.",
            "flavors": {"missing_edge_case": {"severity_tiers": ["trivial"]}},
        }
    ],
    "bug_flavor": {
        "missing_edge_case": {
            "id": "missing_edge_case",
            "definition": "DEF",
            "reference": "REF",
            "examples": [],
        }
    },
    "severity_tier": {
        "trivial": {"id": "trivial", "definition": "DEF", "reference": "REF"}
    },
}

TAG = "claudesonnet45"
ITEM = {
    "item_id": f"aim_a__missing_edge_case__{TAG}__000",
    "cell_id": "aim_a__missing_edge_case",
    "sample_idx": 0,
    "aim_id": "aim_a",
    "bug_flavor": "missing_edge_case",
    "generator_tag": TAG,
    "expected_severity_tiers": ["trivial"],
    "severity_tier": "trivial",
}

GOOD_CODE = "def f(x):\n    total = 0\n    for n in x:\n        total += n\n    result = total\n    if not x:\n        return 0\n    return result / len(x)\n"


class _ScriptedClient:
    def __init__(self, responses):
        self._responses = list(responses)
        self.calls = 0

    def generate(self, prompt):
        self.calls += 1
        return self._responses.pop(0)


class _RaisingClient:
    def __init__(self, error):
        self._error = error
        self.calls = 0

    def generate(self, prompt):
        self.calls += 1
        raise self._error


def test_generate_one_returns_code_and_rationale_on_first_success():
    client = _ScriptedClient(
        [json.dumps({"code": GOOD_CODE, "rationale": "off-by-one on empty list"})]
    )

    result = generate_one(client, ITEM, CONFIG, max_retries=3)

    assert result["code"] == GOOD_CODE
    assert result["rationale"] == "off-by-one on empty list"
    assert client.calls == 1


def test_generate_one_retries_on_invalid_code_then_succeeds():
    client = _ScriptedClient(
        [
            json.dumps({"code": "not valid python(", "rationale": "bad"}),
            json.dumps({"code": GOOD_CODE, "rationale": "good"}),
        ]
    )

    result = generate_one(client, ITEM, CONFIG, max_retries=3)

    assert result["code"] == GOOD_CODE
    assert client.calls == 2


def test_generate_one_raises_after_exhausting_retries():
    client = _ScriptedClient([json.dumps({"code": "bad(", "rationale": "x"})] * 3)

    try:
        generate_one(client, ITEM, CONFIG, max_retries=3)
        assert False, "expected RuntimeError"
    except RuntimeError:
        pass

    assert client.calls == 3


def test_run_writes_item_and_reports_counts(tmp_path):
    client = _ScriptedClient(
        [json.dumps({"code": GOOD_CODE, "rationale": "off-by-one on empty list"})]
    )
    options = RunOptions(
        model="anthropic/claude-sonnet-4.5",
        samples_per_cell=1,
        limit=1,
        dry_run=False,
        overwrite=False,
        max_retries=3,
        items_dir=tmp_path / "items",
        failures_path=tmp_path / "failures.jsonl",
    )

    def fake_load_config():
        return CONFIG

    def fake_build_items(config, samples_per_cell, limit, tag):
        return [ITEM]

    counts = run(client, options, load_config_fn=fake_load_config, build_items_fn=fake_build_items)

    assert counts == {"generated": 1, "skipped": 0, "failed": 0}
    written = json.loads((tmp_path / "items" / f"{ITEM['item_id']}.json").read_text())
    assert written["code"] == GOOD_CODE
    assert written["cell_id"] == ITEM["cell_id"]
    assert written["generation_model"] == "anthropic/claude-sonnet-4.5"


def test_run_skips_existing_item_without_calling_client(tmp_path):
    items_dir = tmp_path / "items"
    items_dir.mkdir(parents=True)
    (items_dir / f"{ITEM['item_id']}.json").write_text("{}")

    client = _ScriptedClient([])  # would raise IndexError if called
    options = RunOptions(
        model="anthropic/claude-sonnet-4.5",
        samples_per_cell=1,
        limit=1,
        dry_run=False,
        overwrite=False,
        max_retries=3,
        items_dir=items_dir,
        failures_path=tmp_path / "failures.jsonl",
    )

    counts = run(
        client,
        options,
        load_config_fn=lambda: CONFIG,
        build_items_fn=lambda config, samples_per_cell, limit, tag: [ITEM],
    )

    assert counts == {"generated": 0, "skipped": 1, "failed": 0}


def test_run_records_failure_and_continues(tmp_path):
    client = _ScriptedClient([json.dumps({"code": "bad(", "rationale": "x"})] * 3)
    options = RunOptions(
        model="anthropic/claude-sonnet-4.5",
        samples_per_cell=1,
        limit=1,
        dry_run=False,
        overwrite=False,
        max_retries=3,
        items_dir=tmp_path / "items",
        failures_path=tmp_path / "failures.jsonl",
    )

    counts = run(
        client,
        options,
        load_config_fn=lambda: CONFIG,
        build_items_fn=lambda config, samples_per_cell, limit, tag: [ITEM],
    )

    assert counts == {"generated": 0, "skipped": 0, "failed": 1}
    failures = (tmp_path / "failures.jsonl").read_text().splitlines()
    assert len(failures) == 1
    assert json.loads(failures[0])["item_id"] == ITEM["item_id"]


def test_generate_one_retries_on_api_error_then_raises_runtime_error():
    error = openai.APIError("rate limited", request=None, body=None)
    client = _RaisingClient(error)

    try:
        generate_one(client, ITEM, CONFIG, max_retries=3)
        assert False, "expected RuntimeError"
    except RuntimeError:
        pass

    assert client.calls == 3


def test_run_logs_api_error_as_failure_and_continues(tmp_path):
    error = openai.APIError("rate limited", request=None, body=None)
    client = _RaisingClient(error)
    options = RunOptions(
        model="anthropic/claude-sonnet-4.5",
        samples_per_cell=1,
        limit=1,
        dry_run=False,
        overwrite=False,
        max_retries=3,
        items_dir=tmp_path / "items",
        failures_path=tmp_path / "failures.jsonl",
    )

    counts = run(
        client,
        options,
        load_config_fn=lambda: CONFIG,
        build_items_fn=lambda config, samples_per_cell, limit, tag: [ITEM],
    )

    assert counts == {"generated": 0, "skipped": 0, "failed": 1}
    failures = (tmp_path / "failures.jsonl").read_text().splitlines()
    assert len(failures) == 1


def test_run_logs_generation_error_as_failure_and_continues(tmp_path):
    error = GenerationError("OpenRouter returned no content (detail: 'error')")
    client = _RaisingClient(error)
    options = RunOptions(
        model="anthropic/claude-sonnet-4.5",
        samples_per_cell=1,
        limit=1,
        dry_run=False,
        overwrite=False,
        max_retries=3,
        items_dir=tmp_path / "items",
        failures_path=tmp_path / "failures.jsonl",
    )

    counts = run(
        client,
        options,
        load_config_fn=lambda: CONFIG,
        build_items_fn=lambda config, samples_per_cell, limit, tag: [ITEM],
    )

    assert counts == {"generated": 0, "skipped": 0, "failed": 1}
    failures = (tmp_path / "failures.jsonl").read_text().splitlines()
    assert len(failures) == 1


def test_run_records_provenance_on_every_item(tmp_path):
    """Corpus-backed generation will fill these in; definition-only items must
    still record that they have no source rather than leaving it ambiguous."""
    client = _ScriptedClient([json.dumps({"code": GOOD_CODE, "rationale": "r"})])
    options = RunOptions(
        model="anthropic/claude-sonnet-4.5",
        generator_tag=TAG,
        samples_per_cell=1,
        limit=None,
        dry_run=False,
        overwrite=False,
        max_retries=1,
        items_dir=tmp_path / "items",
        failures_path=tmp_path / "failures.jsonl",
    )
    run(client, options,
        load_config_fn=lambda: CONFIG,
        build_items_fn=lambda config, samples_per_cell, limit, tag: [ITEM])

    record = json.loads((tmp_path / "items" / f"{ITEM['item_id']}.json").read_text())
    assert record["provenance"]["source"] == "generated"
    assert record["provenance"]["source_label"] is None
    assert record["generator_tag"] == TAG
    assert record["expected_severity_tiers"] == ["trivial"]


def test_run_refuses_to_write_into_another_generators_bank(tmp_path):
    import pytest

    items_dir = tmp_path / "items"
    items_dir.mkdir()
    (items_dir / "other.json").write_text(json.dumps({"generator_tag": "gpt5"}))

    options = RunOptions(
        model="anthropic/claude-sonnet-4.5",
        generator_tag=TAG,
        samples_per_cell=1,
        limit=None,
        dry_run=False,
        overwrite=False,
        max_retries=1,
        items_dir=items_dir,
        failures_path=tmp_path / "failures.jsonl",
    )
    with pytest.raises(ValueError, match="gpt5"):
        run(_ScriptedClient([]), options,
            load_config_fn=lambda: CONFIG,
            build_items_fn=lambda config, samples_per_cell, limit, tag: [ITEM])
