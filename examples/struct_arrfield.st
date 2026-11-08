TYPE Recipe : STRUCT
  id : INT := 5;
  steps : ARRAY[0..3] OF INT := [10, 20];
  grid : ARRAY[1..2, 1..2] OF REAL;
END_STRUCT END_TYPE
PROGRAM P
VAR
  r, backup : Recipe;
  i : INT;
  total : INT;
END_VAR
FOR i := 0 TO 3 DO r.steps[i] := r.steps[i] + i; END_FOR
r.grid[2, 1] := 2.5;
backup := r;
r.steps[0] := 99;
total := backup.steps[0] + backup.steps[3] + r.id;
END_PROGRAM
