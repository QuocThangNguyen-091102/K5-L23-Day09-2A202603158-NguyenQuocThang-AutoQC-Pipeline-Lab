# Báo cáo Day 09 — <Họ và tên>, <MSHV>

Cấu hình: `phash_dist=12`, `second_opinion.conf=0.6`, ngân sách duyệt 80 ảnh. Số liệu lấy từ `submission/reports/` (`08_summary.json`, `config_sha1=58d1755c…`) và `submission/calibration/`.

## 1. Kết luận trước
**HOLD** (mã thoát 10). Đây là bản nháp, chưa phát hành.
- **224** ảnh vào. Bước nhận loại **22** ảnh. **202** ảnh đi qua QC và được xuất vào `submission/export/clean_v1` (`manifest.json` ghi `decision: Hold`).
- Sau autofix và người duyệt còn **0 lỗi bắt buộc**. Tuy vậy **38/202 ảnh (18,8%)** vẫn còn cảnh báo chưa có người xem, cao hơn ngưỡng 10%.
- Nguyên nhân chính: hàng đợi có **125 ảnh**, trong khi ngân sách chỉ đủ duyệt **80**. 45 ảnh dư không ai xem, chủ yếu là box lỏng (16 ảnh) và box thừa (11 ảnh).

## 2. Lỗi và phân việc
Số liệu lấy từ `02_error_list_v1` (lỗi trước khi sửa). Mẫu số là 224 ảnh ở bước nhận và 202 ảnh ở QC.

| Mã lỗi | Số ảnh/dòng | Ai sửa | Vì sao |
|---|---:|---|---|
| `DUP_IMAGE_EXACT` | 8 ảnh / 224 | máy (loại ảnh) | md5 trùng tuyệt đối, không cần người phán |
| `LEAK_TEST` | 5 ảnh / 224 | máy (loại ảnh) | trùng `test` (img_0049, 0101, 0167, 0174, 0221). Nếu giữ lại, mAP của `raw` bị thổi phồng |
| `DUP_IMAGE_NEAR` | 4 ảnh / 224 | máy (loại ảnh) | phash ≤ 12. Đã mở xem cả 4 cặp, đều là ảnh thu nhỏ hoặc cắt của cùng một ảnh |
| `BAD_SIZE` / `CORRUPT_IMAGE` | 3 / 2 ảnh | máy (loại ảnh) | cạnh ngắn < 250 px; img_0136 bị cắt cụt, chỉ lộ lỗi khi gọi `load()` |
| `MISSING_LABEL_FILE` | 6 ảnh / 202 | **người** | máy không bịa nhãn. `needs_label` có trọng số 10 nên luôn đứng đầu hàng đợi, và cả 6 ảnh đã được gán |
| `BOX_OUT_OF_IMAGE` | 8 dòng | máy (`clip_box`) | cắt về [0,1], giữ nguyên lớp. Vẫn đưa ảnh vào hàng đợi (`FIXED_CLIP_BOX`) vì box tràn 2,3–6% có thể là box phình to |
| `DUP_BOX` / `BAD_CLASS_ID` / `BOX_ZERO` / `BAD_FORMAT` | 7 / 6 / 4 / 3 dòng | máy (`drop_line`) | dòng vô nghĩa về cú pháp: ID 93, −1, 7, 4; `nan`; thiếu cột; w hoặc h = 0 |
| `BAD_CLASS_NAME` | 2 (data.yaml) | máy (`rename_classes`) | `Person` và `Bus` viết hoa |
| `POSSIBLE_MISSING` / `WRONG_CLASS` / `LOOSE_BOX` / `FALSE_POS` | 53 / 18 / 28 / 29 | **người** | chỉ là nghi ngờ của model (yolo26l), nên chỉ cảnh báo |
| `EMPTY_LABEL` / `BOX_TINY` / `BOX_HUGE` / `CLASS_RARE` | 12 / 6 / 3 / 4 | **người** | quy tắc dự án. Máy không biết đó là ảnh nền hay thiếu nhãn |

Autofix tạo **35 thay đổi** (`03_fixes.csv`, mỗi dòng ghi trước → sau). Sau autofix, `EMPTY_LABEL` tăng từ 12 lên 15 vì 3 file chỉ có đúng một dòng hỏng (img_0050, 0104, 0194) bị xoá dòng và trở thành file rỗng. Những file này được đẩy sang người kiểm.

