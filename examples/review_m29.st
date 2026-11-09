(* M29 審查修正示範:8 個 BOOL、字串含 // ; (*、陣列邊界運算式、實例陣列初值 *)
TYPE Flags : STRUCT
  f0, f1, f2, f3, f4, f5, f6, f7 : BOOL;
  url : STRING := 'http://host/a;b';
  buf : ARRAY[0..2+1] OF INT := [1, 2];
END_STRUCT END_TYPE
PROGRAM Demo
VAR
  a : Flags := (buf := [10, 20, 30, 40]);
  b : Flags;
  hist : ARRAY[0..(1+1)*2] OF INT;
  i : INT;
  sum : INT;
END_VAR
a.f7 := TRUE;
sum := 0;
FOR i := 0 TO 3 DO sum := sum + a.buf[i] + b.buf[i]; END_FOR
hist[4] := sum;
END_PROGRAM
