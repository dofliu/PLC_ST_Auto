TYPE Motor : STRUCT
  speed : INT := 10;
  run : BOOL;
END_STRUCT END_TYPE
PROGRAM P
VAR
  ms : ARRAY[1..3] OF Motor := [(speed := 100, run := TRUE), (speed := 200)];
  tmp : Motor;
  best : INT;
END_VAR
tmp := ms[1];
ms[3] := ms[2];
ms[2] := tmp;
best := ms[3].speed;
END_PROGRAM
