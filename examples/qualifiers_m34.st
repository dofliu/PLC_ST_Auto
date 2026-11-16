(* M34:VAR CONSTANT / RETAIN / VAR_TEMP 與直接位址 AT %I/%Q/%M *)
PROGRAM Conveyor
VAR CONSTANT
  N : INT := 4;              (* 站數 *)
  MAX_COUNT : DINT := 1000;
END_VAR
VAR RETAIN
  total : DINT;              (* 斷電保持的累計數量 *)
END_VAR
VAR_TEMP
  i : INT;
  sum : INT := 0;
END_VAR
VAR
  start AT %IX0.0 : BOOL;
  sensor AT %IX0.1 : BOOL;
  motor AT %QX0.0 : BOOL;
  speed AT %QW2 : INT;
  full AT %MX1.0 : BOOL;
  slots : ARRAY[0..N - 1] OF INT := [1, 2, 3, 4];
  edge : R_TRIG;
  batch : DINT;
END_VAR
edge(CLK := sensor);
IF edge.Q AND total < MAX_COUNT THEN
  total := total + 1;
  batch := batch + 1;
END_IF;
FOR i := 0 TO N - 1 DO
  sum := sum + slots[i];
END_FOR;
motor := start AND NOT full;
full := total >= MAX_COUNT;
speed := sum * 10;   // 'start' in a string or (* start *) comment stays untouched
END_PROGRAM
