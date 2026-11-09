PROGRAM MotorStartStop
VAR_INPUT
    start : BOOL; (* Start pushbutton, normally-open contact, TRUE = pressed *)
    stop  : BOOL; (* Stop pushbutton, TRUE = pressed *)
                  (* Assumption: stop is wired as a normally-open signal.
                     If a normally-closed stop button is used (the usual
                     fail-safe wiring), invert this signal before it is
                     connected to this program. *)
END_VAR
VAR_OUTPUT
    motor : BOOL; (* Contactor output *)
END_VAR

(* Seal-in (latching) circuit: the motor output is its own holding contact.
   The stop condition is ANDed last, so stop always has priority:
   if start and stop are pressed together, motor stays OFF. *)
motor := (start OR motor) AND NOT stop;

END_PROGRAM
