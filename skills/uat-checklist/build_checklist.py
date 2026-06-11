# -*- coding: utf-8 -*-
# 請以繁體中文產生程式碼註解。請務必保持 UTF-8 編碼。
#
# 功能說明：UAT / 驗收測試清單 xlsx 通用產生器
#           讀取 spec.json（描述工作表與驗收項目）→ 輸出多分頁 Excel
#           每列含 Pass/Fail/N/A/Blocked 結果欄 + 測試人員/日期/備註
# 建立日期：2026-06-11
# 版本：v1.0.0
#
# 用法：
#   python build_checklist.py spec.json                  # 預設 checkbox 模式
#   python build_checklist.py spec.json --out 清單.xlsx   # 指定輸出檔
#   python build_checklist.py spec.json --mode dropdown   # 改用下拉選單（相容舊版 Excel）
#
# 依賴：xlsxwriter（pip install xlsxwriter）；checkbox 模式需 xlsxwriter >= 3.2.0
#
# spec.json 結構見同資料夾 example_spec.json 與 SKILL.md

import argparse
import json
import sys

try:
    import xlsxwriter
except ImportError:
    sys.exit("缺少 xlsxwriter，請先安裝：pip install xlsxwriter")

DEFAULT_RESULTS = ["Pass", "Fail", "N/A", "Blocked"]

# 欄位寬度設定
W_CAT, W_NO, W_DESC = 22, 9, 58
W_RESULT, W_CB = 16, 8
W_TESTER, W_DATE, W_NOTE = 12, 14, 28


def _make_formats(wb):
    """建立共用儲存格格式"""
    return {
        "banner": wb.add_format({"bold": True, "font_size": 12, "font_color": "#FFFFFF",
                                 "bg_color": "#0075C2", "align": "left", "valign": "vcenter", "border": 1}),
        "head": wb.add_format({"bold": True, "font_size": 10, "font_color": "#FFFFFF",
                               "bg_color": "#859ABA", "align": "center", "valign": "vcenter",
                               "border": 1, "text_wrap": True}),
        "cat": wb.add_format({"bold": True, "bg_color": "#EAF3FA", "align": "left", "valign": "top",
                              "border": 1, "text_wrap": True}),
        "no": wb.add_format({"align": "center", "valign": "vcenter", "border": 1}),
        "desc": wb.add_format({"align": "left", "valign": "vcenter", "border": 1, "text_wrap": True}),
        "cell": wb.add_format({"align": "center", "valign": "vcenter", "border": 1}),
        "cb": wb.add_format({"align": "center", "valign": "vcenter", "border": 1}),
        # 說明頁
        "t": wb.add_format({"bold": True, "font_size": 16, "font_color": "#0075C2"}),
        "sub": wb.add_format({"font_size": 11, "font_color": "#444444"}),
        "sh": wb.add_format({"bold": True, "font_size": 12, "font_color": "#0075C2"}),
        "p": wb.add_format({"font_size": 10, "text_wrap": True}),
    }


def _write_intro(wb, fmt, intro):
    """寫入說明 / 範圍頁（純文字，無核取方塊）"""
    ws = wb.add_worksheet(intro.get("tab", "0.說明與範圍")[:31])
    ws.set_column(0, 0, 110)
    ws.hide_gridlines(2)
    kind_fmt = {"title": fmt["t"], "sub": fmt["sub"], "h": fmt["sh"], "p": fmt["p"]}
    for r, line in enumerate(intro.get("lines", [])):
        k, t = line.get("k", "p"), line.get("t", "")
        if k == "blank" or not t:
            continue
        ws.write(r, 0, t, kind_fmt.get(k, fmt["p"]))


