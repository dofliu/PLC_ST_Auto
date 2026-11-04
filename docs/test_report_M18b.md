# M18b 測試報告(PLCopen XML schema 驗證)
日期:2026-11-04

## 問題
1. 陣列初值在 `<initialValue>` 下直接放多個 `<value>`;TC6 規定 `initialValue` 只能含一個值
   (simpleValue / arrayValue / structValue),xmllint 以 XSD 驗證失敗:
   `Element 'value': This element is not expected. Expected is one of (simpleValue, ...)`。
2. 加入 schema 驗證後另發現:`STRING` 被輸出為 `<STRING/>`,TC6 規定為小寫 `<string/>`。
   含 STRING 變數的程式先前匯出的 XML 都不合 schema。

## 修正
- 陣列初值改為 `<initialValue><arrayValue><value><simpleValue value=".."/></value>…</arrayValue></initialValue>`。
- 型別對應抽成 `_tc6_type()`:STRING/WSTRING → `<string/>`/`<wstring/>`。
- `validate_plcopen(xml)`(lxml + `plc_st/schemas/tc6_xml_v201.xsd`),CLI `export --format plcopen --validate`。

## 測試
`python -m unittest discover -s tests` → 112 項全部 OK(新增 `tests/test_plcopen_schema.py` 5 項):
- 涵蓋 VAR_INPUT/OUTPUT/IN_OUT/VAR、FB 實例、負下界陣列、REAL/BOOL 陣列、STRING(含 `<&` 跳脫)、TIME 初值 → 通過 XSD。
- 陣列初值確實含 `<arrayValue>`;移除包覆後的 XML 會被判定為不合法(確認驗證有效)。
- `examples/*.st` 全部通過;CLI `--validate` 輸出 `schema: OK`。
- 修正前以 xmllint 實測:陣列程式 fails to validate;修正後 validates。

## 備註
- 未安裝 lxml 時 schema 測試自動略過(核心仍為純 stdlib)。
- 本次未改動 Web UI,未重跑 UI 截圖。XSD 驗證只檢查結構,仍需在目標 IDE 實際匯入確認。
