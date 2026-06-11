---
name: uat-checklist
description: UAT / 驗收測試清單產生工具。依功能範圍產出多分頁 Excel 驗收清單，每列含 Pass/Fail/N/A/Blocked 核取方塊與測試人員/日期/備註欄。當使用者提到「UAT」、「驗收清單」、「測試清單」、「驗收表」、「上線測試清單」時使用。
argument-hint: "[輸出檔名（可選）]"
disable-model-invocation: true
allowed-tools: Read, Write, Edit, Grep, Glob, Bash(python *), Bash(py *), Bash(*/python.exe *), Bash(pip install xlsxwriter*), Bash(git *), Bash(ls *), Bash(cp *)
---

# UAT / 驗收測試清單產生工具

依使用者指定的功能範圍，產出一份**多分頁 Excel 驗收清單**：每個分頁是一個功能模組，每列是一條可實測的黑箱驗收項，結果欄用 Pass / Fail / N/A / Blocked。

本工具**通用於任何專案 / 系統**，不限特定產品（這次可能是 RFP 分析、下次可能是別的系統）。因此每次使用都要**先確認「要驗收哪個系統、哪個上線階段」**，再依該系統「當前進度」設計驗收項目，不可沿用上一個專案的內容。

產生方式是「先由你（AI）寫一份 `spec.json`，再呼叫本 skill 資料夾的 `build_checklist.py` 產出 xlsx」。資料與產生器分離，之後改項目只要改 spec 重跑。

## 執行流程

1. **先確認目標系統與驗收階段**（每次必做，不可跳過）
   - 先問清楚：這次要驗收**哪一個系統 / 產品**？要驗收**哪一個階段 / 上線批次**（例如「第一階段上線」「v2.0 UAT」「某模組驗收」）？
   - 釐清該階段的邊界：**這次涵蓋什麼、不涵蓋什麼**——未開放或屬下一階段的功能要列出但標 N/A，不要當成缺漏。
   - 主動讀該專案的「進度 / 範圍來源」推斷已完成功能（依專案而定，常見有）：甘特圖 / roadmap（如 `甘特圖/data.json`）、`CLAUDE.md`、`CHANGELOG.md`、release notes、issue / 里程碑清單、上線說明文件。**找不到就直接問使用者**，不要臆測。
   - 若使用者已給功能清單（如上線說明），以那份為準，但仍要回頭與使用者確認階段邊界與已知限制。

2. **設計分頁與項目**（最重要）
   - 一個**使用者操作流程 / 功能模組 = 一個分頁**（tab）。
   - 項目要寫成**使用者視角、可實測的黑箱描述**：「系統可…」「可匯出…」「XX 可編輯」，不要寫成開發任務名稱。
   - 用三層：`評估項目`（群組，如「A1. 連線與環境」）→ `項次`（如 `A1-1`）→ `評估說明`（一句話）。
   - 項次前綴用該分頁的英數縮寫（RFP / CV / EX…）方便溝通。
   - 尚未開放或屬「下一階段」的功能**仍列出**，但在說明裡標明預期填 N/A，避免驗收者誤判為缺漏。

3. **寫 spec.json**（格式見下）。建議第一個分頁放 `intro`（說明與範圍：結果定義、填寫方式、本次範圍、已知限制、測試環境）。

4. **產生 xlsx**
   - 找一個能用的 python 直譯器並確保有 `xlsxwriter`（若該專案有自己的 venv 優先用它；偵測不到就 `pip install xlsxwriter`）。
   - `python <本skill路徑>/build_checklist.py spec.json --out 輸出.xlsx`（spec.json 放專案內或暫存皆可）
   - 預設 `checkbox` 模式（Excel 365 原生核取方塊）。使用者用舊版 Excel 或要相容性 → 加 `--mode dropdown`（下拉選單）。

5. **回報**：檔案位置、分頁數、總項數，並提醒：原生核取方塊只在 **Excel 365 / 網頁版**才顯示為可點方塊，舊版會顯示 TRUE/FALSE（可改 dropdown 模式）。

## spec.json 結構

```json
{
  "output": "XXX_驗收清單.xlsx",
  "mode": "checkbox",
  "result_options": ["Pass", "Fail", "N/A", "Blocked"],
  "intro": {
    "tab": "0.說明與範圍",
    "lines": [
      {"k": "title", "t": "XXX 上線測試／驗證清單"},
      {"k": "sub",   "t": "範圍：…　｜　上線日：YYYY-MM-DD"},
      {"k": "h",     "t": "一、測試結果定義"},
      {"k": "p",     "t": "Pass：符合預期 …"},
      {"k": "blank", "t": ""}
    ]
  },
  "sheets": [
    {
      "tab": "1.功能模組A",
      "title": "功能模組 A",
      "groups": [
        {
          "category": "A1. 子分類",
          "items": [
            {"no": "A1-1", "desc": "系統可…（可實測描述）"},
            {"no": "A1-2", "desc": "…"}
          ]
        }
      ]
    }
  ]
}
```

欄位說明：
- `mode`：`checkbox`（預設）或 `dropdown`；命令列 `--mode` 會覆寫此值。
- `result_options`：結果欄選項，可自訂（如只要 `["Pass","Fail"]`）。checkbox 模式下每個選項是一個核取方塊欄。
- `intro.lines[].k`：`title` / `sub` / `h`（小節標題）/ `p`（內文）/ `blank`（空行）。
- 每個 `sheet` 的 `tab` 名稱會被截到 31 字（Excel 上限），避免過長或含 `: \ / ? * [ ]`。

## 產出版式

| 評估項目 | 項次 | 評估說明 | Pass | Fail | N/A | Blocked | 測試人員 | 測試日期 | 實測備註 |
|---|---|---|---|---|---|---|---|---|---|

- 首列藍色橫幅、第二列為表頭並凍結，`評估項目`同群組垂直合併。
- dropdown 模式時 4 個結果欄合併為單一「測試結果」下拉欄。

## 參考

同資料夾 `example_spec.json` 是**其中一個專案**的完整實例（BCCS 建議書系統第一階段上線，11 分頁 / 95 項），**僅供版式與結構參考**。實際內容務必依「當次目標系統與其階段」重寫，**不要照抄 BCCS 的項目**。
