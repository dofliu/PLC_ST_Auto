TYPE Motor : STRUCT
  speed : INT;
  run : BOOL;
END_STRUCT END_TYPE
PROGRAM P
VAR
  ms : ARRAY[0..2] OF Motor;
  best : INT;
END_VAR
ms[1].speed := 200;
ms[1].run := TRUE;
best := ms[1].speed;
END_PROGRAM
