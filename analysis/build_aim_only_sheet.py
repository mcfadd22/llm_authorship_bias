#!/usr/bin/env python3
"""Contract-blind review sheet for a human reviewer who has not seen the contracts.

Shows each item exactly as a judge sees it under the `none` label -- the aim
sentence and the code -- and nothing else: no contract, flavour, rationale,
clean twin, generator or item_id. Items are shuffled across banks and flavours
with a fixed seed. The reviewer states, in their own words, the input on which
the code misbehaves, what it does, what it should do, and whether the aim
itself establishes that ("stated") or a convention or ambiguous boundary does
("convention"). Entries autosave in the browser and export as CSV
(design.md 1c). The sheet is self-contained, so it can be sent as one file.
Items are keyed by an opaque token, not item_id, which carries the flavour and
generator; build_aim_comparison.py maps tokens back.

    python analysis/build_aim_only_sheet.py
"""
import argparse
import hashlib
import html
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from run_aim_review import judge_view, load_items  # noqa: E402

FIELDS = ["found", "input", "code_does", "should_do", "basis", "other", "note"]
SEED = "20260927"


def token(item_id, seed=SEED):
    """Opaque per-item key: item_id carries flavour and generator, even in the page source."""
    return hashlib.sha256((seed + item_id).encode()).hexdigest()[:12]


def parse_args(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--items-dir", type=Path, nargs="+",
                    default=[ROOT / "data" / "items_gpt5", ROOT / "data" / "items_gemini25pro"])
    ap.add_argument("--out", type=Path, default=ROOT / "analysis" / "aim_only_review.html")
    ap.add_argument("--seed", default=SEED)
    ap.add_argument("--only", type=Path, default=None,
                    help="CSV with an item_id column (e.g. analysis/aim_audit_selection.csv): "
                         "build the sheet for these items only")
    return ap.parse_args(argv)


def card(it, n, aims, seed=SEED):
    aim, _, code = judge_view(it, aims).partition("\n\n")
    code = code.removeprefix("```python\n").removesuffix("\n```")
    iid = token(it["item_id"], seed)

    def text(field, label, rows=2):
        return (f'<label class="f">{label}<textarea data-f="{field}" rows="{rows}"></textarea></label>')
    return f'''
<section class="card" data-item="{iid}">
  <header><span class="num">{n}</span></header>
  <p class="aim">{html.escape(aim)}</p>
  <pre class="code">{html.escape(code)}</pre>
  <div class="row">
    <span class="q">Does the code do something wrong?</span>
    <label><input type="radio" name="found{n}" data-f="found" value="yes"> yes</label>
    <label><input type="radio" name="found{n}" data-f="found" value="no"> no</label>
  </div>
  {text("input", "Input or condition where it goes wrong")}
  {text("code_does", "What the code does")}
  {text("should_do", "What it should do instead")}
  <div class="row">
    <span class="q">What establishes the expected behaviour?</span>
    <label><input type="radio" name="basis{n}" data-f="basis" value="stated"> the description itself</label>
    <label><input type="radio" name="basis{n}" data-f="basis" value="convention"> a convention or ambiguous boundary</label>
  </div>
  {text("other", "Any other problems (optional)", 1)}
  {text("note", "Note (optional)", 1)}
</section>'''


