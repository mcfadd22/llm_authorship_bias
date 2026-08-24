import json

import anthropic

from vignette_gen.orchestrate import RunOptions, generate_one, run

CONFIG = {
    "stated_aims": [
        {"id": "aim_a", "text": "Compute the average of a list of numbers."}
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

ITEM = {
    "item_id": "aim_a__missing_edge_case__trivial__aim_defeating__000",
    "cell_id": "aim_a__missing_edge_case__trivial__aim_defeating",
    "sample_idx": 0,
    "aim_id": "aim_a",
    "bug_flavor": "missing_edge_case",
    "severity_tier": "trivial",
    "bug_aim_relation": "aim_defeating",
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
        model="claude-sonnet-5",
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

    def fake_build_items(config, samples_per_cell, limit):
        return [ITEM]

    counts = run(client, options, load_config_fn=fake_load_config, build_items_fn=fake_build_items)

    assert counts == {"generated": 1, "skipped": 0, "failed": 0}
    written = json.loads((tmp_path / "items" / f"{ITEM['item_id']}.json").read_text())
    assert written["code"] == GOOD_CODE
    assert written["cell_id"] == ITEM["cell_id"]
    assert written["generation_model"] == "claude-sonnet-5"


def test_run_skips_existing_item_without_calling_client(tmp_path):
    items_dir = tmp_path / "items"
    items_dir.mkdir(parents=True)
    (items_dir / f"{ITEM['item_id']}.json").write_text("{}")

    client = _ScriptedClient([])  # would raise IndexError if called
    options = RunOptions(
        model="claude-sonnet-5",
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
        build_items_fn=lambda config, samples_per_cell, limit: [ITEM],
    )

    assert counts == {"generated": 0, "skipped": 1, "failed": 0}


def test_run_records_failure_and_continues(tmp_path):
    client = _ScriptedClient([json.dumps({"code": "bad(", "rationale": "x"})] * 3)
    options = RunOptions(
        model="claude-sonnet-5",
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
        build_items_fn=lambda config, samples_per_cell, limit: [ITEM],
    )

    assert counts == {"generated": 0, "skipped": 0, "failed": 1}
    failures = (tmp_path / "failures.jsonl").read_text().splitlines()
    assert len(failures) == 1
    assert json.loads(failures[0])["item_id"] == ITEM["item_id"]


def test_generate_one_retries_on_api_error_then_raises_runtime_error():
    error = anthropic.APIError(
        message="rate limited", request=None, body=None
    )
    client = _RaisingClient(error)

    try:
        generate_one(client, ITEM, CONFIG, max_retries=3)
        assert False, "expected RuntimeError"
    except RuntimeError:
        pass

    assert client.calls == 3


def test_run_logs_api_error_as_failure_and_continues(tmp_path):
    error = anthropic.APIError(message="rate limited", request=None, body=None)
    client = _RaisingClient(error)
    options = RunOptions(
        model="claude-sonnet-5",
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
        build_items_fn=lambda config, samples_per_cell, limit: [ITEM],
    )

    assert counts == {"generated": 0, "skipped": 0, "failed": 1}
    failures = (tmp_path / "failures.jsonl").read_text().splitlines()
    assert len(failures) == 1
