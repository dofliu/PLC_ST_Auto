FUNCTION Bump : INT
VAR_INPUT step : INT; END_VAR
VAR_IN_OUT v : INT; END_VAR
v := v + step;
Bump := v;
END_FUNCTION

FUNCTION_BLOCK Acc
VAR_INPUT d : INT; END_VAR
VAR_IN_OUT total : INT; END_VAR
total := total + d;
END_FUNCTION_BLOCK

PROGRAM P
VAR
  x : INT := 1; r : INT; y : INT := 10;
  a1 : Acc;
END_VAR
r := Bump(step := 2, v := x);
a1(d := 5, total := y);
END_PROGRAM