def main(argv=None):
    args = parse_args(argv)
    aims = {a["id"]: a for a in json.loads((ROOT / "config" / "stated_aims.json").read_text())["aims"]}
    items = load_items(args.items_dir)
    if args.only:
        import csv
        with args.only.open() as fh:
            keep = {r["item_id"] for r in csv.DictReader(fh)}
        items = [it for it in items if it["item_id"] in keep]
    items.sort(key=lambda it: token(it["item_id"], args.seed))
    body = "".join(card(it, n, aims, args.seed) for n, it in enumerate(items, 1))
    fields = json.dumps(FIELDS)
    args.out.write_text(f'''<!doctype html><meta charset="utf-8">
<title>Code review — {len(items)} functions</title>
<style>
 :root {{ --bg:#fbfaf8; --fg:#1c1a17; --mut:#6b6560; --line:#e3ded7; }}
 @media (prefers-color-scheme: dark) {{ :root {{ --bg:#171614; --fg:#eceae6; --mut:#9a938c; --line:#2f2c28; }} }}
 * {{ box-sizing:border-box }}
 body {{ margin:0; background:var(--bg); color:var(--fg); font:15px/1.55 -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif }}
 .wrap {{ max-width:860px; margin:0 auto; padding:0 20px 120px }}
 header.top {{ position:sticky; top:0; background:var(--bg); border-bottom:1px solid var(--line);
   padding:14px 0; z-index:10; display:flex; gap:14px; align-items:center; flex-wrap:wrap }}
 h1 {{ font-size:17px; margin:0; font-weight:600 }}
 .meta,.num {{ color:var(--mut); font-size:13px }}
 button {{ font:inherit; padding:6px 12px; border:1px solid var(--line); border-radius:6px;
   background:transparent; color:var(--fg); cursor:pointer }}
 #prog {{ margin-left:auto; font-size:13px; color:var(--mut) }}
 .card {{ border:1px solid var(--line); border-radius:10px; padding:16px; margin:16px 0 }}
 .aim {{ margin:4px 0 10px }}
 .code {{ font:12.5px/1.65 ui-monospace,SFMono-Regular,Menlo,monospace; border:1px solid var(--line);
   border-radius:7px; padding:10px 12px; overflow-x:auto; margin:0 0 12px }}
 .row {{ display:flex; gap:14px; flex-wrap:wrap; align-items:center; margin:8px 0; font-size:13.5px }}
 .q {{ font-weight:600; font-size:13px }}
 .f {{ display:block; font-size:12.5px; color:var(--mut); margin:8px 0 0 }}
 textarea {{ display:block; width:100%; margin-top:3px; font:inherit; font-size:13.5px; padding:6px 8px;
   border:1px solid var(--line); border-radius:5px; background:transparent; color:var(--fg) }}
</style>
<div class="wrap">
<header class="top">
  <h1>Code review</h1>
  <span class="meta">{len(items)} functions · entries save in this browser automatically</span>
  <button onclick="exportCsv()">Export CSV</button>
  <span id="prog"></span>
</header>
<p class="meta">Each function comes with the one-sentence description a reviewer would get, and nothing
else. Using only the description and the code, say whether the code does something wrong. If it
does, give the input where it goes wrong, what it does, and what it should do instead, in your own
words. Only count behaviour as wrong if you can justify what it should do from the description, or
from a convention a typical reviewer would apply without being told. Don't assume a rule the
description doesn't state; if it doesn't say whether an input is valid or what should happen for
it, that isn't a bug. Style, comments, performance, and code with no effect on behaviour don't
count. "No" is a perfectly good answer.</p>
{body}
</div>
<script>
const FIELDS={fields}, KEY='aim_only_review_v1';
const store=JSON.parse(localStorage.getItem(KEY)||'{{}}');
function save(){{
  document.querySelectorAll('.card').forEach(c=>{{
    const r={{}};
    c.querySelectorAll('[data-f]').forEach(el=>{{
      if(el.type==='radio'){{ if(el.checked) r[el.dataset.f]=el.value; }}
      else r[el.dataset.f]=el.value;
    }});
    store[c.dataset.item]=r;
  }});
  localStorage.setItem(KEY,JSON.stringify(store)); prog();
}}
function load(){{
  document.querySelectorAll('.card').forEach(c=>{{
    const r=store[c.dataset.item]||{{}};
    c.querySelectorAll('[data-f]').forEach(el=>{{
      if(el.type==='radio') el.checked=(r[el.dataset.f]===el.value);
      else el.value=r[el.dataset.f]||'';
    }});
  }}); prog();
}}
function prog(){{
  const n=Object.values(store).filter(r=>r.found).length;
  document.getElementById('prog').textContent=n+' / {len(items)} answered';
}}
document.addEventListener('input',save); document.addEventListener('change',save);
function exportCsv(){{
  save();
  const out=[['token',...FIELDS]];
  document.querySelectorAll('.card').forEach(c=>{{
    const r=store[c.dataset.item]||{{}}; out.push([c.dataset.item,...FIELDS.map(f=>r[f]||'')]);
  }});
  const csv=out.map(r=>r.map(f=>'"'+String(f).replace(/"/g,'""')+'"').join(',')).join('\\n');
  const a=document.createElement('a');
  a.href=URL.createObjectURL(new Blob([csv],{{type:'text/csv'}}));
  a.download='aim_only_review.csv'; a.click();
}}
load();
</script>''', encoding="utf-8")
    print(f"wrote {args.out} ({len(items)} items)")


if __name__ == "__main__":
    main()
