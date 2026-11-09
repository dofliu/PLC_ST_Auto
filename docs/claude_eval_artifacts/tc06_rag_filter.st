PROGRAM AnalogMovingAvg5
VAR_INPUT
    raw_in : REAL;                      (* raw analog value *)
END_VAR
VAR_OUTPUT
    filter_out : REAL;                  (* filtered output *)
END_VAR
VAR
    buf : ARRAY[0..4] OF REAL := [0.0, 0.0, 0.0, 0.0, 0.0];  (* last 5 samples *)
    idx : INT := 0;                     (* write index 0..4 *)
    i   : INT;
    sum : REAL;
END_VAR

(* Assumption: the buffer starts at 0.0, so during the first 4 scans
   the average includes these initial zeros, as the standard's algorithm
   (sum of 5 points / 5.0) specifies. *)

(* Safety guard: keep the index within the valid range *)
IF (idx < 0) OR (idx > 4) THEN
    idx := 0;
END_IF;

(* Write the new sample into the buffer *)
buf[idx] := raw_in;

(* Sum the 5 points *)
sum := 0.0;
FOR i := 0 TO 4 DO
    sum := sum + buf[i];
END_FOR;

(* Moving average *)
filter_out := sum / 5.0;

(* Advance the circular index *)
idx := (idx + 1) MOD 5;

END_PROGRAM
