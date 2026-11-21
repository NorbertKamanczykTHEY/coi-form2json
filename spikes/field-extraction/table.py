"""out/results.jsonl -> markdown table (last record per form x model)."""
import json
from pathlib import Path

recs = {}
for line in (Path(__file__).parent / "out/results.jsonl").read_text().splitlines():
    r = json.loads(line)
    recs[(r["model"], r["form"], r.get("run", "1"))] = r
print("| Model | Form | Run | Schema (repairs) | Recall | Types | Options | show_if | Repeat | Extra | Gate ok / coverage | Review | s | $ |")
print("|---|---|---|---|---|---|---|---|---|---|---|---|---|---|")
for (m, f, run), r in sorted(recs.items()):
    s, g = r.get("score", {}), r.get("gate", {})
    print(f"| {m.split('/')[-1]} | {f} | {run} | {'ok' if r.get('schema_ok') else 'FAIL'} ({r.get('repairs', 0)}) | {s.get('recall', '-')} | {s.get('type_acc', '-')} | "
          f"{s.get('option_recall', '-')} | {s.get('show_if', '-')} | {s.get('repeating', '-')} | {s.get('extra', '-')} | "
          f"{g.get('ok', '-')} / {g.get('coverage', '-')} | {len(g.get('needs_review', []))} | {r['secs']} | {r['cost']} |")
tot = {}
for (m, _, _), r in recs.items():
    tot.setdefault(m, [0, 0])
    tot[m][0] += r["cost"]
    tot[m][1] += r["secs"]
print("\n" + "\n".join(f"- {m}: ${c:.4f}, {s:.0f}s total" for m, (c, s) in sorted(tot.items())))
