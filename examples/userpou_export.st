(* M33:自訂 FUNCTION / FUNCTION_BLOCK 匯出範例(PLCopen XML、Siemens SCL) *)
FUNCTION Scale : REAL
VAR_INPUT raw : INT; hi : REAL; END_VAR
VAR k : REAL := 100.0; END_VAR
Scale := INT_TO_REAL(raw) * hi / k;
END_FUNCTION

FUNCTION Clamp : INT
VAR_INPUT x : INT; lo : INT; top : INT; END_VAR
IF x > top THEN
  Clamp := top;
  RETURN;
END_IF;
Clamp := MAX(x, lo);
END_FUNCTION

FUNCTION_BLOCK Latch
VAR_INPUT set : BOOL; rst : BOOL; END_VAR
VAR_OUTPUT q : BOOL; n : INT; END_VAR
VAR rt : R_TRIG; END_VAR
rt(CLK := set);
IF rt.Q THEN n := n + 1; END_IF;
IF set THEN q := TRUE; END_IF;
IF rst THEN q := FALSE; END_IF;
END_FUNCTION_BLOCK

PROGRAM Main
VAR_INPUT start : BOOL; stop : BOOL; level_raw : INT; END_VAR
VAR_OUTPUT pump : BOOL; level : REAL; starts : INT; duty : INT; END_VAR
VAR l1 : Latch; msg : STRING := 'Clamp(1, 2)'; END_VAR
level := Scale(level_raw, 200.0);            (* 位置引數 *)
duty := Clamp(REAL_TO_INT(Scale(raw := level_raw, hi := 100.0)), 0, 80);
l1(set := start, rst := stop);
pump := l1.q;
starts := l1.n;
END_PROGRAM
