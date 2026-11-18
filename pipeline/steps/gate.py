"""BƯỚC 4 — Cửa chặn: quyết định Release / Hold / Rework.   ★

Test:  pytest tests/test_gate.py -q

Cây quyết định Day 07 (slide Day 09: "Lỗi bắt buộc chặn pipeline; lỗi cảnh báo chuyển người xem"):

  còn ≥ 1 lỗi bắt buộc (severity ERROR)                          -> "Rework"
  không còn lỗi bắt buộc, nhưng tỉ lệ ẢNH còn cảnh báo
      >= cfg["gate"]["warn_ratio_hold"]                          -> "Hold"
  còn lại                                                        -> "Release"

Tỉ lệ cảnh báo = (số ẢNH khác nhau có ≥ 1 cảnh báo) / (tổng số ảnh).  Chú ý:
- chỉ đếm issue có `image` nằm trong `image_stems` (bỏ "<dataset>", "data.yaml");
- bỏ qua ảnh nằm trong `reviewed` (người đã xem, cảnh báo của ảnh đó coi như đã xử lý) — nhưng LỖI BẮT BUỘC thì không bao giờ được bỏ qua;
- mẫu số là số ảnh, không phải số issue.

Trả về dict: decision, n_errors, n_warn_images, n_images, warn_ratio (làm tròn 4 chữ số), reasons (list[str], giải thích bằng tiếng Việt, có số liệu).
"""
from ..common import ERROR, WARN  # noqa: F401


def decide(issues, image_stems, cfg, reviewed=frozenset()):
    stems = set(image_stems)
    reviewed = set(reviewed or ())
    hold_at = cfg["gate"]["warn_ratio_hold"]

    errors = [i for i in issues if i.severity == ERROR]          # KHÔNG lọc theo reviewed / stems: lỗi bắt buộc luôn chặn
    warn_imgs = {i.image for i in issues if i.severity == WARN and i.image in stems and i.image not in reviewed}
    n_images = len(stems)
    raw_ratio = len(warn_imgs) / n_images if n_images else 0.0  # so ngưỡng bằng giá trị THÔ (làm tròn chỉ để báo cáo)
    ratio = round(raw_ratio, 4)

    if errors:
        codes = {}
        for i in errors:
            codes[i.code] = codes.get(i.code, 0) + 1
        detail = ", ".join(f"{c}×{n}" for c, n in sorted(codes.items()))
        decision = "Rework"
        reasons = [f"còn {len(errors)} lỗi bắt buộc ({detail}): trả về sửa/gán nhãn, không xuất dataset"]
    elif raw_ratio >= hold_at - 1e-12:                          # 3/30 phải đúng bằng 10% (sai số dấu phẩy động)
        decision = "Hold"
        reasons = [f"không còn lỗi bắt buộc, nhưng {len(warn_imgs)}/{n_images} ảnh ({ratio:.1%}) còn cảnh báo chưa người duyệt "
                   f">= ngưỡng {hold_at:.0%}"]
    else:
        decision = "Release"
        reasons = [f"không còn lỗi bắt buộc; {len(warn_imgs)}/{n_images} ảnh ({ratio:.1%}) còn cảnh báo chưa duyệt < ngưỡng {hold_at:.0%}"]
    return dict(decision=decision, n_errors=len(errors), n_warn_images=len(warn_imgs), n_images=n_images,
                warn_ratio=ratio, reasons=reasons)
