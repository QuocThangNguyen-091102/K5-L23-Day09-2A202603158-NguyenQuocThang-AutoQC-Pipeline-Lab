"""BƯỚC 2/4 — Sửa tự động những lỗi bắt buộc mà máy sửa được AN TOÀN.   ★★

Test:  pytest tests/test_autofix.py -q

`fix(ds, issues, cfg) -> list[dict]`: duyệt `issues` (chỉ lỗi severity ERROR), sửa thẳng vào thư mục `ds`,
và trả về danh sách thay đổi; mỗi phần tử có khoá: image, line, action, before, after
(đây chính là file `03_fixes.csv` — bằng chứng pipeline đã làm gì, người có thể kiểm lại).

| code lỗi                                       | cách sửa                                    | action           |
|------------------------------------------------|---------------------------------------------|------------------|
| BAD_FORMAT, BAD_CLASS_ID, BOX_ZERO, DUP_BOX    | xoá dòng đó khỏi file nhãn                  | "drop_line"      |
| BOX_OUT_OF_IMAGE                               | cắt box về trong [0,1] (giữ nguyên lớp)     | "clip_box"       |
| MISSING_LABEL_FILE                             | KHÔNG sửa file (máy không thể bịa nhãn): ghi 1 dòng fix, before="(không có file)", after="chuyển người gán" | "needs_label" |
| BAD_CLASS_NAME                                 | ghi lại `names` trong data.yaml đúng `cfg["classes"]` | "rename_classes" |
| DUP_IMAGE_*, LEAK_TEST, CORRUPT_IMAGE, BAD_SIZE| xoá ảnh + nhãn khỏi `ds`                    | "remove_image"   |

Bẫy cần nghĩ tới (có test cho từng cái)
- Một file có NHIỀU dòng lỗi: số dòng trong `issues` là số dòng GỐC. Nếu xoá từng dòng một thì số dòng lệch.
  Gom theo file, rồi ghi lại MỘT lần.
- Sau khi cắt, box có thể không còn diện tích (nằm hẳn ngoài ảnh): lúc đó xoá dòng thay vì ghi box rỗng.
- Một dòng có 2 lỗi (vd. BOX_OUT_OF_IMAGE + DUP_BOX): xoá dòng thắng, chỉ ghi 1 fix `drop_line`, không ghi thêm `clip_box`. Dòng trống ở giữa file vẫn đếm vào số dòng gốc.
- Ảnh vừa bị xoá (DUP_IMAGE_*...) mà còn issue dòng của chính nó: bỏ qua êm, không được báo lỗi/chết.
- Không động tới lỗi WARN (cảnh báo là việc của người). Không sửa file ở `data/raw/` — chỉ sửa `ds`.
- Chạy lần 2 trên dữ liệu đã sửa phải không làm gì thêm (idempotent) — NGOẠI LỆ duy nhất: `needs_label` được ghi lại mỗi lần còn lỗi `MISSING_LABEL_FILE` (vì ảnh vẫn chưa có nhãn).

- `needs_label` KHÔNG tạo file nhãn rỗng (rỗng = "ảnh nền", khác với "chưa gán"). `review_queue` sẽ đẩy ảnh này lên đầu hàng đợi cho người.

Gợi ý: `yaml.safe_load / safe_dump`.
"""
from collections import defaultdict  # noqa: F401

import yaml  # noqa: F401

from ..common import ERROR, parse_yolo_line  # noqa: F401


DROP_CODES = {"BAD_FORMAT", "BAD_CLASS_ID", "BOX_ZERO", "DUP_BOX"}
CLIP_CODES = {"BOX_OUT_OF_IMAGE"}
REMOVE_CODES = {"DUP_IMAGE_EXACT", "DUP_IMAGE_NEAR", "LEAK_TEST", "CORRUPT_IMAGE", "BAD_SIZE"}


def _fmt(v):
    return f"{v:.6f}"


def _clip(text):
    """Cắt box về [0,1]. Trả về dòng mới, hoặc None nếu box không còn diện tích (nằm hẳn ngoài ảnh)."""
    c, x, y, w, h = parse_yolo_line(text)
    x1, x2 = max(0.0, x - w / 2), min(1.0, x + w / 2)
    y1, y2 = max(0.0, y - h / 2), min(1.0, y + h / 2)
    nw, nh = x2 - x1, y2 - y1
    if nw <= 0 or nh <= 0 or float(_fmt(nw)) <= 0 or float(_fmt(nh)) <= 0:
        return None
    return f"{c} {_fmt((x1 + x2) / 2)} {_fmt((y1 + y2) / 2)} {_fmt(nw)} {_fmt(nh)}"


