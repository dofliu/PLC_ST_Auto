TYPE Motor : STRUCT
  speed : INT := 10;
  run : BOOL;
END_STRUCT END_TYPE
TYPE Line : STRUCT
  m : Motor;
  count : DINT;
END_STRUCT END_TYPE
PROGRAM P
VAR
  a : Motor := (speed := 50);
  l : Line := (count := 3, m := (speed := 7));
  t : TON;
END_VAR
a.run := a.speed > 20;
l.m.speed := l.m.speed + 1;
l.count := l.count + a.speed;
END_PROGRAM
