(* M36:整個陣列傳入 VAR_IN_OUT / VAR_INPUT、陣列整體賦值 *)
FUNCTION SumAndDouble : DINT
VAR_IN_OUT data : ARRAY[1..5] OF INT; END_VAR
VAR i : INT; END_VAR
SumAndDouble := 0;
FOR i := 1 TO 5 DO
  SumAndDouble := SumAndDouble + data[i];
  data[i] := data[i] * 2;
END_FOR;
END_FUNCTION

FUNCTION_BLOCK ShiftReg
VAR_INPUT nv : INT; END_VAR
VAR_IN_OUT buf : ARRAY[0..4] OF INT; END_VAR
VAR k : INT; END_VAR
FOR k := 4 TO 1 BY -1 DO
  buf[k] := buf[k - 1];
END_FOR;
buf[0] := nv;
END_FUNCTION_BLOCK

FUNCTION MaxOf : INT
VAR_INPUT v : ARRAY[0..4] OF INT; END_VAR
VAR i : INT; END_VAR
MaxOf := v[0];
FOR i := 1 TO 4 DO
  IF v[i] > MaxOf THEN MaxOf := v[i]; END_IF;
END_FOR;
END_FUNCTION

PROGRAM Main
VAR_INPUT
  sample : INT;
END_VAR
VAR
  hist : ARRAY[0..4] OF INT;
  snap : ARRAY[0..4] OF INT;
  sh : ShiftReg;
  peak : INT;
END_VAR
sh(nv := sample, buf := hist);
snap := hist;
peak := MaxOf(snap);
END_PROGRAM