def _write_sheet(wb, fmt, sheet, results, mode):
    """寫入單一驗收工作表"""
    ws = wb.add_worksheet(sheet["tab"][:31])

    # 欄位佈局：checkbox 模式每個結果一欄；dropdown 模式單一「測試結果」欄
    col = {"cat": 0, "no": 1, "desc": 2}
    c = 3
    result_cols = []
    if mode == "checkbox":
        for opt in results:
            result_cols.append((opt, c))
            c += 1
    else:
        col["result"] = c
        c += 1
    col["tester"], col["date"], col["note"] = c, c + 1, c + 2
    last_col = col["note"]

    ws.set_column(col["cat"], col["cat"], W_CAT)
    ws.set_column(col["no"], col["no"], W_NO)
    ws.set_column(col["desc"], col["desc"], W_DESC)
    if mode == "checkbox":
        ws.set_column(result_cols[0][1], result_cols[-1][1], W_CB)
    else:
        ws.set_column(col["result"], col["result"], W_RESULT)
    ws.set_column(col["tester"], col["tester"], W_TESTER)
    ws.set_column(col["date"], col["date"], W_DATE)
    ws.set_column(col["note"], col["note"], W_NOTE)

    # 橫幅
    banner = sheet.get("banner") or (
        f"{sheet.get('title', sheet['tab'])}　—　"
        f"請於「{' / '.join(results)}」{'欄位點選核取方塊' if mode == 'checkbox' else '欄選擇結果'}，"
        f"並填寫測試人員／日期／備註"
    )
    ws.merge_range(0, 0, 0, last_col, banner, fmt["banner"])
    ws.set_row(0, 26)

    # 表頭
    hr = 1
    ws.write(hr, col["cat"], "評估項目", fmt["head"])
    ws.write(hr, col["no"], "項次", fmt["head"])
    ws.write(hr, col["desc"], "評估說明", fmt["head"])
    if mode == "checkbox":
        for opt, cc in result_cols:
            ws.write(hr, cc, opt, fmt["head"])
    else:
        ws.write(hr, col["result"], "測試結果", fmt["head"])
    ws.write(hr, col["tester"], "測試人員", fmt["head"])
    ws.write(hr, col["date"], "測試日期", fmt["head"])
    ws.write(hr, col["note"], "實測備註", fmt["head"])
    ws.set_row(hr, 30)
    ws.freeze_panes(hr + 1, 0)

    # 資料列
    row = hr + 1
    for group in sheet.get("groups", []):
        start = row
        items = group.get("items", [])
        for item in items:
            ws.write(row, col["no"], item.get("no", ""), fmt["no"])
            ws.write(row, col["desc"], item.get("desc", ""), fmt["desc"])
            if mode == "checkbox":
                for _, cc in result_cols:
                    ws.insert_checkbox(row, cc, False, fmt["cb"])
            else:
                ws.write_blank(row, col["result"], None, fmt["cell"])
                ws.data_validation(row, col["result"], row, col["result"], {
                    "validate": "list", "source": results,
                })
            ws.write_blank(row, col["tester"], None, fmt["cell"])
            ws.write_blank(row, col["date"], None, fmt["cell"])
            ws.write_blank(row, col["note"], None, fmt["desc"])
            ws.set_row(row, 24)
            row += 1
        # 評估項目欄垂直合併
        label = group.get("category", "")
        if row - start > 1:
            ws.merge_range(start, col["cat"], row - 1, col["cat"], label, fmt["cat"])
        elif row - start == 1:
            ws.write(start, col["cat"], label, fmt["cat"])


def build(spec, out_path, mode):
    results = spec.get("result_options") or DEFAULT_RESULTS
    wb = xlsxwriter.Workbook(out_path)
    fmt = _make_formats(wb)
    if spec.get("intro"):
        _write_intro(wb, fmt, spec["intro"])
    for sheet in spec.get("sheets", []):
        _write_sheet(wb, fmt, sheet, results, mode)
    wb.close()
    return out_path


def main():
    ap = argparse.ArgumentParser(description="UAT/驗收測試清單 xlsx 產生器")
    ap.add_argument("spec", help="spec.json 路徑")
    ap.add_argument("--out", help="輸出 xlsx 路徑（預設取 spec.output）")
    ap.add_argument("--mode", choices=["checkbox", "dropdown"], default=None,
                    help="checkbox=Excel 365 原生核取方塊（預設）；dropdown=下拉選單，相容舊版 Excel")
    args = ap.parse_args()

    with open(args.spec, encoding="utf-8") as f:
        spec = json.load(f)

    out_path = args.out or spec.get("output") or "uat_checklist.xlsx"
    # 優先序：命令列 --mode > spec.mode > 預設 checkbox
    mode = args.mode or spec.get("mode") or "checkbox"
    build(spec, out_path, mode)

    total = sum(len(g.get("items", [])) for s in spec.get("sheets", []) for g in s.get("groups", []))
    print(f"OK -> {out_path}　（{len(spec.get('sheets', []))} 個驗收分頁，{total} 個驗收項，mode={mode}）")


if __name__ == "__main__":
    main()
