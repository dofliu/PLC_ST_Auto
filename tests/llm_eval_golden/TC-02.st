PROGRAM StarDeltaStarter
VAR_INPUT
    start : BOOL;   (* Start pushbutton, momentary NO *)
    stop  : BOOL;   (* Stop input, TRUE = stop request; stop has priority *)
END_VAR
VAR_OUTPUT
    km_main  : BOOL; (* Main contactor *)
    km_star  : BOOL; (* Star contactor *)
    km_delta : BOOL; (* Delta contactor *)
END_VAR
VAR
    running   : BOOL;  (* Latched run command *)
    tmr_star  : TON;   (* Star running time: 5000 ms *)
    tmr_dead  : TON;   (* Star-to-delta dead time *)
END_VAR

(* Assumptions:
   - start is a momentary pushbutton, so the run command is latched internally.
   - stop is TRUE when a stop is requested. If a normally closed stop button is used,
     invert it at the input mapping.
   - A 100 ms dead time between km_star dropping out and km_delta pulling in
     is added as extra protection against short circuit (contactor arc/off delay).
   - No overload input was specified, so none is implemented. *)

(* Run latch, stop priority *)
running := (start OR running) AND NOT stop;

(* Star time of 5 s, started when running *)
tmr_star(IN := running, PT := T#5000ms);

(* Dead time starts when the star time has elapsed *)
tmr_dead(IN := running AND tmr_star.Q, PT := T#100ms);

(* Main contactor *)
km_main := running;

(* Star contactor: only during the star phase, interlocked with delta *)
km_star := running AND NOT tmr_star.Q AND NOT km_delta;

(* Delta contactor: after dead time, interlocked with star *)
km_delta := running AND tmr_dead.Q AND NOT km_star;

END_PROGRAM
