PROGRAM Motor
VAR_INPUT start : BOOL; stop : BOOL; END_VAR
VAR_OUTPUT motor : BOOL; END_VAR
VAR t : TON; cnt : INT; END_VAR
IF start AND NOT stop THEN motor := TRUE; END_IF;
IF stop THEN motor := FALSE; END_IF;
t(IN := motor, PT := T#500ms);
IF t.Q THEN cnt := cnt + 1; END_IF;
END_PROGRAM
