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
  b : Motor;
  l : Line;
END_VAR
a.run := TRUE;
b := a;          (* whole-STRUCT copy *)
l.m := b;        (* nested STRUCT copy *)
l.count := l.count + 1;
a.speed := a.speed + 1;
END_PROGRAM
