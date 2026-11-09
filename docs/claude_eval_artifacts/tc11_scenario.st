PROGRAM FireAlarmSystem
VAR_INPUT
    fire_sensor : BOOL;   (* TRUE = fire detected *)
    ack_btn     : BOOL;   (* acknowledge push button *)
END_VAR
VAR_OUTPUT
    alarm : BOOL;         (* alarm output, latched *)
    siren : BOOL;         (* buzzer output, latched *)
END_VAR
VAR
    tmr_siren : TON;
    ack_edge  : R_TRIG;
END_VAR

(* Assumptions:
   - alarm and siren are latched: they stay TRUE even if the fire signal
     disappears, until the fire is cleared AND ack_btn is pressed.
   - Acknowledge is evaluated on the rising edge of ack_btn, and only
     when fire_sensor is FALSE at that moment.
   - If fire_sensor is active again, the alarm is set again immediately
     (fire has priority over reset).
   - The 400 ms timer runs only while fire_sensor is continuously TRUE;
     siren is latched once the timer elapses. *)

(* Siren delay timer: fire continuously present for 400 ms *)
tmr_siren(IN := fire_sensor, PT := T#400ms);

(* Acknowledge button edge detection *)
ack_edge(CLK := ack_btn);

(* Set: alarm immediately on fire *)
IF fire_sensor THEN
    alarm := TRUE;
END_IF;

(* Set: siren after fire lasted more than 400 ms *)
IF tmr_siren.Q THEN
    siren := TRUE;
END_IF;

(* Reset: fire cleared and acknowledge pressed (fire has priority) *)
IF ack_edge.Q AND NOT fire_sensor THEN
    alarm := FALSE;
    siren := FALSE;
END_IF;

END_PROGRAM
