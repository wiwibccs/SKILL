---
name: refactor
description: 模組化重構檢查工具。依據 CLAUDE.md 模組化規範，掃描超過 500 行的程式碼檔案，列出違規總數與前 10 名供使用者選擇，一支一支拆分。當使用者提到「重構」、「refactor」、「拆分」、「模組化」時使用。
argument-hint: "[檔案路徑（可選，直接指定要拆的檔案，跳過掃描）]"
disable-model-invocation: true
allowed-tools: Read, Edit, Write, Grep, Glob, Bash(git *), Bash(npx tsc *), Bash(npm run lint*), Bash(wc *), Bash(python -c *), Bash(python -m py_compile *)
---

# 模組化重構檢查工具

依據 CLAUDE.md 模組化規範，掃描超過 500 行的程式碼檔案，由使用者選擇要拆分的目標，一次只拆一支。

- **無參數** `/refactor`：執行完整掃描，顯示前 10 名供選擇
- **帶參數** `/refactor path/to/file.py`：跳過掃描，直接拆分指定檔案

## 執行流程

### 第一階段：掃描與總覽

> 若使用者已透過參數指定檔案，跳過本階段，直接進入第二階段。

1. **掃描專案程式碼**：檢查所有 `.ts`、`.tsx`、`.js`、`.py` 檔案的行數
   - **排除目錄**：`venv/`、`node_modules/`、`dist/`、`build/`、`__pycache__/`、`.git/`
2. **找出違規檔案**：列出所有超過 500 行的程式碼檔案
3. **顯示總覽**：
   - 先告知使用者**違規檔案總數**（例如：「共有 23 個檔案超過 500 行」）
   - 再顯示**前 10 名**最需要拆分的檔案評估表格（依行數由多到少排序）：

| # | 檔案路徑 | 行數 | 主要功能 | 建議拆分方案 | 可行性 | 優先順序 |
|---|---------|------|---------|------------|--------|---------|
| 1 | xxx.ts  | 892  | ...     | ...        | 高     | P0      |
| 2 | xxx.py  | 756  | ...     | ...        | 高     | P0      |
| ... | ... | ... | ... | ... | ... | ... |

4. **等待使用者選擇**：使用 AskUserQuestion 詢問使用者要拆哪一支（提供前 10 名作為選項）

### 第二階段：拆分選定的檔案

使用者選定後（或透過參數指定後），**只拆分該支檔案**：

#### 步驟 0：建立 Git 基線快照

在做任何修改前，建立可靠的比對基準：

```bash
STASH_SHA=$(git stash create)
```

- 若 `STASH_SHA` 非空：以此作為 `BASELINE_REF`（包含未提交修改的完整快照）
- 若 `STASH_SHA` 為空：使用 `HEAD` 作為 `BASELINE_REF`
- 後續用 `git show BASELINE_REF:<相對路徑>` 取得拆分前原始碼
- 記住此 `BASELINE_REF`，同時用於驗收比對與回滾還原

> `git stash create` 是 plumbing 指令，只建立 stash 物件，不修改工作目錄也不影響 stash list。

#### 步驟 1：分析與拆分

- 識別獨立功能區塊
- 將功能拆分為 core（核心邏輯）與 utils（工具函數），或依功能職責拆分為多個獨立檔案
- 確保每個拆分後的檔案都在 500 行以下

#### 步驟 2：執行規則

- 不可破壞既有公開介面（export 保持不變）
- 原檔案保留為 index / 入口，re-export 拆分後的模組
- 確保所有 import 引用都已更新
- 拆分後的檔案需加入檔頭註解

#### 步驟 3：行數檢查

拆分完成後，檢查每個結果檔案的行數。若任一檔案仍超過 500 行：

```
WARNING: [檔名] 仍有 [N] 行（超過 500 行上限）
此檔案應在下次 /refactor 中繼續拆分。
```

#### 回滾機制

若拆分過程中方向錯誤或使用者要求放棄，使用 `BASELINE_REF` 還原：

```bash
git checkout BASELINE_REF -- <原檔案相對路徑>
```

並手動刪除本次新建的拆分檔案。回滾後終止流程，不進入後續階段。

### 第 2.5 階段：自動正確性驗收（拆分後必做）

拆分完成後、產出驗收清單前，**必須自動執行正確性驗收**：

#### TypeScript / TSX / JS 檔案

1. **編譯檢查**（僅 TS/TSX）：`npx tsc --noEmit`
2. **Lint 檢查**：`npm run lint`（僅關注新增錯誤，忽略既有警告）
3. **Export 清單比對**：
   - 用 Grep 從 `git show BASELINE_REF:<路徑>` 提取原始 export 清單
   - 用 Grep 從新入口檔提取目前 export 清單
   - 比對：所有原始 export 必須仍然存在

#### Python 檔案

1. **AST export 比對**：
   分別對原始檔（透過 git show 取得）和新入口檔執行以下指令，比對兩份清單是否一致：
   ```bash
   python -c "
   import ast, json, sys
   src = sys.stdin.read()
   tree = ast.parse(src)
   names = []
   for node in ast.iter_child_nodes(tree):
       if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
           if not node.name.startswith('_'): names.append(node.name)
       elif isinstance(node, ast.ClassDef):
           if not node.name.startswith('_'): names.append(node.name)
       elif isinstance(node, ast.Assign):
           for t in node.targets:
               if isinstance(t, ast.Name) and t.id.isupper(): names.append(t.id)
   all_node = [n for n in ast.iter_child_nodes(tree)
                if isinstance(n, ast.Assign)
                for t in n.targets if isinstance(t, ast.Name) and t.id == '__all__']
   if all_node:
       val = ast.literal_eval(all_node[0].value)
       names = list(val)
   print(json.dumps(sorted(set(names))))
   " < <檔案路徑>
   ```
   - 所有原始公開名稱必須仍可從新入口匯入
   - 若原始檔定義了 `__all__`，以 `__all__` 為準

