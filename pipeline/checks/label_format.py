"""CHECK 2 — Dòng nhãn YOLO: sai định dạng, ID lớp lạ, box tràn ảnh, box rỗng, box lặp.   (Script 2 trong slide)   ★★

Test:  pytest tests/test_label_format.py -q

Mỗi dòng nhãn: `id cx cy w h` (5 số, toạ độ 0–1). Trả về list[Issue]; `Issue.line` = số dòng (đếm từ 1).

| code             | severity | khi nào                                                                  |
|------------------|----------|--------------------------------------------------------------------------|
| BAD_FORMAT       | ERROR    | không đúng 5 cột số (dùng `parse_yolo_line`, bắt `ValueError`)           |
| BAD_CLASS_ID     | ERROR    | id lớp ngoài 0..len(ds.classes)-1                                        |
| BOX_ZERO         | ERROR    | w <= 0 hoặc h <= 0                                                       |
| BOX_OUT_OF_IMAGE | ERROR    | mép box vượt [0,1] quá `cfg["label_format"]["overflow_tol"]`; extra={"overflow": mức tràn} |
| DUP_BOX          | ERROR    | cùng lớp với một dòng TRƯỚC ĐÓ và IoU > `dup_box_iou`; báo ở dòng SAU    |
| BOX_TINY         | WARN     | cạnh ngắn của box (px) < `min_box_px`  (cần `ds.image_size(stem)`)       |
| BOX_HUGE         | WARN     | w*h > `max_box_frac`                                                     |

Gợi ý
- Mép trái = x - w/2, mép phải = x + w/2 (xem câu hỏi "dòng YOLO nào lỗi?" trong slide).
- Một dòng hỏng (BAD_FORMAT, BAD_CLASS_ID, BOX_ZERO) thì `continue`, đừng kiểm tiếp hình học của dòng đó.
- Dòng thiếu cột làm script của slide dừng giữa chừng: đây là lý do phải `try/except`.
- `iou_xywh(a, b)` có sẵn trong common.py.
- Ngưỡng nằm trong `cfg["label_format"]` — đừng viết cứng số vào code.
"""
from ..common import ERROR, WARN, Issue, iou_xywh, parse_yolo_line  # noqa: F401


CHECK = "label_format"


def _stems(ds):
    """Ảnh có file nhãn + file nhãn mồ côi (vẫn kiểm cú pháp), theo thứ tự tên -> kết quả tái lập."""
    imgs = {p.stem for p in ds.image_files()}
    labs = {p.stem for p in ds.label_files()}
    return sorted(imgs | labs)


def check_file(ds, stem, cfg):
    lf = cfg["label_format"]
    tol, min_px, max_frac, dup_iou = lf["overflow_tol"], lf["min_box_px"], lf["max_box_frac"], lf["dup_box_iou"]
    n_cls = len(ds.classes)
    lines = ds.read_label_lines(stem)
    if not lines:                                 # không có file / file rỗng: missing_labels báo
        return []
    size = ds.image_size(stem)                    # None nếu không có ảnh / ảnh hỏng -> bỏ qua BOX_TINY
    issues, kept = [], []                         # kept: (số dòng, box) các dòng hợp lệ trước đó, để tìm DUP_BOX
    for no, text in lines:
        try:
            c, x, y, w, h = parse_yolo_line(text)
        except ValueError as e:
            issues.append(Issue(CHECK, ERROR, "BAD_FORMAT", stem, f"dòng không đúng 5 cột số: {e}", no, {"text": text.strip()[:60]}))
            continue
        if not 0 <= c < n_cls:
            issues.append(Issue(CHECK, ERROR, "BAD_CLASS_ID", stem, f"id lớp {c} ngoài 0..{n_cls - 1}", no, {"class_id": c}))
            continue
        if w <= 0 or h <= 0:
            issues.append(Issue(CHECK, ERROR, "BOX_ZERO", stem, f"box rộng/cao <= 0 (w={w}, h={h})", no))
            continue
        overflow = max(0.0, -(x - w / 2), (x + w / 2) - 1, -(y - h / 2), (y + h / 2) - 1)
        if overflow > tol:
            issues.append(Issue(CHECK, ERROR, "BOX_OUT_OF_IMAGE", stem, f"box tràn ảnh {overflow:.4f} > {tol}", no, {"overflow": round(overflow, 6)}))
        box = (x, y, w, h)
        dup = next((pno for pno, (pc, pb) in kept if pc == c and iou_xywh(pb, box) > dup_iou), None)
        if dup is not None:
            issues.append(Issue(CHECK, ERROR, "DUP_BOX", stem, f"lặp box dòng {dup} (cùng lớp, IoU > {dup_iou})", no, {"of_line": dup}))
        kept.append((no, (c, box)))               # mọi dòng hợp lệ (kể cả dòng lặp) là "dòng trước đó" của các dòng sau: A≈B≈C báo cả B và C
        if size:
            W, H = size
            short = min(w * W, h * H)
            if short < min_px:
                issues.append(Issue(CHECK, WARN, "BOX_TINY", stem, f"cạnh ngắn {short:.1f}px < {min_px}px", no, {"short_px": round(short, 1)}))
        if w * h > max_frac:
            issues.append(Issue(CHECK, WARN, "BOX_HUGE", stem, f"box phủ {w * h:.2f} ảnh > {max_frac}", no, {"area_frac": round(w * h, 4)}))
    return issues


def run(ds, cfg):
    issues = []
    for stem in _stems(ds):
        issues.extend(check_file(ds, stem, cfg))
    return issues
