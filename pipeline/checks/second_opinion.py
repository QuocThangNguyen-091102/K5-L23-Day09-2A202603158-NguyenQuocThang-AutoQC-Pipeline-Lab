"""CHECK 6 — Ý kiến thứ hai: so nhãn với một model LỚN HƠN (yolo26l).   ★★★ (khó nhất, đáng điểm nhất)

Test:  pytest tests/test_second_opinion.py -q

Máy kiểm quy tắc, người kiểm ý nghĩa (slide). Các lỗi như thiếu nhãn / gán nhầm lớp hợp lệ / box lỏng
KHÔNG bắt được bằng quy tắc cú pháp. Ta nhờ một model mạnh hơn "nhìn lại" và CHỈ CẢNH BÁO (model cũng có thể sai):
những ảnh bị cờ sẽ vào hàng đợi cho NGƯỜI duyệt.

`preds[stem]` = list `[id_lớp, conf, cx, cy, w, h]` của model (lấy qua `get_preds(ds, cfg, "checker")` nếu preds=None).
`L = ds.valid_boxes(stem)` = list `(id_lớp, cx, cy, w, h)` của nhãn (đã bỏ dòng hỏng).
Ngưỡng ở `cfg["second_opinion"]`: conf, min_area_px, fp_conf, iou_missing, iou_match, iou_loose.

Thuật toán gợi ý, với từng ảnh (bỏ qua ảnh không có trong preds hoặc không có file nhãn):
  P = dự đoán có conf >= conf  VÀ diện tích px (w*W * h*H) >= min_area_px
  Với mỗi dự đoán r trong P: lấy các nhãn có IoU(r, nhãn) >= iou_missing  (cands)
   - không có cands                            -> POSSIBLE_MISSING     (model thấy vật mà nhãn không có box)
   - có cands cùng lớp, tốt nhất IoU < iou_loose -> POSSIBLE_LOOSE_BOX  (đúng vật, box lỏng/lệch)
   - không có cands cùng lớp, nhưng cands tốt nhất IoU >= iou_match (khác lớp) -> POSSIBLE_WRONG_CLASS
  Với mỗi dòng nhãn hợp lệ: nếu IoU với MỌI dự đoán (conf >= fp_conf, không lọc diện tích) đều < iou_missing
                                             -> POSSIBLE_FALSE_POS  (box nhãn không khớp vật nào model thấy; Issue.line = số dòng)

Chi tiết các ca biên (test kiểm đúng các ca này)
- `cands` gồm nhãn MỌI lớp có IoU >= iou_missing; "tốt nhất cùng lớp" = cands cùng lớp có IoU lớn nhất; "tốt nhất khác lớp" tương tự với cands khác lớp.
- Thứ tự quyết định cho mỗi dự đoán: (1) cands rỗng -> MISSING. (2) có cands cùng lớp: IoU tốt nhất < iou_loose -> LOOSE_BOX, ngược lại KHÔNG cờ
  (nhãn đúng lớp đã phủ vật này, kể cả khi còn nhãn khác lớp chồng lên). (3) không có cands cùng lớp: nếu IoU tốt nhất khác lớp >= iou_match -> WRONG_CLASS;
  nếu chỉ có khác lớp với IoU trong [iou_missing, iou_match) -> không cờ gì (mơ hồ: để cho FALSE_POS / lần duyệt khác).
- Một dự đoán sinh tối đa MỘT issue (MISSING / LOOSE_BOX / WRONG_CLASS); một ảnh có thể có nhiều issue.
- Thứ tự issue: theo `ds.image_files()` rồi theo thứ tự dự đoán trong `preds[stem]`, cuối cùng là các FALSE_POS theo số dòng; `Issue.image` = stem, `Issue.line` chỉ đặt cho FALSE_POS.

Lưu ý số dòng: dùng `ds.read_label_lines(stem)` (giữ số dòng gốc, kể cả dòng hỏng/trống) để lấy `Issue.line`; `valid_boxes` KHÔNG giữ số dòng.

Tất cả severity WARN; `Issue.extra` nên có {"conf": ...} hoặc {"iou": ...} (hàng đợi duyệt dùng conf để xếp ưu tiên).

Gợi ý
- `iou_xywh` có sẵn. Dòng nhãn hỏng không được làm script chết (dùng `ds.valid_boxes` và `parse_yolo_line` trong try).
- Kết quả phụ thuộc mạnh vào ngưỡng: calibrate chúng ở Bước 3 thay vì đoán.
"""
from ..common import WARN, Issue, iou_xywh, parse_yolo_line  # noqa: F401
from ..model_cache import get_preds  # noqa: F401


