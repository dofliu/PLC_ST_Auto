# M16 測試報告(CTUD 計數器 + 標準函式擴充)
日期:2026-11-02

## 單元測試
`python -m unittest discover -s tests` → 92 項全部 OK(新增 1 項)。
- CTUD(CU/CD/R/LD、QU/QD)上數、下數、重置。
- 新函式:ASIN/ACOS/ATAN、FLOOR/CEIL、REAL_TO_DINT、SHL/SHR/ROL/ROR、LEN/CONCAT/LEFT/RIGHT 等。

## UI 功能測試(Playwright + Chromium)
13 項全部 PASS。截圖:`docs/screenshots/web_ui.png`

## 已知限制
- ROL/ROR 固定以 16 位元運算;字串函式為簡化版。