2. **Import 鏈語法驗證**：
   ```bash
   python -m py_compile <每個新檔案>
   ```
   確認語法正確且無明顯遺失

3. **可選 pytest 提示**：
   若 `tests/` 目錄中存在與拆分檔案相關的測試檔案：
   - 報告：「找到相關測試：tests/test_xxx.py」
   - 建議：「請在本次拆分完成後手動執行測試」
   - **不自動執行**（測試可能依賴 DB/網路環境）

#### 通用檢查（所有語言皆執行）

4. **Diff 分析**：
   - 執行 `git diff BASELINE_REF -- <原檔案路徑>`
   - 確認從原檔移除的程式碼行，都出現在新拆分檔案中（邏輯搬移而非遺失）

5. **行數報告**：每個結果檔案標示行數，超過 500 行標記 WARNING

#### 輸出格式

```
=== 自動正確性驗收 ===

[TypeScript] / [JavaScript] / [Python] 模式

CHECK 1: 編譯 / 語法
  tsc --noEmit: PASS（或 N/A for JS）
  （或 py_compile: 全部 [N] 個檔案 PASS）

CHECK 2: Export 比對
  原始 exports: [N] 項
  新入口 exports: [N] 項
  遺漏: 無
  PASS

CHECK 3: Import 鏈（Python）/ Lint（TypeScript/JS）
  PASS

CHECK 4: Diff 分析
  原檔移除行數: [N]
  拆分檔案中找到: [N]
  未對應行數: 0
  PASS

CHECK 5: 行數檢查
  [檔案1]: [N] 行 -- OK
  [檔案2]: [N] 行 -- WARNING: 超過 500

可選: 找到相關測試 tests/test_xxx.py，建議手動執行。

=== 結論：全部通過 / 有 [N] 項問題需修正 ===
```

#### 失敗處理

- 有 FAIL：**立即修正**拆分後的程式碼，重新驗收直到全部 PASS
- 多次修正仍無法通過：詢問使用者是否回滾（見第二階段回滾機制）
- 全部 PASS：繼續進入第三階段
- **嚴禁跳過此步驟**

---

### 第三階段：驗收清單 + 清理

拆分完成並通過自動驗收後，產出功能面驗收清單：

```
功能面驗收清單
拆分日期：YYYY-MM-DD
原始檔案：[原檔案路徑]（[原行數] 行）
拆分結果：[N] 個檔案（各檔行數）

拆分前後對照：
[原檔案] -> [拆分後檔案清單]

編譯檢查：
- [ ] TypeScript / JavaScript / Python 編譯無錯誤
- [ ] 無新增的 Lint 警告

頁面 / 端點載入（動態偵測）：
（前端：從 router 或 CLAUDE.md 頁面結構表格偵測受影響路由）
（後端：從 api/ 路由檔偵測呼叫拆分服務的端點）
- [ ] [路由/端點] ([名稱]) 正常運作
- [ ] ...
若為純工具模組：「N/A（工具模組，無直接頁面/端點依賴）」

功能驗收（依拆分影響範圍動態生成）：
- [ ] [功能區域] - [具體可操作的測試動作]
- [ ] ...
```

**偵測規則**：
- 前端拆分：解析 `router/index.tsx`（或類似路由檔），僅列出 import 鏈涉及拆分模組的頁面
- 後端拆分：用 Grep 搜尋 `api/` 目錄中 import 了拆分模組的路由檔，列出對應端點
- 工具模組：無直接頁面/端點依賴時標示 N/A

**同步執行清理**：
- 檢查是否有未使用的舊檔案
- 移除廢棄程式碼

### 第四階段：文檔更新 + 提交 + 標完工

驗收清單產出後，**依序執行收尾工作**：

1. **更新架構依賴圖**：更新拆分檔案所屬模組的 `CLAUDE.md` 架構依賴圖
2. **更新接口契約**（如有 API 變更）：同步更新 `API_CONTRACT.md`
3. **記錄變更日誌**：更新 `CHANGELOG.md`，格式：`[重構] vX.Y.Z: [模組名稱] 模組化拆分（原行數 -> N 模組）`
4. **Git commit**：
   - `git add` 所有相關變更檔案
   - commit 訊息格式：`[重構] vX.Y.Z: [模組名稱] 模組化拆分（原行數 -> N 模組）`
5. **詢問是否推送**：使用 AskUserQuestion 詢問「是否推送到遠端？」
   - 使用者同意：執行 `git push`
   - 使用者拒絕：跳過，提醒稍後手動推送
6. **完工摘要**：
   - 輸出拆分結果：從幾行變成幾個檔案、版本號
   - 若有仍超過 500 行的檔案，再次提醒
   - 提示：**「請清空 CLI 後重新執行 /refactor 繼續拆下一支」**

## 注意事項

- 嚴格遵守「一個功能一支程式」原則
- 拆分後每支程式碼不得超過 500 行
- 拆分後的程式碼需加入檔頭註解
- 所有註解使用繁體中文
- 使用 UTF-8 編碼
- 不可破壞既有公開介面（export 不變）
- 驗收清單必須具體到可操作的測試動作
- **一次只拆一支檔案**，拆完後結束
- 使用者需清空 CLI 重新執行 `/refactor` 來拆下一支（避免 context 過長）
- 本 Skill 主要在 Windows 上執行，避免 Unix-only 路徑假設（不使用 `/tmp/`）
- **禁止自動推送遠端**，必須詢問使用者