**Hàng đợi `05_review_queue.csv`.** Điểm ưu tiên = Σ trọng số × (1 + conf).
- Đầu hàng là img_0020 (11,5 điểm): vừa bị xoá dòng ID 93, vừa có MISSING và WRONG_CLASS. Tiếp theo là 6 ảnh `NEEDS_LABEL` (10 điểm mỗi ảnh), sau đó là các ảnh có WRONG_CLASS hoặc MISSING với conf cao.
- Với ngân sách 80 ảnh, người duyệt xem được **94/123 cảnh báo ngữ nghĩa**, tương ứng **74/103 ảnh** có cảnh báo ngữ nghĩa. Cụ thể: **18/18 ảnh WRONG_CLASS**, **50/52 ảnh MISSING**, nhưng chỉ **8/24 ảnh LOOSE_BOX** và **12/23 ảnh FALSE_POS**.
- Điểm yếu của cách xếp: FALSE_POS không có `conf` (vì không có dự đoán nào khớp), nên chỉ được nhân hệ số 1. Box "bus" giữa biển (img_0177, IoU 0,00) vì thế xếp sau các ảnh MISSING có conf 0,6. Xem mục 4b.

## 3. Calibration (2 ngưỡng)
| Tham số | Khởi đầu | Đã chọn | Precision / Recall (trước → sau) | Lý do (đánh đổi) |
|---|---|---|---|---|
| `duplicates.phash_dist` | 2 | **12** | Trên calib: NEAR 1,00/0,50 → **1,00/0,67**; EXACT 1,00/1,00 không đổi. Trên raw: 14 → 17 ảnh bị loại | Lỗi này dẫn tới **xoá ảnh**, nên ưu tiên precision. Trên raw, mình đo phash giữa mọi cặp ảnh: các cặp trùng thật nằm ở **0–10**, không có cặp nào ở 11–15, các cặp khác nhau bắt đầu từ **16**. Chọn 12 để có biên 2 phía trên cặp trùng xa nhất và 4 phía dưới cặp khác gần nhất. Mức 2 bỏ sót img_0223 (6), img_0186 (10) và **ca rò rỉ test img_0101 (6)** |
| `second_opinion.conf` | 0,25 | **0,6** | WRONG_CLASS 0,56/0,83 → **0,62/0,83**; MISSING 0,50/1,00 → **0,57/1,00**; LOOSE 0,29/0,40 → 0,20/0,20; FALSE_POS 0,31/1,00 không đổi (dùng `fp_conf`) | Đây là cảnh báo cho người, nên giữ recall. 0,6 là điểm cao nhất mà recall MISSING vẫn là 1,00 và WRONG_CLASS vẫn là 0,83. Lên 0,7 thì MISSING tụt còn 0,88 chỉ để đổi lấy +0,01 precision. Cái giá phải trả là LOOSE_BOX (từ 2/5 xuống 1/5). Trên raw: số cờ MISSING giảm 151 → 53, hàng đợi 143 → 125 ảnh |

**Không chọn conf = 0,8, dù 0,8 cho kết quả Release.** Mình đã chạy thử trên raw: ở 0,8 chỉ còn 16/202 ảnh có cảnh báo chưa duyệt (7,9%), đủ để Release. Nhưng trên calib, recall MISSING ở 0,8 tụt còn 0,75. Đó sẽ là Release vì checker bị làm mù, không phải vì dữ liệu sạch.

**Một chỗ calibration đánh lừa: ở `phash_dist=16`, bảng calib trông tốt hơn (NEAR recall 0,83, precision 1,00), nhưng trên raw lại tệ hơn.**
- `calibrate.py` **không chấm `LEAK_TEST`** vì calib không có ca rò rỉ nào. Ở mức 16, các ca LEAK giả không hiện lên trong bảng.
- Trên raw, phash=16 loại thêm 9 ảnh. Chỉ **1 cặp trùng thật** (img_0084 là bản cắt của img_0074). **8 ảnh còn lại bị báo nhầm**: 6 ca LEAK_TEST giả (ví dụ img_0013, ảnh bàn laptop, bị coi là trùng test_087, ảnh sân bóng chày) và 2 ca NEAR giả (img_0011, ảnh tennis, bị coi là trùng img_0008, ảnh trượt tuyết). Mình đã mở xem từng cặp.
- Ở mức 20, raw mất **137/224** ảnh ở bước nhận (134 ảnh bị báo trùng/rò rỉ, cộng 3 ảnh hỏng/sai kích thước). Riêng calib cũng có 22 ca LEAK giả, nhưng không có trong bảng điểm.
- Calib chỉ có 6 ca NEAR và 6 ca WRONG_CLASS, mỗi ca chiếm khoảng 17% recall. Calib cũng không có ca LEAK nào. Không nên tin recall trên calib như recall trên raw.
- Tài liệu cho rằng lỗi nhầm lớp trên raw nghiêng về car/truck/bus. Nhưng cờ WRONG_CLASS trên raw lại chủ yếu là nhãn `car` mà model nói `person` (12/18 cờ), 6 cờ còn lại là nhầm giữa car/truck/bus. Nhầm truck/car giữa hai model cùng họ YOLO dễ bị bỏ lọt (xem 4b, ý 3).

