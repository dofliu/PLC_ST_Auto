PROGRAM m32
VAR
  msg : STRING := 'it$'s $$5$N';
  n : INT;
  r : REAL := 2.5;
  rounded : INT;
  cnt : INT;
END_VAR
n := LEN(msg);
rounded := r;            (* 2.5 -> 3 (遠離零) *)
FOR cnt := 0 TO 10 DO
  IF cnt = 4 THEN EXIT; END_IF
END_FOR
END_PROGRAM