CHECK = "second_opinion"


def _labels(ds, stem):
    """[(số dòng gốc, id lớp, (cx, cy, w, h))] các dòng parse được, id lớp hợp lệ (giống ds.valid_boxes nhưng GIỮ số dòng)."""
    out = []
    for no, text in ds.read_label_lines(stem) or []:
        try:
            c, x, y, w, h = parse_yolo_line(text)
        except ValueError:
            continue                              # dòng hỏng: label_format báo
        if 0 <= c < len(ds.classes):
            out.append((no, c, (x, y, w, h)))
    return out


def _name(ds, c):
    return ds.classes[c] if 0 <= c < len(ds.classes) else str(c)


def check_image(ds, stem, rows, cfg):
    so = cfg["second_opinion"]
    conf_min, min_area, fp_conf = so["conf"], so["min_area_px"], so["fp_conf"]
    iou_missing, iou_match, iou_loose = so["iou_missing"], so["iou_match"], so["iou_loose"]
    size = ds.image_size(stem)
    if not size:
        return []
    W, H = size
    labels = _labels(ds, stem)
    preds = []
    for r in rows:
        try:
            c, s, x, y, w, h = int(r[0]), float(r[1]), *map(float, r[2:6])
        except (TypeError, ValueError, IndexError):
            continue
        preds.append((c, s, (x, y, w, h)))

    issues = []
    # (a) dự đoán tin cậy, đủ lớn -> nhãn có thiếu / lỏng / nhầm lớp?
    for c, s, box in preds:
        if s < conf_min or box[2] * W * box[3] * H < min_area:
            continue
        cands = [(iou_xywh(box, lb), lc, no) for no, lc, lb in labels]
        cands = [t for t in cands if t[0] >= iou_missing]
        if not cands:
            issues.append(Issue(CHECK, WARN, "POSSIBLE_MISSING", stem,
                                f"model thấy {_name(ds, c)} (conf {s:.2f}) mà nhãn không có box nào khớp",
                                extra={"conf": round(s, 4), "pred_class": c, "box": [round(v, 4) for v in box]}))
            continue
        same = [t for t in cands if t[1] == c]
        if same:
            best = max(same)
            if best[0] < iou_loose:
                issues.append(Issue(CHECK, WARN, "POSSIBLE_LOOSE_BOX", stem,
                                    f"box {_name(ds, c)} dòng {best[2]} lệch/lỏng so với model (IoU {best[0]:.2f} < {iou_loose})",
                                    extra={"conf": round(s, 4), "iou": round(best[0], 4), "label_line": best[2]}))
            continue                              # nhãn cùng lớp đã phủ vật này
        best = max(cands)
        if best[0] >= iou_match:
            issues.append(Issue(CHECK, WARN, "POSSIBLE_WRONG_CLASS", stem,
                                f"dòng {best[2]} gán {_name(ds, best[1])}, model nói {_name(ds, c)} (conf {s:.2f}, IoU {best[0]:.2f})",
                                extra={"conf": round(s, 4), "iou": round(best[0], 4), "label_line": best[2],
                                       "label_class": best[1], "pred_class": c}))
        # chỉ khác lớp với IoU trong [iou_missing, iou_match): mơ hồ -> không cờ

    # (b) box nhãn không khớp vật nào model thấy (dự đoán conf >= fp_conf, KHÔNG lọc diện tích)
    weak = [box for _, s, box in preds if s >= fp_conf]
    for no, lc, lb in labels:
        best = max((iou_xywh(lb, pb) for pb in weak), default=0.0)
        if best < iou_missing:
            issues.append(Issue(CHECK, WARN, "POSSIBLE_FALSE_POS", stem,
                                f"box {_name(ds, lc)} không khớp vật nào model thấy (IoU tốt nhất {best:.2f})",
                                no, {"iou": round(best, 4)}))
    return issues


def run(ds, cfg, preds=None):
    if preds is None:
        preds = get_preds(ds, cfg, "checker")
    issues = []
    for p in ds.image_files():
        stem = p.stem
        if stem not in preds or not ds.label_path(stem).exists():
            continue                              # không có ý kiến thứ hai / chưa có nhãn (missing_labels báo)
        issues.extend(check_image(ds, stem, preds[stem], cfg))
    return issues