## 4. Cửa chặn và điều pipeline KHÔNG bắt được
**(a) Gate chặn đúng.** Mình đã chạy:
```
python -m pipeline.run --budget 0 --work work/run_nb --reports work/rep_nb --export-dir work/exp_nb
```
Kết quả: `REWORK — còn 6 lỗi bắt buộc (MISSING_LABEL_FILE×6)`, **mã thoát 20**, log in `KHÔNG xuất`, `08_summary.json` ghi `"exported": null`, và thư mục `work/exp_nb` **không được tạo**. Không có người thì 6 ảnh chưa có nhãn vẫn còn nguyên, nên gate không cho xuất. Ngược lại, với ngân sách 80, cả 6 ảnh được gán và lỗi bắt buộc về 0. Test `test_error_cannot_be_hidden_by_reviewed` bảo đảm ảnh "đã duyệt" cũng không che được lỗi bắt buộc.

**(b) Điểm mù có bằng chứng:**
1. **Ảnh trùng biến đổi mạnh.** img_0074 và img_0084 là cùng một cảnh: một ảnh 352×470, ảnh kia là bản cắt rồi phóng to 480×640, phash cách nhau 16. Không có ngưỡng nào bắt được cặp này mà không kéo theo 8 ca báo nhầm (mục 3), nên **cả hai ảnh vẫn nằm trong `clean_v1`**. Đây là điểm mù đã biết, giống ca "cắt 80% rồi thu nhỏ" trong tài liệu. Muốn bắt phải dùng đặc trưng khác, ví dụ so khớp keypoint hoặc embedding, kèm người xem.
2. **Box thừa ngoài ngân sách.** img_0177 (lướt sóng), img_0111 (đua ngựa) và img_0180 (cột đỗ xe) đều có một box `bus` nhỏ đặt ở chỗ không có vật gì. Mình đã vẽ bằng `viz_labels.py`. `second_opinion` có cờ FALSE_POS (IoU 0,00), nhưng ba ảnh này xếp sau vị trí 80 nên không được duyệt, và **box sai vẫn nằm trong bản nháp**.
3. **Ý kiến thứ hai không phải sự thật.** Sau khi người thay nhãn, trên chính 80 ảnh đã duyệt model vẫn cờ 11 MISSING, 10 FALSE_POS, 4 LOOSE và 3 WRONG_CLASS. Nghĩa là những cờ này là báo động giả của model so với nhãn người. Chiều ngược lại cũng đúng: lỗi mà cả nhãn gốc (yolo26n) lẫn yolo26l cùng sai, ví dụ cùng nhầm truck thành car, sẽ không bao giờ bị cờ.
4. **Box lỏng nhẹ.** Chỉ box có IoU < 0,5 so với dự đoán mới bị cờ. Calib cho thấy LOOSE_BOX recall chỉ **1/5** dù box đã phình 1,45–1,58 lần, và 16/24 ảnh LOOSE trên raw chưa được duyệt.

## 5. Train: raw vs clean (tùy chọn, chấm riêng)
**Cấu hình (rút gọn, chạy CPU cục bộ, không dùng Colab):**
```
python scripts/train_compare.py --variants raw clean --seeds 0 1 --epochs 20 --imgsz 416 --device cpu
```
- yolo26n.pt, 20 epoch, batch 16, **imgsz 416** (thay cho 640 vì chạy CPU), seed 0 và 1.
- Val chung là `gold_val` (40 ảnh), test chung là `data/test` (100 ảnh). Cả 4 lượt có cùng `config_sha1`. Hai lượt `clean` có `manifest_sha1` khớp với `clean_v1` (bản nháp Hold).
- Số ảnh train: `raw` 224 ảnh, nhưng Ultralytics tự bỏ **11 ảnh** (2 ảnh hỏng và 9 ảnh có dòng nhãn lỗi), nên thực chất chỉ train trên **213** ảnh. Với mỗi ảnh có một dòng lỗi, toàn bộ ảnh bị bỏ. `clean` train trên 202 ảnh.