def _remove_image(ds, stem):
    p = ds.image_path(stem)
    if p is None:                                 # đã xoá ở lần trước -> idempotent, không ghi gì
        return None
    lp = ds.label_path(stem)
    before = p.name + (f" + {lp.name}" if lp.exists() else "")
    p.unlink()
    lp.unlink(missing_ok=True)
    ds._size_cache.pop(stem, None)
    return before


def _rename_classes(ds, cfg):
    data = {}
    if ds.yaml_path.exists():
        data = yaml.safe_load(ds.yaml_path.read_text(encoding="utf-8")) or {}
    old = ds.yaml_names()
    new = dict(enumerate(cfg["classes"]))
    if old == new:
        return None
    data["names"] = new
    ds.yaml_path.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")
    return dict(image="data.yaml", line=None, action="rename_classes",
                before=", ".join(f"{k}:{v}" for k, v in sorted(old.items())) or "(không đọc được)",
                after=", ".join(f"{k}:{v}" for k, v in new.items()))


def _fix_lines(ds, stem, drop, clip):
    """Sửa một file nhãn theo SỐ DÒNG GỐC (đếm cả dòng trống), ghi lại một lần."""
    lp = ds.label_path(stem)
    if not lp.exists():                           # ảnh vừa bị loại (nhãn đã xoá cùng) -> bỏ qua êm
        return []
    raw_lines = lp.read_text(encoding="utf-8", errors="replace").splitlines()
    out, fixes = [], []
    for no, text in enumerate(raw_lines, 1):
        if no in drop:                            # xoá thắng cắt: một dòng chỉ một fix
            fixes.append(dict(image=stem, line=no, action="drop_line", before=text.strip(), after="(xoá dòng)"))
            continue
        if no in clip:
            try:
                new = _clip(text)
            except ValueError:                    # dòng hỏng mà chỉ bị gắn BOX_OUT_OF_IMAGE (không xảy ra với label_format chuẩn)
                new = None
            if new is None:
                fixes.append(dict(image=stem, line=no, action="drop_line", before=text.strip(), after="(xoá dòng: box nằm ngoài ảnh)"))
                continue
            fixes.append(dict(image=stem, line=no, action="clip_box", before=text.strip(), after=new))
            out.append(new)
            continue
        out.append(text)
    if fixes:
        lp.write_text("".join(l + "\n" for l in out), encoding="utf-8")
    return fixes


def fix(ds, issues, cfg):
    errors = [i for i in issues if i.severity == ERROR]   # cảnh báo là việc của người: không động tới
    fixes = []

    # 1) loại ảnh (trùng / rò rỉ / hỏng / sai kích thước) trước, để bỏ qua các lỗi dòng của chính ảnh đó
    for stem in sorted({i.image for i in errors if i.code in REMOVE_CODES}):
        codes = sorted({i.code for i in errors if i.image == stem and i.code in REMOVE_CODES})
        before = _remove_image(ds, stem)
        if before is not None:
            fixes.append(dict(image=stem, line=None, action="remove_image", before=before, after=f"(xoá ảnh + nhãn: {', '.join(codes)})"))

    # 2) tên lớp trong data.yaml
    if any(i.code == "BAD_CLASS_NAME" for i in errors):
        f = _rename_classes(ds, cfg)
        if f:
            fixes.append(f)

    # 3) lỗi dòng: gom theo file, dùng số dòng gốc
    drop, clip = defaultdict(set), defaultdict(set)
    for i in errors:
        if i.line is None:
            continue
        if i.code in DROP_CODES:
            drop[i.image].add(i.line)
        elif i.code in CLIP_CODES:
            clip[i.image].add(i.line)
    for stem in sorted(set(drop) | set(clip)):
        fixes.extend(_fix_lines(ds, stem, drop[stem], clip[stem] - drop[stem]))

    # 4) ảnh chưa có file nhãn: máy KHÔNG bịa nhãn (kể cả file rỗng) -> chuyển người gán
    for stem in sorted({i.image for i in errors if i.code == "MISSING_LABEL_FILE"}):
        if ds.image_path(stem) is not None and not ds.label_path(stem).exists():
            fixes.append(dict(image=stem, line=None, action="needs_label", before="(không có file)", after="chuyển người gán"))
    return fixes
