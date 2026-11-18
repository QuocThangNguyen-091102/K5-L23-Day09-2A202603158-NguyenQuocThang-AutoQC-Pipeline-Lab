"""CHECK THƯỞNG — box có tỉ lệ khung hình (tính theo PIXEL) bất thường.   (RUBRIC: "+3 thêm một check mới")

Test:  pytest tests/test_box_aspect.py -q
Chạy:  python -m pipeline.checks.box_aspect --src work/run/ds        # in "tên file, số dòng, lý do"

Vì sao: box "que diêm" (rất mảnh, ví dụ 3 px × 200 px) thường là box vẽ hỏng / kéo nhầm, nhưng KHÔNG bị bắt bởi
BOX_ZERO (w,h > 0), BOX_TINY (chỉ xét cạnh ngắn < 12 px nên bỏ qua que dài 13 px) hay BOX_HUGE. Tỉ lệ phải tính theo
pixel, không theo toạ độ chuẩn hoá: w=h=0.2 trên ảnh 640×480 là 128×96 px (tỉ lệ 1.33), không phải 1.0.

| code            | severity | khi nào                                                          |
|-----------------|----------|------------------------------------------------------------------|
| BOX_ODD_ASPECT  | WARN     | max(w_px/h_px, h_px/w_px) > max_ratio; extra={"ratio", "size_px"} |

- Chỉ CẢNH BÁO (người đứng thẳng xa camera có thể mảnh thật): việc của người.
- Ngưỡng đọc từ `cfg["box_aspect"]["max_ratio"]` nếu có; `configs/pipeline.yaml` của lab bị ghim (không thêm khoá được)
  nên khi thiếu thì dùng `DEFAULT_MAX_RATIO`.
- Dòng hỏng / id lạ / box rỗng / ảnh không mở được: bỏ qua (label_format, images đã báo), không làm script chết.
- Không đăng ký vào `QC_CHECKS` vì `pipeline/checks/__init__.py` được ghim sha1.
"""
from __future__ import annotations

import argparse
import sys

from ..common import WARN, Issue, parse_yolo_line

CHECK = "box_aspect"
DEFAULT_MAX_RATIO = 15.0          # person đứng ~ 1:3–1:4; 1:15 trở lên gần như chắc là box hỏng


def max_ratio_from(cfg) -> float:
    return float((cfg.get("box_aspect") or {}).get("max_ratio", DEFAULT_MAX_RATIO))


def run(ds, cfg):
    max_ratio = max_ratio_from(cfg)
    issues = []
    for p in ds.image_files():
        stem = p.stem
        lines = ds.read_label_lines(stem)
        if not lines:
            continue
        size = ds.image_size(stem)
        if not size:
            continue
        W, H = size
        for no, text in lines:
            try:
                c, _, _, w, h = parse_yolo_line(text)
            except ValueError:
                continue
            if not 0 <= c < len(ds.classes) or w <= 0 or h <= 0:
                continue
            wp, hp = w * W, h * H
            ratio = max(wp / hp, hp / wp)
            if ratio > max_ratio:
                issues.append(Issue(CHECK, WARN, "BOX_ODD_ASPECT", stem,
                                    f"box {ds.classes[c]} {wp:.0f}×{hp:.0f}px, tỉ lệ {ratio:.1f} > {max_ratio:g}",
                                    no, {"ratio": round(ratio, 2), "size_px": [round(wp, 1), round(hp, 1)]}))
    return issues


def main(argv=None):
    from ..common import ROOT, Dataset, load_config
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--src", default="work/run/ds")
    ap.add_argument("--config", default="configs/pipeline.yaml")
    ap.add_argument("--max-ratio", type=float, help="ghi đè ngưỡng (thí nghiệm)")
    a = ap.parse_args(argv)
    cfg = load_config(ROOT / a.config)
    if a.max_ratio is not None:
        cfg["box_aspect"] = {"max_ratio": a.max_ratio}
    ds = Dataset(ROOT / a.src, cfg["classes"])
    iss = run(ds, cfg)
    print(f"ảnh đã quét: {len(ds.image_files())} | ngưỡng tỉ lệ: {max_ratio_from(cfg):g} | {len(iss)} cảnh báo")
    for i in iss:
        print(f"{i.image}.txt:{i.line}  {i.code}  {i.message}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
