"""All names here are invented. No real document is ever used in tests."""
import json
import zipfile

import docx
import openpyxl
import pptx
import pytest

from piiguard import config as cfgmod, detect, pipeline
from piiguard.documents import UnsupportedFormat, open_document
from piiguard.masking import build_replacements
from piiguard.replace import Replacer
from piiguard.surname import split_surname

P = lambda *names: [{"value": n, "type": "person"} for n in names]


def cfg(**kw):
    c = json.loads(json.dumps(cfgmod.DEFAULTS))
    c.update(kw)
    return c


# ---- masking -----------------------------------------------------------
@pytest.mark.parametrize("name,expected", [
    ("王小明", ("王", "小明")), ("王明", ("王", "明")), ("歐陽大華", ("歐陽", "大華")),
    ("王林美玉", ("王", "林美玉")), ("John Smith", ("J", "ohn Smith")),
])
def test_split_surname(name, expected):
    assert split_surname(name) == expected


def test_modes():
    ents = P("王小明", "王大同", "歐陽大華", "王明")
    assert build_replacements(ents, "keep_surname", "○") == {
        "王小明": "王○○", "王大同": "王○○", "歐陽大華": "歐陽○○", "王明": "王○"}
    numbered = build_replacements(ents, "keep_surname_numbered", "○")
    assert numbered["王小明"] == "王○○(1)" and numbered["王大同"] == "王○○(2)"
    assert numbered["王明"] == "王○"  # no collision, no number
    assert build_replacements(ents, "full", "Ｏ")["歐陽大華"] == "ＯＯＯＯ"
    assert build_replacements(ents, "code", "○") == {
        "王小明": "人員A", "王大同": "人員B", "歐陽大華": "人員C", "王明": "人員D"}


def test_non_person_always_fully_masked():
    r = build_replacements([{"value": "A123456789", "type": "tw_id"}], "keep_surname", "○")
    assert r == {"A123456789": "○" * 10}


# ---- replacer ----------------------------------------------------------
def test_longest_first_and_digit_boundaries():
    rep = Replacer({"王小明": "王○○", "王小": "X", "123456": "######"})
    assert rep.apply("王小明與王小") == "王○○與X"
    assert rep.apply("病歷號123456，流水號91234567") == "病歷號######，流水號91234567"


# ---- documents ---------------------------------------------------------
def test_docx_name_split_across_runs_keeps_formatting(tmp_path):
    d = docx.Document()
    p = d.add_paragraph()
    p.add_run("通報人 王")
    bold = p.add_run("小")
    bold.bold = True
    p.add_run("明 發現異常")
    d.sections[0].header.paragraphs[0].text = "承辦：林美玲"
    d.core_properties.author = "王小明"
    src = tmp_path / "a.docx"
    d.save(src)

    res = pipeline.apply(str(src), P("王小明", "林美玲"), cfg())
    assert res["verified"] and res["replaced"] == 2
    out = docx.Document(res["output"])
    runs = out.paragraphs[0].runs
    assert "".join(r.text for r in runs) == "通報人 王○○ 發現異常"
    assert len(runs) == 3 and runs[1].bold  # run structure and style untouched
    assert out.sections[0].header.paragraphs[0].text == "承辦：林○○"
    assert out.core_properties.author == ""
    assert src.exists() and "王小明" in docx.Document(src).paragraphs[0].text  # original intact


def test_xlsx_cells_numbers_and_styles(tmp_path):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["原醫師", "病歷號", "說明"])
    ws.append(["王小明", 12345678, "王小明醫師與林美玲護理師討論"])
    ws.append(["行政", 87654321, "無"])
    ws["A2"].font = openpyxl.styles.Font(bold=True, name="標楷體")
    ws.column_dimensions["C"].width = 40
    src = tmp_path / "a.xlsx"
    wb.save(src)

    ents = P("王小明", "林美玲") + [{"value": "12345678", "type": "mrn"}]
    res = pipeline.apply(str(src), ents, cfg(write_mapping=True))
    assert res["verified"] and res["replaced"] == 4
    ws2 = openpyxl.load_workbook(res["output"]).active
    assert ws2["A2"].value == "王○○" and ws2["A2"].font.bold and ws2["A2"].font.name == "標楷體"
    assert ws2["B2"].value == "○" * 8 and ws2["B3"].value == 87654321
    assert ws2["C2"].value == "王○○醫師與林○○護理師討論"
    assert ws2["A3"].value == "行政" and ws2.column_dimensions["C"].width == 40
    rows = open(res["mapping"], encoding="utf-8-sig").read().splitlines()
    assert rows[0] == "原文,取代為,類別" and "王小明,王○○,person" in rows


def test_pptx(tmp_path):
    prs = pptx.Presentation()
    s = prs.slides.add_slide(prs.slide_layouts[1])
    s.shapes.title.text = "案例：王小明"
    s.notes_slide.notes_text_frame.text = "報告人林美玲"
    src = tmp_path / "a.pptx"
    prs.save(src)
    res = pipeline.apply(str(src), P("王小明", "林美玲"), cfg(mode="code"))
    out = pptx.Presentation(res["output"]).slides[0]
    assert out.shapes.title.text == "案例：人員A"
    assert out.notes_slide.notes_text_frame.text == "報告人人員B"
    assert res["verified"]


