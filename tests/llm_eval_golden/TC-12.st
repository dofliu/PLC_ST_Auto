PROGRAM HighSpeedProductionCounter
VAR_INPUT
    pulse : BOOL;   (* Sensor pulse input *)
    clear : BOOL;   (* Reset button: clears total_count to 0 *)
END_VAR
VAR_OUTPUT
    total_count : INT := 0;        (* Total production count, saturates at 32767 *)
    at_limit    : BOOL := FALSE;   (* TRUE when counter has reached the upper limit *)
END_VAR
VAR
    pulse_trig : R_TRIG;   (* Rising edge detector for pulse *)
END_VAR

(* Assumption: clear has priority over counting when both occur in the same scan. *)
(* Assumption: the rising edge detection is evaluated every scan; the pulse must be
   slower than the PLC scan time to be captured (a true high-speed input would require
   a hardware counter, which is outside standard IEC ST). *)

pulse_trig(CLK := pulse);

IF clear THEN
    total_count := 0;
ELSIF pulse_trig.Q THEN
    IF total_count < 32767 THEN
        total_count := total_count + 1;
    END_IF;
END_IF;

at_limit := (total_count >= 32767);

END_PROGRAM
