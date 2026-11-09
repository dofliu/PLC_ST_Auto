PROGRAM water_tank_control
VAR_INPUT
  emergency_stop : BOOL := false; (* 現場急停開關 *)
  high_level_sw : BOOL := false; (* 水槽高水位浮球 *)
  low_level_sw : BOOL := false; (* 水槽低水位浮球 *)
END_VAR
VAR_OUTPUT
  inlet_valve : BOOL := false; (* 進水電磁閥 *)
  drain_pump : BOOL := false; (* 排水泵浦 *)
  alarm_lamp : BOOL := false; (* 水位警報燈 *)
END_VAR
VAR
  fill_time : TIME := T#0s; (* 進水累計時間 *)
  fill_timer : TON;
END_VAR

(* Assumptions:
   - emergency_stop = TRUE means emergency active (TRUE = stop requested).
   - low_level_sw = TRUE means water is at or below the low level.
   - high_level_sw = TRUE means water is at or above the high level.
   - Inlet valve latches on at low level and stays on until high level
     (the requirement does not specify the hold behaviour).
   - Drain pump starts at high level and stops when low level is reached
     (stop condition is not specified in the requirement).
   - fill_time shows the elapsed time of the current filling run and
     resets to 0 when the inlet valve closes (TON elapsed time, max 1 h). *)

IF emergency_stop THEN
  (* Emergency: everything off, alarm lamp on *)
  inlet_valve := FALSE;
  drain_pump  := FALSE;
  alarm_lamp  := TRUE;
ELSE
  alarm_lamp := FALSE;

  IF high_level_sw THEN
    (* High level: close inlet, start drain pump *)
    inlet_valve := FALSE;
    drain_pump  := TRUE;
  ELSIF low_level_sw THEN
    (* Low level and not high: open inlet, stop pump *)
    inlet_valve := TRUE;
    drain_pump  := FALSE;
  ELSE
    (* Between levels: keep previous state (hysteresis);
       inlet and pump are never on at the same time *)
    IF inlet_valve AND drain_pump THEN
      inlet_valve := FALSE;
    END_IF;
  END_IF;
END_IF;

(* Fill time measurement *)
fill_timer(IN := inlet_valve, PT := T#1h);
fill_time := fill_timer.ET;

END_PROGRAM
