PROGRAM Conveyor_Control
VAR_INPUT
    start        : BOOL;   (* 啟動按鈕 (常開, 按下=TRUE) *)
    stop         : BOOL;   (* 停止按鈕 (假設為常開, 按下=TRUE; 若為常閉接線請於輸入映射時反相) *)
    item_trigger : BOOL;   (* 光電開關, 物件通過時為 TRUE *)
    count_reset  : BOOL;   (* 產量歸零按鈕 (額外提供, 非必要) *)
END_VAR
VAR_OUTPUT
    conveyor     : BOOL;   (* 輸送帶馬達運轉輸出 *)
    item_count   : DINT;   (* 累計產量 *)
END_VAR
VAR
    run_latch    : BOOL;   (* 運轉自保持 *)
    trig_item    : R_TRIG; (* 光電開關上升緣偵測, 避免同一物件重複計數 *)
END_VAR

(* 假設: 停止優先於啟動; 僅在輸送帶運轉時才累計產量 *)
run_latch := (start OR run_latch) AND NOT stop;
conveyor  := run_latch;

(* 光電開關上升緣偵測 *)
trig_item(CLK := item_trigger);

IF count_reset THEN
    item_count := 0;
ELSIF trig_item.Q AND run_latch THEN
    IF item_count < 2147483647 THEN   (* 防止 DINT 溢位 *)
        item_count := item_count + 1;
    END_IF;
END_IF;

END_PROGRAM
