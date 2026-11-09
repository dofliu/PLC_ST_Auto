PROGRAM TempControl
VAR_INPUT
    temp_pv : REAL;   (* Process value (analog input, engineering units) *)
    temp_sp : REAL;   (* Setpoint *)
END_VAR
VAR_OUTPUT
    heater : BOOL;    (* Heater output *)
    cooler : BOOL;    (* Cooler output *)
END_VAR
VAR
    hyst : REAL := 2.0;   (* Hysteresis band +/- 2.0 around setpoint *)
END_VAR

(* Assumptions:
   - Inside the dead band (sp-2.0 <= pv <= sp+2.0) the outputs hold their
     previous state (latching on/off hysteresis behaviour), since the
     requirement does not specify otherwise.
   - Heater is switched off when the cooler is started (pv > sp+2.0).
   - Cooler is switched off when the heater is started (pv < sp-2.0).
     This guarantees heater and cooler are never on simultaneously.
   - Cooler stays on until the temperature falls below sp-2.0 (heating
     demand); heater stays on until pv exceeds sp+2.0. Adjust here if
     a different switch-off point (e.g. at setpoint) is desired. *)

IF temp_pv < (temp_sp - hyst) THEN
    heater := TRUE;
    cooler := FALSE;
ELSIF temp_pv > (temp_sp + hyst) THEN
    heater := FALSE;
    cooler := TRUE;
END_IF;

END_PROGRAM
