"""Loop v1 driver (Milestone 3): retrieval, patch rounds, stop rules.

  init                         seed round 1 of every sample on the list from its baseline attempt
  round <sample_id> <code.py>  score the next round (+ preview), print per-view IoU and the stop decision
  stop  <sample_id> <reason>   close a sample early (e.g. no_hypothesis) - reason is logged
  retrieve <sample_id>         3-5 closest SOLVED train examples (empty until train samples are solved)
  status                       per-sample table

Stop rules (spec section 5): pass bar (aligned IoU-min >= 0.98), 8 rounds used, or two consecutive
rounds each improving the best score by < 0.5 % (relative). Extra logged rule: no_hypothesis.
"""
from __future__ import annotations

import json
import re
import shutil
import sqlite3
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
import attempt  # noqa: E402
import preview  # noqa: E402

SKILL = "loop-v1"
PASS, MAX_ROUNDS, MIN_GAIN = 0.98, 8, 0.005
STATE_DIR = ROOT / "runs" / "loop_v1"   # one state file per sample: parallel rounds on different samples are safe
LIST = ROOT / "evals" / "baseline_list.txt"
SOLVED = ROOT / "runs" / "solved"   # train-sample solutions only (never held-out)


def load():
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    out = {}
    for f in sorted(STATE_DIR.glob("*.json")):
        d = json.loads(f.read_text())
        out[d["sample_id"]] = d
    return out


def save(s):
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    for sid, st in s.items():
        st["sample_id"] = sid
        (STATE_DIR / f"{key(sid)}.json").write_text(json.dumps(st, indent=1))


def key(sid):
    return sid.rsplit("/", 1)[1]


def subset(sid):
    return sid.split("/")[1]


def decide(hist):
    best = [max(hist[: i + 1]) for i in range(len(hist))]
    if best[-1] >= PASS:
        return "pass"
    if len(hist) >= MAX_ROUNDS:
        return "max_rounds"
    if len(best) >= 3:
        g1 = (best[-2] - best[-3]) / max(best[-3], 1e-9)
        g2 = (best[-1] - best[-2]) / max(best[-2], 1e-9)
        if g1 < MIN_GAIN and g2 < MIN_GAIN:
            return "plateau"
    return None


def init():
    s = load()
    con = sqlite3.connect(ROOT / "evals" / "manifest.sqlite")
    for sid in [l.strip() for l in open(LIST) if l.strip()]:
        if sid in s:
            continue
        att = ROOT / "runs" / "attempts" / key(sid)
        base = json.loads((att / "round_01" / "score.json").read_text())
        base["skill_version"] = SKILL
        con.execute("INSERT INTO attempts (sample_id, kind, round, skill_version, blender_version, score_json, created_at)"
                    " VALUES (?,?,?,?,?,?,?)", (sid, "attempt", 1, SKILL, base["blender_version"], json.dumps(base), time.time()))
        preview.make(str(att), str(att / "round_01"), subset(sid))
        shutil.copy(att / "attempt.py", att / "round_01" / "attempt.py")
        s[sid] = {"hist": [base["aligned"]["iou_min"]], "views": [[base["aligned"][f"iou_v{i}"] for i in range(4)]],
                  "stop": decide([base["aligned"]["iou_min"]])}
    con.commit()
    save(s)
    print(f"initialised {len(s)} samples")


def run_round(sid, code):
    s = load()
    st = s[sid]
    if st["stop"]:
        sys.exit(f"{sid} already stopped: {st['stop']}")
    rnd = len(st["hist"]) + 1
    res = attempt.score_attempt(sid, code, rnd, SKILL)
    al = res["aligned"]
    att = ROOT / "runs" / "attempts" / key(sid)
    if al.get("runs_clean"):
        preview.make(str(att), str(att / f"round_{rnd:02d}"), subset(sid))
    st["hist"].append(al.get("iou_min", 0.0))
    st["views"].append([al.get(f"iou_v{i}", 0.0) for i in range(4)])
    st["stop"] = decide(st["hist"])
    save({sid: st})
    print(json.dumps({"sample": key(sid), "round": rnd, "iou_min": al.get("iou_min"), "views": st["views"][-1],
                      "best": max(st["hist"]), "hist": st["hist"], "stop": st["stop"], "error": res.get("error")}))


def stop(sid, reason):
    s = load()
    s[sid]["stop"] = reason
    save({sid: s[sid]})


def retrieve(sid):
    cat = re.sub(r"(Factory)?(_\d+)?_geo$", "", key(sid))
    hits = sorted(SOLVED.glob(f"{cat}*.json")) if SOLVED.exists() else []
    print(json.dumps([json.loads(h.read_text()) for h in hits[:5]]))


def status():
    s = load()
    for sid, st in s.items():
        print(f"{key(sid):34s} r={len(st['hist'])} best={max(st['hist']):.4f} base={st['hist'][0]:.4f} stop={st['stop']}")


if __name__ == "__main__":
    cmd, *a = sys.argv[1:]
    {"init": lambda: init(), "round": lambda: run_round(*a), "stop": lambda: stop(*a),
     "retrieve": lambda: retrieve(*a), "status": lambda: status()}[cmd]()
