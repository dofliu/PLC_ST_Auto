PROGRAM Matrix
VAR
  m : ARRAY[1..2, 1..3] OF INT := [1, 2, 3, 4, 5, 6];
  i : INT := 1;
  j : INT := 1;
  total : INT;
END_VAR
total := 0;
FOR i := 1 TO 2 DO
  FOR j := 1 TO 3 DO
    total := total + m[i, j];
  END_FOR;
END_FOR;
m[2, 3] := m[2, 3] + 1;
END_PROGRAM
