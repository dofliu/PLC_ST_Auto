(* M37:直接位址共用記憶體。
   %IB0 是整個輸入位元組,start / stop 是其中的位元;%MW0 狀態字與 %MX 旗標共用位元組。
   位元組順序依 profile:IEC/CODESYS 為 little-endian(%MX0.0 = %MW0 bit 0),
   Siemens 為 big-endian(%M0.0 = %MW0 bit 8,%M1.0 = bit 0)。 *)
PROGRAM SharedMem
VAR
    inByte  AT %IB0   : BYTE;     (* 整個輸入位元組:可一次強制 8 個輸入 *)
    start   AT %IX0.0 : BOOL;
    stop    AT %IX0.1 : BOOL;
    status  AT %MW0   : WORD;     (* 狀態字,例如送到 HMI *)
    running AT %MX0.0 : BOOL;     (* IEC:status 的 bit 0;Siemens:bit 8 *)
    alarm   AT %MX1.7 : BOOL;     (* IEC:status 的 bit 15;Siemens:bit 7 *)
    motor   AT %QX0.0 : BOOL;
    outByte AT %QB0   : BYTE;
END_VAR
IF start AND NOT stop THEN
    running := TRUE;
ELSIF stop THEN
    running := FALSE;
END_IF;
alarm := start AND stop;
motor := running;
END_PROGRAM
