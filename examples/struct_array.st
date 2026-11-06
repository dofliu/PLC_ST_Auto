TYPE Motor : STRUCT
  speed : INT := 10;
  run : BOOL;
END_STRUCT END_TYPE
PROGRAM P
VAR
  ms : ARRAY[1..3] OF Motor;
  i : INT;
  total : INT;
END_VAR
total := 0;
FOR i := 1 TO 3 DO
  ms[i].speed := ms[i].speed + i;
  ms[i].run := ms[i].speed > 11;
  total := total + ms[i].speed;
END_FOR;
END_PROGRAM
