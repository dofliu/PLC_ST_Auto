PROGRAM literals
VAR
    a : INT; b : REAL; t : TIME; c : INT; h : DINT; f : BOOL;
    m : ARRAY[0..4] OF INT := [2(1), 3(0)];
END_VAR
a := INT#5 + 16#FF + 2#1010 + 1_000;
b := INT_TO_REAL(a) + REAL#1.5;
t := INT_TO_TIME(250);
c := TIME_TO_INT(t) + REAL_TO_INT(2.6);
h := 8#17;
f := BOOL#1;
END_PROGRAM
