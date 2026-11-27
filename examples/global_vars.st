(* M43 範例:VAR_GLOBAL / VAR_EXTERNAL(CODESYS GVL 寫法)
   兩條輸送帶共用全域計數 g_count、全域上限 G_LIMIT(常數)與全域停止旗標 g_stop *)
VAR_GLOBAL CONSTANT
    G_LIMIT : INT := 5;
END_VAR
VAR_GLOBAL
    g_count : INT := 0;
    g_stop : BOOL;
    g_log : ARRAY[0..3] OF INT;
END_VAR

FUNCTION_BLOCK FB_Counter
VAR_INPUT
    pulse : BOOL;
END_VAR
VAR_EXTERNAL
    g_count : INT;
    g_stop : BOOL;
    g_log : ARRAY[0..3] OF INT;
END_VAR
VAR_EXTERNAL CONSTANT
    G_LIMIT : INT;
END_VAR
VAR
    edge : R_TRIG;
    mine : INT;
END_VAR
edge(CLK := pulse);
IF edge.Q AND NOT g_stop THEN
    g_count := g_count + 1;
    mine := mine + 1;
    g_log[g_count MOD 4] := mine;
END_IF;
g_stop := g_count >= G_LIMIT;
END_FUNCTION_BLOCK

FUNCTION Remaining : INT
VAR_EXTERNAL
    g_count : INT;
END_VAR
VAR_EXTERNAL CONSTANT
    G_LIMIT : INT;
END_VAR
Remaining := G_LIMIT - g_count;
END_FUNCTION

PROGRAM Main
VAR_INPUT
    sensorA : BOOL;
    sensorB : BOOL;
    reset : BOOL;
END_VAR
VAR_OUTPUT
    full : BOOL;
    remain : INT;
END_VAR
VAR
    cA : FB_Counter;
    cB : FB_Counter;
END_VAR
cA(pulse := sensorA);
cB(pulse := sensorB);
IF reset THEN
    g_count := 0;
END_IF;
full := g_stop;
remain := Remaining();
END_PROGRAM
