"""Test cho check thưởng box_aspect (học viên viết thêm)."""
from pipeline.checks import box_aspect


def run(make_ds, cfg, lines, size=(640, 480)):
    ds = make_ds(images={"a": 1}, labels={"a": lines}, size=size)
    return [(i.code, i.line, i.severity) for i in box_aspect.run(ds, cfg)]


def test_normal_boxes_are_silent(make_ds, cfg):
    assert run(make_ds, cfg, ["1 0.5 0.5 0.1 0.4", "0 0.3 0.3 0.2 0.15"]) == []      # người đứng 64×192 px: tỉ lệ 3


def test_matchstick_box_is_warned_with_line_number(make_ds, cfg):
    # dòng 2: 0.005*640 = 3.2 px rộng × 0.5*480 = 240 px cao -> tỉ lệ 75
    assert run(make_ds, cfg, ["1 0.5 0.5 0.1 0.4", "1 0.5 0.5 0.005 0.5"]) == [("BOX_ODD_ASPECT", 2, "warn")]


def test_ratio_is_measured_in_pixels_not_normalised_units(make_ds, cfg):
    # chuẩn hoá 0.6 × 0.04 (tỉ lệ 15) nhưng trên ảnh 640×160 là 384 × 6.4 px = tỉ lệ 60 -> cảnh báo
    assert run(make_ds, cfg, ["0 0.5 0.5 0.6 0.04"], size=(640, 160)) == [("BOX_ODD_ASPECT", 1, "warn")]
    # chuẩn hoá 0.05 × 0.9 (tỉ lệ 18) nhưng trên ảnh 960×80 là 48 × 72 px = tỉ lệ 1.5 -> im lặng
    assert run(make_ds, cfg, ["0 0.5 0.5 0.05 0.9"], size=(960, 80)) == []


def test_threshold_comes_from_config(make_ds, cfg):
    lines = ["1 0.5 0.5 0.02 0.5"]                       # 12.8 × 240 px -> tỉ lệ 18.75
    assert run(make_ds, cfg, lines) == [("BOX_ODD_ASPECT", 1, "warn")]
    cfg["box_aspect"] = {"max_ratio": 20}
    assert run(make_ds, cfg, lines) == []


def test_broken_lines_blank_lines_and_missing_label_do_not_crash(make_ds, cfg):
    ds = make_ds(images={"a": 1, "b": 2}, labels={"a": ["garbage", "", "93 0.5 0.5 0.001 0.9", "1 0.5 0.5 0 0.3", "1 0.5 0.5 0.005 0.5"]})
    assert [(i.image, i.line) for i in box_aspect.run(ds, cfg)] == [("a", 5)]
