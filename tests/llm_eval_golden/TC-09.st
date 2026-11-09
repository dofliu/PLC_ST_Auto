PROGRAM DualMotorSequence
VAR_INPUT
    start : BOOL;
    stop  : BOOL;
END_VAR
VAR_OUTPUT
    motor1 : BOOL;
    motor2 : BOOL;
END_VAR
VAR
    delay2 : TON;
END_VAR
(* Assumption: start is momentary; stop has priority *)
motor1 := (start OR motor1) AND NOT stop;
delay2(IN := motor1, PT := T#3s);
motor2 := motor1 AND delay2.Q;
END_PROGRAM
