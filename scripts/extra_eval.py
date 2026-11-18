# Phân tích phụ: đánh giá best.pt và last.pt trên test đủ 100 ảnh và test bỏ 5 ảnh rò rỉ (trùng raw). Ghi vào submission/results/extra_eval.json. Chạy: .venv/Scripts/python scripts/extra_eval.py (cần đã chạy train_compare.py)
import json, shutil, sys
from pathlib import Path
from ultralytics import YOLO
ROOT = Path.cwd()
LEAK = {"test_009", "test_033", "test_039", "test_044", "test_085"}
names = "names:\n  0: car\n  1: person\n  2: truck\n  3: bus\n"
sets = {}
for tag, excl in [("test100", set()), ("test95", LEAK)]:
    d = ROOT / "work/extra" / tag
    if d.exists(): shutil.rmtree(d)
    (d / "images").mkdir(parents=True); (d / "labels").mkdir()
    for p in sorted((ROOT / "data/test/images").iterdir()):
        if p.stem in excl: continue
        shutil.copy2(p, d / "images" / p.name)
        shutil.copy2(ROOT / "data/test/labels" / f"{p.stem}.txt", d / "labels" / f"{p.stem}.txt")
    y = d / "data.yaml"; y.write_text(f"path: {d.resolve()}\ntrain: images\nval: images\ntest: images\n{names}")
    sets[tag] = (y, len(list((d / "images").iterdir())))
out = {}
for run in ["raw_seed0", "raw_seed1", "clean_seed0", "clean_seed1"]:
    for w in ["best", "last"]:
        m = YOLO(str(ROOT / f"work/train/runs/{run}/weights/{w}.pt"))
        for tag, (y, n) in sets.items():
            r = m.val(data=str(y), split="test", imgsz=416, device="cpu", plots=False, verbose=False, batch=16)
            out[f"{run}|{w}|{tag}"] = dict(n=n, map50=round(float(r.box.map50), 4), map50_95=round(float(r.box.map), 4))
            print(run, w, tag, out[f"{run}|{w}|{tag}"], flush=True)
(ROOT / "submission/results/extra_eval.json").write_text(json.dumps(out, indent=2))