`submission/results/comparison.md` (sinh bởi `summarize_results.py`):

| biến thể | #ảnh train | số seed | map50 (TB ± độ lệch) | map50_95 (TB ± độ lệch) | precision (TB ± độ lệch) | recall (TB ± độ lệch) |
|---|---|---|---|---|---|---|
| raw | 224 | 2 | 0.621 ± 0.004 | 0.415 ± 0.008 | 0.639 ± 0.006 | 0.582 ± 0.013 |
| clean | 202 | 2 | 0.558 ± 0.102 | 0.361 ± 0.071 | 0.675 ± 0.137 | 0.484 ± 0.051 |

**So với nhiễu:** chênh mAP50 (clean − raw) là **−0,063**. Nhưng độ lệch giữa hai seed của `clean` là **0,102** (seed 0 được 0,631, seed 1 chỉ 0,486), lớn hơn chính mức chênh. Vì vậy **chưa kết luận được** clean tốt hơn hay kém hơn raw. Với 2 seed và 100 ảnh test, không thể nói "clean kém hơn".

**Vì sao nhiễu lớn đến vậy?** Mình kiểm tra và tìm ra nguyên nhân: `best.pt` được chọn theo mAP50-95 trên val chỉ có 40 ảnh, và với **3/4 lượt, epoch tốt nhất trên val lại là epoch 1** (theo `results.csv` của Ultralytics trong `work/train/runs/`, thư mục không commit; tái lập bằng lệnh train ở trên). Ở epoch 1, mô hình pretrained COCO đã đạt val mAP50 khoảng 0,70–0,72; sau đó điểm tụt rồi mới hồi lại. Chỉ riêng clean seed 1 chọn epoch 10. Như vậy bảng chính thức thực chất so 3 mô hình mới fine-tune **1 epoch** với 1 mô hình 10 epoch, chứ chưa đo được tác động của dữ liệu.

Mình đánh giá thêm `last.pt` (đủ 20 epoch) trên cùng tập test bằng `scripts/extra_eval.py`, kết quả lưu ở `submission/results/extra_eval.json`. Dùng `best.pt` thì con số khớp chính xác với bảng chính thức:

| mAP50 (TB ± độ lệch, 2 seed) | raw | clean | clean − raw |
|---|---|---|---|
| `last.pt`, test 100 ảnh | 0,520 ± 0,008 | 0,528 ± 0,013 | **+0,008** |
| `last.pt`, test bỏ 5 ảnh trùng raw (95 ảnh) | 0,503 | 0,519 | +0,016 |
| `last.pt` mAP50-95, test 100 ảnh | 0,351 | 0,370 | +0,019 |

Sau đủ 20 epoch, clean nhỉnh hơn một chút, nhưng mức chênh vẫn cỡ độ lệch giữa các seed (0,008–0,013). **Kết luận vẫn là nằm trong nhiễu.**

**Giả thuyết và cách kiểm:**
1. **Rò rỉ test làm điểm raw bị thổi phồng.** `raw` chứa 5 ảnh trùng test (img_0049, 0101, 0167, 0174, 0221). Khi bỏ 5 ảnh test đó, `last.pt` của raw giảm 0,017 còn clean chỉ giảm 0,009, tức có dấu hiệu nhỏ đúng chiều. Kiểm chứng: so điểm trên test 95 ảnh với nhiều seed hơn.
2. **Chọn checkpoint trên val 40 ảnh là nguồn nhiễu chính, lấn át hiệu ứng của nhãn.** Kiểm chứng: báo cáo cả `last.pt`, tăng lên ≥ 5 seed, hoặc dùng val lớn hơn.
3. **`clean` vẫn còn nhãn máy.** 122/202 ảnh chưa được người duyệt, còn box thừa (img_0177…) và box lỏng (16 ảnh). `clean` cũng ít ảnh hơn (202 so với 213). Kiểm chứng: train thêm biến thể `oracle` (cùng ảnh với clean, nhãn người) để biết trần, và `auto` (không có người duyệt) để tách đóng góp của 80 ảnh được duyệt.
4. **imgsz 416 và chỉ 20 epoch trên CPU.** Fine-tune 200 ảnh từ trọng số COCO dễ làm giảm điểm so với epoch 1. Kiểm chứng: chạy lại trên Colab với imgsz 640 theo cấu hình chuẩn.

