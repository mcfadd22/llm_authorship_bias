#!/usr/bin/env python3
"""Adjudication sheet for the aim-visibility flag (design.md 1c).

Shows each item's intended bug (flavour, rationale, contract, diff against the
clean twin) next to the contract-blind accounts: the model review(s) in
data/aim_review/ and, if given, the human aim-only CSV. The adjudicator decides
whether a blind account identifies the *intended* bug and assigns the flag:

  yes         the aim and code establish the intended violation without an
              unstated input-domain or output rule
  borderline  a plausible violation is visible, but it rests on a common
              convention or an ambiguous boundary
  no          only the hidden contract establishes it, or it is an inert
              artifact the aim does not prohibit

Items where the blind accounts give least support come first. Autosaves in the
browser; exports analysis/aim_visibility.csv-shaped rows.

    python analysis/build_aim_comparison.py --human ~/Downloads/aim_only_review.csv
"""
import argparse
import csv
import html
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "analysis"))
sys.path.insert(0, str(ROOT / "scripts"))
from build_aim_only_sheet import token  # noqa: E402
from build_item_review import diff_html, load  # noqa: E402

REVIEW_DIR = ROOT / "data" / "aim_review"


def load_reviews(review_dir, current=None):
    """{item_id: [(reviewer, issues), ...]} from every non-pilot reviewer file.

    With `current` ({item_id: prompt}), keep only reviews of the item's current
    code: a regenerated item keeps its item_id, and its old reviews stay in the
    file as history.
    """
    out = {}
    for path in sorted(Path(review_dir).glob("*.jsonl")):
        if path.name.startswith("pilot-"):
            continue
        with path.open() as fh:
            for line in fh:
                r = json.loads(line)
                if current is not None and current.get(r["item_id"]) != r["messages"][0]["content"]:
                    continue
                out.setdefault(r["item_id"], []).append((r["reviewer"], r["issues"]))
    return out


def support(reviews, human):
    """Sort key: 0 = no blind account found anything, 1 = only convention-based, 2 = stated."""
    bases = [i["basis"] for _, issues in reviews for i in issues]
    if human and human.get("found") == "yes":
        bases.append(human.get("basis") or "convention")
    if not bases:
        return 0
    return 2 if "stated" in bases else 1


def account_html(who, issues):
    if not issues:
        return f'<div class="acct"><b>{html.escape(who)}</b>: <i>no issue found</i></div>'
    rows = "".join(
        f'<li><span class="basis b-{html.escape(i["basis"])}">{html.escape(i["basis"])}</span> '
        f'<b>input:</b> {html.escape(i["input"])}<br><b>does:</b> {html.escape(i["code_does"])}'
        f'<br><b>should:</b> {html.escape(i["should_do"])}</li>' for i in issues)
    return f'<div class="acct"><b>{html.escape(who)}</b><ul>{rows}</ul></div>'


def human_html(h):
    if not h:
        return ""
    if h.get("found") != "yes":
        return f'<div class="acct"><b>human reviewer</b>: <i>no issue found</i> {html.escape(h.get("note", ""))}</div>'
    issue = {k: h.get(k, "") for k in ("input", "code_does", "should_do")}
    issue["basis"] = h.get("basis") or "unspecified"
    extra = f'<div class="mut">other: {html.escape(h["other"])}</div>' if h.get("other") else ""
    return account_html("human reviewer", [issue]) + extra


