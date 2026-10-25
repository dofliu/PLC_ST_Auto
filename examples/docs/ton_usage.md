# TON 計時器

TON(接通延時):IN 為 TRUE 持續達 PT 後,Q 變 TRUE。呼叫:`t(IN := start, PT := T#2s);`,讀取 `t.Q` 與 `t.ET`。

# CTU 計數器

CTU 上升緣計數:`c(CU := pulse, R := reset, PV := 5);` 計數達 PV 時 `c.Q` 為 TRUE,`c.CV` 為目前值。
