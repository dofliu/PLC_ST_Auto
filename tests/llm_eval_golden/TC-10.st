PROGRAM PumpStartStop
VAR_INPUT
    start : BOOL;   (* Start pushbutton, normally open: TRUE = pressed *)
    stop  : BOOL;   (* Stop pushbutton: TRUE = pressed (assumption: NO contact, no fail-safe wiring) *)
END_VAR
VAR_OUTPUT
    pump      : BOOL;  (* Pump contactor command *)
    run_hours : INT;   (* Accumulated full running hours; held at 32767 max *)
END_VAR
VAR
    pump_latch : BOOL := FALSE;
    hour_timer : TON;
END_VAR

(* Classic seal-in circuit; stop has priority over start *)
pump_latch := (start OR pump_latch) AND NOT stop;
pump := pump_latch;

(* Run-hour counter: 1 h timer runs only while pump is on.
   Assumption: partial hours are lost when the pump stops (timer resets);
   run_hours is not retentive across power cycles unless the vendor makes it so. *)
hour_timer(IN := pump_latch AND NOT hour_timer.Q, PT := T#1h);

IF hour_timer.Q THEN
    IF run_hours < 32767 THEN
        run_hours := run_hours + 1;
    END_IF;
END_IF;

END_PROGRAM