**Việc tiếp theo:** chạy ≥ 5 seed với imgsz 640 trên GPU, báo cáo cả best và last, thêm biến thể `oracle`/`auto`, và sửa cách xếp hàng đợi (mục 6a) trước khi train lại.

## 6. Quyết định và ghi chú AI
**(a) Quyết định: HOLD.** Không còn lỗi bắt buộc, nhưng 18,8% ảnh còn cảnh báo chưa duyệt, cao hơn ngưỡng 10%. Bản `clean_v1` chỉ dùng để thử nghiệm.

Để chuyển sang **Release**, cần đưa số ảnh còn cảnh báo chưa duyệt xuống **≤ 20/202**, tức duyệt thêm ít nhất **18** trong 38 ảnh đó. Có hai cách:
- Tăng ngân sách lên khoảng 125 ảnh để phủ hết hàng đợi.
- Sửa cách xếp hàng để FALSE_POS có IoU 0,00 được ưu tiên ngang MISSING (ví dụ cộng điểm theo `1 − best_iou`), rồi xem tay img_0177, img_0111, img_0180 và 16 ảnh LOOSE_BOX.

Ngoài ra nên xoá một trong hai ảnh img_0074/img_0084. Không được hạ `conf` hay `phash_dist` chỉ để gate "qua".

**(b) Ghi chú AI.** Có dùng AI (Claude Code) để viết 4 module.
- **Prompt chính:** dán docstring của từng stub cùng file test tương ứng. Yêu cầu: chỉ sửa thư mục `ds`, không viết cứng ngưỡng, không đọc `review_reference` hay đáp án calib.
- **Cách kiểm:** chạy `pytest` từng file rồi toàn bộ (79/79 test của đề). Nhờ thêm một agent review độc lập, không biết trước kết luận của mình: agent này tìm ra ca DUP_BOX dạng chuỗi (A≈B≈C chỉ báo B) và mình đã sửa. Nhờ thêm một agent đối chiếu từng số trong báo cáo với `reports/`, nhờ đó sửa được 3 số liệu sai. Tự thử thêm 3 ca ngoài test trên bản sao tạm: một dòng vừa tràn vừa lặp, dòng trống giữa file, file nhãn mồ côi. Kiểm tra idempotent. So bảng calib ở cấu hình khởi đầu với ví dụ trong `docs/CALIBRATION.md`: khớp từng số (0,56/0,83, 0,50/1,00).
- **Lần AI sai:** bản autofix đầu tiên bỏ qua lỗi dòng của file nhãn không có ảnh. Test vẫn xanh, nhưng lỗi bắt buộc đó sẽ còn mãi và pipeline Rework vĩnh viễn. Mình phát hiện khi tự thử với file mồ côi và đã sửa. Ngoài ra, bản gate đầu tiên so ngưỡng bằng tỉ lệ đã làm tròn 4 chữ số (0,09996 sẽ thành Hold), nên đã đổi sang so bằng giá trị thô.

*(Thưởng +3, check mới)* `pipeline/checks/box_aspect.py` cảnh báo `BOX_ODD_ASPECT` khi box có tỉ lệ khung hình theo pixel > 15. Check này bắt box dạng "que diêm" mà BOX_ZERO và BOX_TINY bỏ qua. Có 5 test trong `tests/test_box_aspect.py` (tổng cộng 84/84 test xanh). Chạy độc lập bằng `python -m pipeline.checks.box_aspect --src work/run/ds`, vì `QC_CHECKS` bị ghim sha1 nên không đăng ký vào pipeline được. Kết quả trên raw: 0 cờ ở ngưỡng 15. Thử hạ xuống 8 thì có 2 cờ (img_0042 dòng 5, img_0124 dòng 6), nhưng mở xem thì cả hai là vật thật bị cắt ở mép ảnh, tức báo động giả. Đây là lý do check chỉ nên cảnh báo, và ngưỡng 15 hợp lý hơn 8.

*(Thưởng CVAT: không làm vì không có máy chủ CVAT.)*
