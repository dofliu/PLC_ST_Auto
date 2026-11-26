(* 配方槽:ARRAY OF STRUCT,且 STRUCT 內含 ARRAY 欄位(M41) *)
TYPE Recipe : STRUCT
  setp : ARRAY[1..3] OF INT := [100, 200, 300];
  hold : ARRAY[1..3] OF TIME;
  name : STRING := 'empty';
END_STRUCT
END_TYPE

FUNCTION_BLOCK StepRunner
VAR_INPUT run : BOOL; END_VAR
VAR_IN_OUT sp : ARRAY[1..3] OF INT; END_VAR
VAR_OUTPUT total : INT; END_VAR
VAR i : INT; END_VAR
total := 0;
FOR i := 1 TO 3 DO
  IF run THEN sp[i] := sp[i] + 1; END_IF;
  total := total + sp[i];
END_FOR;
END_FUNCTION_BLOCK

PROGRAM Main
VAR_INPUT
  slot : INT := 1;
  bump : BOOL;
  save : BOOL;
END_VAR
VAR_OUTPUT
  active : ARRAY[1..3] OF INT;
  sum : INT;
END_VAR
VAR
  slots : ARRAY[1..3] OF Recipe := [(name := 'A'), (setp := [10, 20, 30], name := 'B')];
  work : Recipe;
  runner : StepRunner;
  k : INT;
  n : INT;
END_VAR
n := LIMIT(1, slot, 3);
work := slots[n];                       (* 整個元素複製到單一 STRUCT *)
active := slots[n].setp;                (* 元素的陣列欄位整體讀出 *)
runner(run := bump, sp := slots[n].setp, total => sum);   (* VAR_IN_OUT 寫回元素的陣列欄位 *)
IF save THEN
  FOR k := 1 TO 3 DO
    slots[3].setp[k] := slots[n].setp[k] * 2;
  END_FOR;
  slots[3].name := 'copy';
END_IF;
END_PROGRAM
