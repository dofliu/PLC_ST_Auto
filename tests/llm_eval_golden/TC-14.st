PROGRAM CoolingTower
VAR_INPUT
    start : BOOL;
    stop  : BOOL;
END_VAR
VAR_OUTPUT
    pump : BOOL;
END_VAR
pump := (start OR pump) AND NOT stop;
END_PROGRAM