def test_untouched_parts_are_byte_identical(tmp_path):
    wb = openpyxl.Workbook()
    wb.active.append(["王小明"])
    src = tmp_path / "a.xlsx"
    wb.save(src)
    res = pipeline.apply(str(src), P("王小明"), cfg(scrub_metadata=False))
    a, b = zipfile.ZipFile(src), zipfile.ZipFile(res["output"])
    assert a.namelist() == b.namelist()
    changed = [n for n in a.namelist() if a.read(n) != b.read(n)]
    assert len(changed) == 1 and changed[0].startswith("xl/")  # only the part holding the text


def test_text_file_big5_roundtrip(tmp_path):
    src = tmp_path / "a.txt"
    src.write_bytes("通報人：王小明\n電話 0912-345-678\n".encode("cp950"))
    res = pipeline.apply(str(src), P("王小明") + [{"value": "0912-345-678", "type": "phone"}], cfg())
    assert open(res["output"], encoding="cp950").read() == "通報人：王○○\n電話 ○○○○○○○○○○○○\n"


@pytest.mark.parametrize("name,hint", [("a.xls", ".xlsx"), ("a.doc", ".docx"), ("a.pdf", "PDF")])
def test_legacy_and_pdf_are_refused_with_guidance(tmp_path, name, hint):
    f = tmp_path / name
    f.write_bytes(b"x")
    with pytest.raises(UnsupportedFormat, match=hint):
        open_document(f)


def test_never_overwrites_existing_output(tmp_path):
    src = tmp_path / "a.txt"
    src.write_text("王小明", "utf-8")
    first = pipeline.apply(str(src), P("王小明"), cfg())["output"]
    second = pipeline.apply(str(src), P("王小明"), cfg())["output"]
    assert first != second and first.endswith("a_去識別.txt")


# ---- detection (model replaced by a stub) --------------------------------
def test_scan_filters_hallucinations_titles_and_whitelist(tmp_path, monkeypatch):
    src = tmp_path / "a.txt"
    src.write_text("王小明醫師於急診科告知家屬林美玲。行政已通知。身分證 A123456789", "utf-8")
    monkeypatch.setattr(pipeline.server, "connection", lambda: {"model": "stub", "port": 0, "key": ""})
    monkeypatch.setattr(pipeline.server, "status", lambda: {"state": "ready"})
    monkeypatch.setattr(detect, "ask_model",
                        lambda conn, w: ["王小明醫師", "林美玲", "行政", "急診科", "張不存在", "王"])
    c = cfg(blacklist=["家屬"])
    c["categories"]["tw_id"] = True
    res = pipeline.scan(str(src), c)
    got = {e["value"]: e for e in res["entities"]}
    assert set(got) == {"王小明", "林美玲", "家屬", "A123456789"}
    assert got["王小明"]["replacement"] == "王○○" and got["王小明"]["count"] == 1
    assert got["家屬"]["source"] == "blacklist"  # blacklist beats the default whitelist
    assert set(res["whitelisted"]) == {"行政", "急診科"}
    assert res["discarded_model_outputs"] == 2  # invented name + bare surname


def test_scan_without_model_fails_loudly(tmp_path, monkeypatch):
    src = tmp_path / "a.txt"
    src.write_text("王小明", "utf-8")
    monkeypatch.setattr(pipeline.server, "connection", lambda: None)
    with pytest.raises(detect.ModelError):
        pipeline.scan(str(src), cfg())


def test_windows_split_long_text_with_overlap():
    w = detect.windows(["甲" * 3000, "短句", "短句"])
    assert all(len(x) <= detect.WINDOW_CHARS for x in w) and sum("短句" in x for x in w) == 1


def test_stop_handles_server_that_already_exited(tmp_path, monkeypatch):
    """Regression: a finished-but-unreaped child made stop() raise PermissionError."""
    import subprocess, time
    from piiguard import server
    monkeypatch.setattr(server, "STATE", tmp_path / "server.json")
    proc = subprocess.Popen(["/usr/bin/true"], start_new_session=True)
    time.sleep(0.3)  # exited, not yet reaped by us
    server.STATE.write_text(json.dumps({"pid": proc.pid, "port": 1, "key": "k", "model": "m", "started": 0}))
    assert server.stop() == {"state": "stopped", "model": None}
    assert server.status()["state"] == "stopped" and not server.STATE.exists()


def test_model_answer_is_mapped_back_to_spaced_original():
    w = "醫品病安中心 伍 佳 穎、護理部 萬芳儀"
    assert detect.clean_name("伍佳穎", w) == "伍 佳 穎"   # what the document really contains
    assert detect.clean_name("萬芳儀督導", w) == "萬芳儀"   # trailing title removed
    assert detect.clean_name("張不存在", w) is None
