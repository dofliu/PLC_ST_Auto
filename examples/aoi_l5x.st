(* M35:自訂 FUNCTION_BLOCK → Rockwell L5X Add-On Instruction 匯出範例 *)
FUNCTION_BLOCK Latch
VAR_INPUT set : BOOL; rst : BOOL; END_VAR
VAR_OUTPUT q : BOOL; n : INT; END_VAR
VAR rt : R_TRIG; END_VAR
rt(CLK := set);
IF rt.Q THEN n := n + 1; END_IF;
IF set THEN q := TRUE; END_IF;
IF rst THEN q := FALSE; END_IF;
END_FUNCTION_BLOCK

FUNCTION_BLOCK Accum
VAR_INPUT add : DINT := 1; go : BOOL; END_VAR
VAR_IN_OUT shared : DINT; END_VAR
VAR_OUTPUT total : DINT; END_VAR
VAR CONSTANT LAST : INT := 3; END_VAR
VAR i : INT; inner : Latch; buf : ARRAY[0..3] OF DINT := [1, 2, 3, 4]; END_VAR
inner(set := go, rst := FALSE);
IF inner.q THEN
  total := 0;
  FOR i := 0 TO LAST DO
    buf[i] := buf[i] + add;
    total := total + buf[i];
  END_FOR;
  shared := shared + total;
END_IF;
END_FUNCTION_BLOCK

PROGRAM Main
VAR_INPUT start : BOOL; stop : BOOL; END_VAR
VAR_OUTPUT pump : BOOL; starts : INT; sum : DINT; END_VAR
VAR l1 : Latch; acc : Accum; pool : DINT; END_VAR
l1(set := start, rst := stop, q => pump);
starts := l1.n;
IF start THEN
  acc(add := 10, go := start, shared := pool, total => sum);
END_IF;
END_PROGRAM