def review_html(v):
    """The contract-and-flavour review for this item, which is not blind to the contract."""
    if not v:
        return ""
    return (f'<p class="mut"><b>Contract review:</b> item {html.escape(v.get("verdict", ""))}, '
            f'twin {html.escape(v.get("twin_verdict", ""))}. {html.escape(v.get("note", ""))}</p>')


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--items-dir", type=Path, nargs="+",
                    default=[ROOT / "data" / "items_gpt5", ROOT / "data" / "items_gemini25pro"])
    ap.add_argument("--review-dir", type=Path, default=REVIEW_DIR)
    ap.add_argument("--human", type=Path, default=None, help="CSV exported from aim_only_review.html")
    ap.add_argument("--out", type=Path, default=ROOT / "analysis" / "aim_comparison.html")
    args = ap.parse_args(argv)

    rows = []
    for d in args.items_dir:
        rows += load(d, d.parent / f"{d.name}_clean")
    from run_aim_review import build_messages
    aims = {a["id"]: a for a in json.loads((ROOT / "config" / "stated_aims.json").read_text())["aims"]}
    reviews = load_reviews(args.review_dir,
                           {it["item_id"]: build_messages(it, aims)[0]["content"] for it in rows})
    humans = {}
    if args.human:
        by_token = {token(it["item_id"]): it["item_id"] for it in rows}
        with args.human.open() as fh:
            humans = {by_token[r["token"]]: r for r in csv.DictReader(fh) if r["token"] in by_token}
    verdicts = {}
    for path in sorted((ROOT / "analysis").glob("item_verdicts_*.csv")):
        with path.open() as fh:
            verdicts.update({r["item_id"]: r for r in csv.DictReader(fh)})
    rows.sort(key=lambda it: (support(reviews.get(it["item_id"], []), humans.get(it["item_id"])),
                              it["bug_flavor"], it["item_id"]))

    cards = []
    for n, it in enumerate(rows, 1):
        iid = html.escape(it["item_id"])
        accts = "".join(account_html(who, issues) for who, issues in reviews.get(it["item_id"], []))
        cards.append(f'''
<section class="card" data-item="{iid}">
  <header><span class="num">{n}</span> <code>{iid}</code>
    <span class="tag">{html.escape(it["bug_flavor"])}</span></header>
  <p><b>Aim (judge sees):</b> {html.escape(it["aim_text"])}</p>
  <p class="mut"><b>Contract (judge does not see):</b> {html.escape(it.get("contract") or "")}</p>
  <div class="code">{diff_html(it["code"], it["clean_code"])}</div>
  <p class="mut"><b>Intended bug:</b> {html.escape(it.get("rationale") or "")}</p>
  {review_html(verdicts.get(it["item_id"]))}
  <div class="blind">{accts}{human_html(humans.get(it["item_id"]))}</div>
  <div class="row">
    <label><input type="radio" name="f{n}" data-f="flag" value="yes"> yes</label>
    <label><input type="radio" name="f{n}" data-f="flag" value="borderline"> borderline</label>
    <label><input type="radio" name="f{n}" data-f="flag" value="no"> no</label>
    <input class="reason" data-f="reason" placeholder="reason (required for borderline / no)">
  </div>
</section>''')

    args.out.write_text(f'''<!doctype html><meta charset="utf-8">
<title>Aim-visibility adjudication — {len(rows)} items</title>
<style>
 :root {{ --bg:#fbfaf8; --fg:#1c1a17; --mut:#6b6560; --line:#e3ded7; --bug:#fdf0ed; --fix:#eef6ef; }}
 @media (prefers-color-scheme: dark) {{ :root {{ --bg:#171614; --fg:#eceae6; --mut:#9a938c;
   --line:#2f2c28; --bug:#2b1c17; --fix:#16241a; }} }}
 body {{ margin:0; background:var(--bg); color:var(--fg); font:14.5px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif }}
 .wrap {{ max-width:900px; margin:0 auto; padding:0 20px 120px }}
 header.top {{ position:sticky; top:0; background:var(--bg); border-bottom:1px solid var(--line);
   padding:12px 0; z-index:10; display:flex; gap:14px; align-items:center }}
 h1 {{ font-size:17px; margin:0 }} #prog {{ margin-left:auto; color:var(--mut); font-size:13px }}
 button {{ font:inherit; padding:5px 11px; border:1px solid var(--line); border-radius:6px;
   background:transparent; color:var(--fg); cursor:pointer }}
 .card {{ border:1px solid var(--line); border-radius:10px; padding:14px 16px; margin:14px 0 }}
 .num,.mut {{ color:var(--mut) }} .tag {{ font-size:11px; border:1px solid var(--line); border-radius:20px; padding:1px 8px; color:var(--mut) }}
 .code {{ font:12.5px/1.6 ui-monospace,SFMono-Regular,Menlo,monospace; border:1px solid var(--line);
   border-radius:7px; padding:8px 0; overflow-x:auto }}
 .ln {{ padding:0 12px; white-space:pre }} .ln.bug {{ background:var(--bug) }} .ln.fix {{ background:var(--fix) }}
 .g {{ color:var(--mut) }}
 .blind {{ border-left:3px solid var(--line); padding-left:10px; margin:10px 0 }}
 .acct ul {{ margin:4px 0 8px; padding-left:18px }} .acct li {{ margin-bottom:4px }}
 .basis {{ font-size:11px; border-radius:4px; padding:0 5px; border:1px solid var(--line) }}
 .row {{ display:flex; gap:14px; align-items:center; flex-wrap:wrap; border-top:1px solid var(--line); padding-top:10px }}
 .reason {{ flex:1; min-width:200px; font:inherit; padding:4px 8px; border:1px solid var(--line);
   border-radius:5px; background:transparent; color:var(--fg) }}
</style>
<div class="wrap">
<header class="top"><h1>Aim-visibility adjudication</h1>
  <button onclick="exportCsv()">Export CSV</button><span id="prog"></span></header>
<p class="mut">Decide whether a blind account identifies the <i>intended</i> bug, then flag.
<b>yes</b>: the aim and code establish the intended violation without an unstated input-domain or
output rule. <b>borderline</b>: a plausible violation is visible but rests on a common convention or
an ambiguous boundary. <b>no</b>: only the hidden contract establishes it, or it is an inert
artifact the aim does not prohibit. Undecided after discussion: take the stricter flag. Items with
the least blind support come first.</p>
{"".join(cards)}
</div>
<script>
const KEY='aim_comparison_v1', store=JSON.parse(localStorage.getItem(KEY)||'{{}}');
function save(){{ document.querySelectorAll('.card').forEach(c=>{{
  const f=c.querySelector('[data-f=flag]:checked');
  store[c.dataset.item]={{flag:f?f.value:'', reason:c.querySelector('[data-f=reason]').value}};
}}); localStorage.setItem(KEY,JSON.stringify(store)); prog(); }}
function prog(){{ document.getElementById('prog').textContent=
  Object.values(store).filter(r=>r.flag).length+' / {len(rows)} flagged'; }}
document.querySelectorAll('.card').forEach(c=>{{ const r=store[c.dataset.item]||{{}};
  c.querySelectorAll('[data-f=flag]').forEach(el=>el.checked=(el.value===r.flag));
  c.querySelector('[data-f=reason]').value=r.reason||''; }});
document.addEventListener('input',save); document.addEventListener('change',save); prog();
function exportCsv(){{ save(); const out=[['item_id','aim_visible','reason']];
  document.querySelectorAll('.card').forEach(c=>{{ const r=store[c.dataset.item]||{{}};
    out.push([c.dataset.item,r.flag||'',r.reason||'']); }});
  const csv=out.map(r=>r.map(f=>'"'+String(f).replace(/"/g,'""')+'"').join(',')).join('\\n');
  const a=document.createElement('a'); a.href=URL.createObjectURL(new Blob([csv],{{type:'text/csv'}}));
  a.download='aim_visibility.csv'; a.click(); }}
</script>''', encoding="utf-8")
    print(f"wrote {args.out} ({len(rows)} items, {sum(1 for r in rows if r['item_id'] in reviews)} with model reviews)")


if __name__ == "__main__":
    main()
