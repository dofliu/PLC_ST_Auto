PROGRAM FAN_CONTROL
VAR_INPUT
    run_cmd  : BOOL; (* Start pushbutton, normally open *)
    stop_cmd : BOOL; (* Stop command; assumption: TRUE = stop requested *)
END_VAR
VAR_OUTPUT
    fan_out  : BOOL; (* Fan contactor output *)
END_VAR
VAR
    fan_latch : BOOL; (* Internal seal-in memory *)
END_VAR

(* Assumptions:
   - Stop has priority over run (safety): if both buttons are pressed
     at the same time, the fan is stopped / stays off.
   - stop_cmd is treated as active-high (TRUE = stop pressed).
     For a wiring-fault-safe design, a normally-closed stop button
     would normally be used and inverted here.
   - The fan does not automatically restart after both buttons are
     released, because the stop command resets the latch; a new
     rising run_cmd with stop_cmd = FALSE is required.
   - Latch is not retained, so fan is off after power-up. *)

(* Stop-dominant seal-in logic *)
fan_latch := (run_cmd OR fan_latch) AND NOT stop_cmd;

fan_out := fan_latch;

END_PROGRAM
