#!/usr/bin/env python3
"""Build a single self-contained HTML review sheet for one or more item banks.

Each item is shown with its declared bug_flavor/severity_tier, the generator's
rationale, and a minimal-pair diff against its bug-free twin in data/items_clean/
-- the diff is what makes "is the planted bug actually what it says it is"
checkable at a glance. Verdicts are recorded in-page and exported as CSV.

    python analysis/build_item_review.py

Several banks can share one sheet. With --blind the item_id (which carries the
generator tag) is hidden and cards are shuffled within each flavour, so the
reviewer does not know which generator wrote an item. --only-unreviewed skips
items that already have a verdict in any --verdicts file:

    python analysis/build_item_review.py --blind --only-unreviewed \
        --items-dir data/items_gpt5 data/items_gemini25pro \
        --verdicts analysis/item_verdicts_gpt5.csv --out analysis/item_review_pending.html

Merge the exported CSV back with analysis/merge_verdicts.py.
"""
import argparse
import csv
import difflib
import hashlib
import html
import json
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def parse_args(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--items-dir", type=Path, nargs="+", default=[ROOT / "data" / "items"])
    ap.add_argument("--clean-dir", type=Path, default=None,
                    help="defaults to <items-dir>_clean; only with a single --items-dir")
    ap.add_argument("--out", type=Path, default=None,
                    help="defaults to analysis/item_review_<bank>[+<bank>...].html")
    ap.add_argument("--verdicts", type=Path, nargs="+", default=[],
                    help="CSVs of existing verdicts to pre-load, so the sheet "
                         "reflects a completed review and can be revised")
    ap.add_argument("--only-unreviewed", action="store_true",
                    help="omit items that already have an item verdict in --verdicts")
    ap.add_argument("--also", nargs="+", default=[],
                    help="item_ids to include even though they have a verdict, e.g. to "
                         "re-check them after their contract changed; the prior verdict is pre-loaded")
    ap.add_argument("--blind", action="store_true",
                    help="hide item_id and shuffle within flavour, so the "
                         "generator is not visible")
    args = ap.parse_args(argv)
    if args.clean_dir and len(args.items_dir) > 1:
        ap.error("--clean-dir needs a single --items-dir")
    return args


def load(ITEMS, CLEAN):
    aims = {a["id"]: a for a in json.loads((ROOT / "config" / "stated_aims.json").read_text())["aims"]}
    flavors = {f["id"]: f for f in json.loads((ROOT / "config" / "bug_flavor.json").read_text())["levels"]}
    rows = []
    for p in sorted(ITEMS.glob("*.json")):
        item = json.loads(p.read_text())
        twin = CLEAN / p.name
        item["clean_code"] = json.loads(twin.read_text())["code"] if twin.exists() else None
        item["fix_rationale"] = json.loads(twin.read_text()).get("fix_rationale") if twin.exists() else None
        aim = aims.get(item["aim_id"], {})
        item["aim_text"] = aim.get("text") or aim.get("aim") or item["aim_id"]
        item["contract"] = aim.get("contract", "")
        item["flavor_def"] = (flavors.get(item["bug_flavor"], {}) or {}).get("definition", "")
        rows.append(item)
    return rows


def diff_html(buggy, clean):
    """Buggy code with lines that differ from the clean twin marked."""
    b, c = buggy.splitlines(), (clean or "").splitlines()
    if not clean:
        return "".join(f'<div class="ln"><span class="g">  </span>{html.escape(l) or "&nbsp;"}</div>' for l in b)
    sm = difflib.SequenceMatcher(None, c, b)
    out = []
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag in ("replace", "insert"):
            for l in b[j1:j2]:
                out.append(f'<div class="ln bug"><span class="g">- </span>{html.escape(l) or "&nbsp;"}</div>')
            for l in c[i1:i2]:
                out.append(f'<div class="ln fix"><span class="g">+ </span>{html.escape(l) or "&nbsp;"}</div>')
        elif tag == "delete":
            for l in c[i1:i2]:
                out.append(f'<div class="ln fix"><span class="g">+ </span>{html.escape(l) or "&nbsp;"}</div>')
        else:
            for l in b[j1:j2]:
                out.append(f'<div class="ln"><span class="g">  </span>{html.escape(l) or "&nbsp;"}</div>')
    return "".join(out)


def _severity_tag(it):
    tier = it.get("severity_tier")
    if tier:
        return f'<span class="tag tier t-{html.escape(tier)}">{html.escape(tier)}</span>'
    expected = " / ".join(it.get("expected_severity_tiers") or ["?"])
    return f'<span class="tag tier open">severity open: {html.escape(expected)}</span>'


def card(it, n, prior=None, blind=False):
    changed = "" if it["clean_code"] else '<span class="warn">no clean twin</span>'
    iid = html.escape(it["item_id"])
    prior = prior or {}
    v, tv = prior.get("verdict", ""), prior.get("twin_verdict", "")
    note = html.escape(prior.get("note", ""))

    def chk(name, value):
        return " checked" if name == value else ""
    return f'''
<section class="card" data-flavor="{html.escape(it['bug_flavor'])}" data-tier="{html.escape(it.get('severity_tier') or 'open')}" id="i{n}">
  <header>
    <span class="num">{n}</span>
    {"" if blind else f'<code class="iid">{iid}</code>'}
    <span class="tag flavor">{html.escape(it['bug_flavor'])}</span>
    {_severity_tag(it)}
    {changed}
  </header>
  <p class="aim"><strong>Stated aim:</strong> {html.escape(it['aim_text'])}</p>
  <p class="contract"><strong>Contract:</strong> {html.escape(it.get('contract') or '(none)')}</p>
  <div class="code">{diff_html(it['code'], it['clean_code'])}</div>
  <details><summary>Generator rationale &amp; flavor definition</summary>
    <p class="rat">{html.escape(it.get('rationale') or '')}</p>
    <p class="fix"><strong>Twin fix:</strong> {html.escape(it.get('fix_rationale') or '—')}</p>
    <p class="def"><strong>Declared flavor means:</strong> {html.escape(it['flavor_def'])}</p>
  </details>
  <div class="verdict" data-item="{iid}">
    <span class="vlabel">item</span>
    <label><input type="radio" name="v{n}" value="ok"{chk("ok", v)}> ok</label>
    <label><input type="radio" name="v{n}" value="wrong_flavor"{chk("wrong_flavor", v)}> wrong flavor</label>
    <label><input type="radio" name="v{n}" value="wrong_tier"{chk("wrong_tier", v)}> wrong tier</label>
    <label><input type="radio" name="v{n}" value="not_a_bug"{chk("not_a_bug", v)}> not a real bug</label>
    <label><input type="radio" name="v{n}" value="violates_contract"{chk("violates_contract", v)}> breaks contract elsewhere</label>
    <label><input type="radio" name="v{n}" value="drop"{chk("drop", v)}> drop</label>
  </div>
  <div class="verdict twin" data-twin="{iid}">
    <span class="vlabel">twin</span>
    <label><input type="radio" name="t{n}" value="ok"{chk("ok", tv)}> clean</label>
    <label><input type="radio" name="t{n}" value="twin_not_clean"{chk("twin_not_clean", tv)}> has another flaw</label>
    <label><input type="radio" name="t{n}" value="twin_breaks_contract"{chk("twin_breaks_contract", tv)}> breaks the contract</label>
    <label><input type="radio" name="t{n}" value="twin_not_minimal"{chk("twin_not_minimal", tv)}> changes too much</label>
    <input class="note" type="text" placeholder="note (optional)" value="{note}">
  </div>
</section>'''


def main(argv=None):
    args = parse_args(argv)
    rows = []
    for items_dir in args.items_dir:
        clean_dir = args.clean_dir or items_dir.parent / f"{items_dir.name}_clean"
        rows += load(items_dir, clean_dir)
    names = "+".join(d.name for d in args.items_dir)
    out_path = args.out or ROOT / "analysis" / f"item_review_{names}.html"

    prior = {}
    for path in args.verdicts:
        with path.open() as fh:
            prior.update({r["item_id"]: r for r in csv.DictReader(fh)})
    if args.only_unreviewed:
        also = set(args.also)
        rows = [r for r in rows
                if r["item_id"] in also or not (prior.get(r["item_id"]) or {}).get("verdict")]

    def order(r):
        if args.blind:
            # a stable shuffle: item_id order would group each generator's items
            return (r.get("severity_tier") or "~open",
                    hashlib.sha256(r["item_id"].encode()).hexdigest())
        return (r.get("severity_tier") or "~open", r["item_id"])

    by_flavor = defaultdict(list)
    for r in rows:
        by_flavor[r["bug_flavor"]].append(r)

    n, body = 0, []
    for flavor in sorted(by_flavor):
        group = sorted(by_flavor[flavor], key=order)
        body.append(f'<h2 class="fh">{html.escape(flavor)} <span class="cnt">{len(group)} items</span></h2>')
        for it in group:
            n += 1
            body.append(card(it, n, prior.get(it['item_id']), blind=args.blind))

    tiers = defaultdict(int)
    for r in rows:
        tiers[r.get("severity_tier") or "severity open"] += 1
    summary = " · ".join(f"{k}: {v}" for k, v in sorted(tiers.items()))
    missing = sum(1 for r in rows if not r["clean_code"])

    out_path.write_text(f'''<!doctype html><meta charset="utf-8">
<title>Item bank review — {len(rows)} items</title>
<style>
 :root {{ --bg:#fbfaf8; --fg:#1c1a17; --mut:#6b6560; --line:#e3ded7;
          --bug:#fdf0ed; --bugl:#c2410c; --fix:#eef6ef; --fixl:#15803d; }}
 @media (prefers-color-scheme: dark) {{ :root {{ --bg:#171614; --fg:#eceae6; --mut:#9a938c;
          --line:#2f2c28; --bug:#2b1c17; --bugl:#f19d76; --fix:#16241a; --fixl:#86c99a; }} }}
 * {{ box-sizing:border-box }}
 body {{ margin:0; background:var(--bg); color:var(--fg); font:15px/1.55 -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif; }}
 .wrap {{ max-width:900px; margin:0 auto; padding:0 20px 120px }}
 header.top {{ position:sticky; top:0; background:var(--bg); border-bottom:1px solid var(--line);
   padding:14px 0; z-index:10; display:flex; gap:14px; align-items:center; flex-wrap:wrap }}
 h1 {{ font-size:17px; margin:0; font-weight:600 }}
 .meta {{ color:var(--mut); font-size:13px }}
 button {{ font:inherit; padding:6px 12px; border:1px solid var(--line); border-radius:6px;
   background:transparent; color:var(--fg); cursor:pointer }}
 button:hover {{ border-color:var(--mut) }}
 #prog {{ margin-left:auto; font-variant-numeric:tabular-nums; font-size:13px; color:var(--mut) }}
 h2.fh {{ font-size:14px; text-transform:uppercase; letter-spacing:.06em; color:var(--mut);
   margin:40px 0 12px; padding-bottom:6px; border-bottom:1px solid var(--line) }}
 .cnt {{ text-transform:none; letter-spacing:0 }}
 .card {{ border:1px solid var(--line); border-radius:10px; padding:16px; margin:0 0 16px }}
 .card header {{ display:flex; gap:9px; align-items:center; flex-wrap:wrap; margin-bottom:9px }}
 .num {{ color:var(--mut); font-size:12px; font-variant-numeric:tabular-nums; min-width:22px }}
 .iid {{ font-size:12.5px; color:var(--fg) }}
 .tag {{ font-size:11px; padding:2px 8px; border-radius:20px; border:1px solid var(--line); color:var(--mut) }}
 .t-significant {{ border-color:var(--bugl); color:var(--bugl) }}
 .warn {{ font-size:11px; color:var(--bugl) }}
 .aim {{ margin:0 0 10px; font-size:13.5px; color:var(--mut) }}
 .code {{ font:12.5px/1.65 ui-monospace,SFMono-Regular,Menlo,monospace; border:1px solid var(--line);
   border-radius:7px; padding:10px 0; overflow-x:auto; background:color-mix(in srgb,var(--fg) 3%,transparent) }}
 .ln {{ padding:0 12px; white-space:pre }}
 .ln.bug {{ background:var(--bug) }} .ln.fix {{ background:var(--fix) }}
 .g {{ color:var(--mut); user-select:none }}
 .ln.bug .g {{ color:var(--bugl) }} .ln.fix .g {{ color:var(--fixl) }}
 details {{ margin:10px 0 0; font-size:13.5px }}
 summary {{ cursor:pointer; color:var(--mut); font-size:12.5px }}
 details p {{ margin:8px 0 0 }} .def,.fix {{ color:var(--mut); font-size:12.5px }}
 .verdict {{ display:flex; gap:12px; align-items:center; flex-wrap:wrap; margin-top:12px;
   padding-top:11px; border-top:1px solid var(--line); font-size:12.5px }}
 .verdict label {{ cursor:pointer; color:var(--mut) }}
 .verdict.twin {{ border-top:1px dashed var(--line) }}
 .vlabel {{ font-size:10.5px; text-transform:uppercase; letter-spacing:.07em;
   color:var(--mut); min-width:34px }}
 .contract {{ margin:0 0 10px; font-size:13px; color:var(--fg);
   border-left:2px solid var(--line); padding-left:9px }}
 .tag.open {{ border-style:dashed }}
 .verdict input[type=radio] {{ margin-right:4px }}
 .note {{ flex:1; min-width:160px; font:inherit; font-size:12.5px; padding:4px 8px;
   border:1px solid var(--line); border-radius:5px; background:transparent; color:var(--fg) }}
 .card:has(input:checked) {{ border-color:var(--mut) }}
</style>
<div class="wrap">
<header class="top">
  <h1>Item bank review</h1>
  <span class="meta">{len(rows)} items · {summary}{' · ' + str(missing) + ' missing twin' if missing else ''}</span>
  <button onclick="exportCsv()">Export verdicts CSV</button>
  <span id="prog">0 / {len(rows)} reviewed</span>
</header>
<p class="meta">Lines marked <span style="color:var(--bugl)">−</span> are the planted bug; <span style="color:var(--fixl)">+</span> is the clean twin's fix.
Check each item against its declared flavor and tier. Verdicts stay in this page until exported.</p>
{''.join(body)}
</div>
<script>
const upd=()=>document.getElementById('prog').textContent=
  document.querySelectorAll('.verdict input[type=radio]:checked').length+' / {len(rows)} reviewed';
document.addEventListener('change',upd);
function exportCsv(){{
  const out=[['item_id','verdict','twin_verdict','note']];
  document.querySelectorAll('.verdict[data-item]').forEach(v=>{{
    const t=document.querySelector('.verdict.twin[data-twin="'+v.dataset.item+'"]');
    const c=v.querySelector('input[type=radio]:checked');
    const tc=t?t.querySelector('input[type=radio]:checked'):null;
    out.push([v.dataset.item, c?c.value:'', tc?tc.value:'', t?t.querySelector('.note').value:'']);
  }});
  const csv=out.map(r=>r.map(f=>'"'+String(f).replace(/"/g,'""')+'"').join(',')).join('\\n');
  const a=document.createElement('a');
  a.href=URL.createObjectURL(new Blob([csv],{{type:'text/csv'}}));
  a.download='item_verdicts.csv'; a.click();
}}
</script>''', encoding="utf-8")
    print(f"wrote {out_path}  ({len(rows)} items, {summary}, {missing} missing twins)")


if __name__ == "__main__":
    main()
