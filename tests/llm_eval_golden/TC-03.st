PROGRAM PackageCounter
VAR_INPUT
    sensor    : BOOL;   (* Photoelectric sensor: TRUE while a workpiece is detected *)
    reset_btn : BOOL;   (* Reset pushbutton: TRUE while pressed *)
END_VAR
VAR_OUTPUT
    package_ready : BOOL;  (* TRUE when the count reaches the package quantity *)
    count_value   : INT;   (* Current accumulated count, for display/monitoring *)
END_VAR
VAR
    cnt_ctu : CTU;         (* Standard IEC up-counter *)
    PACK_QTY : INT := 10;  (* Preset package quantity *)
END_VAR

(* Assumptions:
   - The CTU counts rising edges on its CU input internally (it contains an R_TRIG),
     so each workpiece passing is counted once per rising edge of sensor.
   - While reset_btn is TRUE, R is dominant: the counter is cleared to 0
     and package_ready (Q) is FALSE.
   - After reaching PV the CTU keeps counting further pulses and Q stays TRUE
     until reset; package_ready therefore stays latched until reset_btn is pressed. *)

cnt_ctu(CU := sensor,
        R  := reset_btn,
        PV := PACK_QTY);

package_ready := cnt_ctu.Q;
count_value   := cnt_ctu.CV;

END_PROGRAM
