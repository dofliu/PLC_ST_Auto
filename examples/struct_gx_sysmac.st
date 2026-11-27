(* M42:TYPE STRUCT 匯出 GX Works3 / Sysmac Studio 範例(巢狀 STRUCT、陣列欄位、ARRAY OF STRUCT 初值) *)
TYPE Pt : STRUCT
  x : INT := 1;
  y : INT;
END_STRUCT END_TYPE
TYPE Axis : STRUCT
  home : Pt;
  pos : ARRAY[0..1] OF INT := [0, 0];
  name : STRING := 'axis';
  ready : BOOL;
END_STRUCT END_TYPE
PROGRAM P
VAR_INPUT
  start : BOOL;
END_VAR
VAR_OUTPUT
  sum : INT;
END_VAR
VAR
  ax : Axis := (home := (x := 5, y := 6), name := 'X, main');
  marks : ARRAY[1..3] OF Pt := [(x := 10), 2((y := 20))];
END_VAR
IF start THEN
  ax.pos[1] := ax.pos[1] + 1;
  ax.ready := ax.pos[1] >= 3;
END_IF;
sum := ax.home.x + ax.home.y + marks[1].x + marks[3].y + ax.pos[1];
END_PROGRAM
