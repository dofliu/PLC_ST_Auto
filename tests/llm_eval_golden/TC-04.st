PROGRAM TrafficLight
VAR_INPUT
    emergency : BOOL;   (* TRUE = force all-red mode immediately *)
END_VAR
VAR_OUTPUT
    green  : BOOL;
    yellow : BOOL;
    red    : BOOL;
END_VAR
VAR
    State      : INT := 0;      (* 0=green, 1=yellow, 2=red *)
    tGreen     : TON;
    tYellow    : TON;
    tRed       : TON;
END_VAR

(* Assumptions:
   - While emergency is TRUE: only red is ON, all timers are reset.
   - When emergency is released, the cycle restarts from State 0 (green)
     with a fresh 5 s timer.
   - Each state's timer runs only while that state is active. *)

IF emergency THEN
    State := 0;   (* restart cycle from green after emergency is cleared *)
    tGreen(IN := FALSE, PT := T#5s);
    tYellow(IN := FALSE, PT := T#2s);
    tRed(IN := FALSE, PT := T#5s);
    green  := FALSE;
    yellow := FALSE;
    red    := TRUE;
ELSE
    tGreen(IN := (State = 0), PT := T#5s);
    tYellow(IN := (State = 1), PT := T#2s);
    tRed(IN := (State = 2), PT := T#5s);

    CASE State OF
        0:  (* Green *)
            green  := TRUE;
            yellow := FALSE;
            red    := FALSE;
            IF tGreen.Q THEN
                State := 1;
            END_IF;

        1:  (* Yellow *)
            green  := FALSE;
            yellow := TRUE;
            red    := FALSE;
            IF tYellow.Q THEN
                State := 2;
            END_IF;

        2:  (* Red *)
            green  := FALSE;
            yellow := FALSE;
            red    := TRUE;
            IF tRed.Q THEN
                State := 0;
            END_IF;

    ELSE
        (* Invalid state: recover to green *)
        State := 0;
        green  := FALSE;
        yellow := FALSE;
        red    := TRUE;
    END_CASE;
END_IF;

END_PROGRAM
