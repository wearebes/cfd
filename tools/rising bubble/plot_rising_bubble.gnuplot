if (!exists("ROOT")) ROOT = "../.."

raw = ROOT . "/dataset/official_data/rising_bubble/raw"
src = ROOT . "/dataset/official_data/rising_bubble/sources"
out = ROOT . "/dataset/official_data/rising_bubble/figures/author_style"

set style line 1 lc rgb "#222222" lw 1.9
set style line 2 lc rgb "#0b6e69" lw 1.8
set style line 3 lc rgb "#b23a48" lw 1.8
set style line 4 lc rgb "#3b5b92" lw 1.8
set style line 5 lc rgb "#7a5c00" lw 1.8
set style line 6 lc rgb "#6f4e7c" lw 1.8
set style line 7 lc rgb "#555555" lw 1.8 dt 2

set terminal svg enhanced size 640,320 font "Arial,12"
set output out . "/rising_case1_shape.svg"
set size ratio -1
set grid
plot [][0:0.4] src . "/c1g3l4s.txt" u 2:($1-0.5) w l ls 1 t 'MooNMD', \
              raw . "/rising/log" u 1:2 w l ls 2 t 'Basilisk', \
              raw . "/rising-levelset/log" u 1:2 w l ls 3 t 'Basilisk (levelset)', \
              raw . "/rising-clsvof/log" u 1:2 w l ls 4 t 'Basilisk (CLSVOF)', \
              raw . "/rising-axi/log" u 1:2 w l ls 5 t 'Basilisk (axisymmetric)', \
              raw . "/rising-axi-clsvof/log" u 1:2 w l ls 6 t 'Basilisk (axi + CLSVOF)', \
              raw . "/rising-axi-momentum/log" u 1:2 w l ls 7 t 'Basilisk (axi + momentum)'

set output out . "/rising_case2_shape.svg"
set key bottom left
plot [][0:0.4] src . "/c2g3l4s.txt" u 2:($1-0.5) w l ls 1 t 'MooNMD', \
              raw . "/rising2/log" u 1:2 w l ls 2 t 'Basilisk', \
              raw . "/rising2-levelset/log" u 1:2 w l ls 3 t 'Basilisk (levelset)', \
              raw . "/rising2-clsvof/log" u 1:2 w l ls 4 t 'Basilisk (CLSVOF)'

set terminal svg enhanced size 640,480 font "Arial,12"
set output out . "/rising_case1_velocity.svg"
reset
set style line 1 lc rgb "#222222" lw 1.9
set style line 2 lc rgb "#0b6e69" lw 1.8
set style line 3 lc rgb "#b23a48" lw 1.8
set style line 4 lc rgb "#3b5b92" lw 1.8
set style line 5 lc rgb "#7a5c00" lw 1.8
set style line 6 lc rgb "#6f4e7c" lw 1.8
set style line 7 lc rgb "#555555" lw 1.8 dt 2
set grid
set xlabel 'Time'
set key bottom right
plot [0:3][0:] src . "/c1g3l4.txt" u 1:5 w l ls 1 t 'MooNMD', \
              raw . "/rising/out" u 1:5 w l ls 2 t 'Basilisk', \
              raw . "/rising-levelset/out" u 1:5 w l ls 3 t 'Basilisk (levelset)', \
              raw . "/rising-clsvof/out" u 1:5 w l ls 4 t 'Basilisk (CLSVOF)', \
              raw . "/rising-axi/out" u 1:5 w l ls 5 t 'Basilisk (axisymmetric)', \
              raw . "/rising-axi-clsvof/out" u 1:5 w l ls 6 t 'Basilisk (axi + CLSVOF)', \
              raw . "/rising-axi-momentum/out" u 1:5 w l ls 7 t 'Basilisk (axi + momentum)'

set output out . "/rising_case1_volume.svg"
reset
set style line 2 lc rgb "#0b6e69" lw 1.8
set style line 3 lc rgb "#b23a48" lw 1.8
set style line 4 lc rgb "#3b5b92" lw 1.8
set style line 5 lc rgb "#7a5c00" lw 1.8
set style line 6 lc rgb "#6f4e7c" lw 1.8
set style line 7 lc rgb "#555555" lw 1.8 dt 2
set grid
set xlabel 'Time'
set ylabel '(vb - vb_0)/vb_0'
set key bottom left
plot [0:3] raw . "/rising/out" u 1:2 w l ls 2 t 'Basilisk', \
          raw . "/rising-levelset/out" u 1:2 w l ls 3 t 'Basilisk (levelset)', \
          raw . "/rising-clsvof/out" u 1:2 w l ls 4 t 'Basilisk (CLSVOF)', \
          raw . "/rising-axi/out" u 1:2 w l ls 5 t 'Basilisk (axisymmetric)', \
          raw . "/rising-axi-clsvof/out" u 1:2 w l ls 6 t 'Basilisk (axi + CLSVOF)', \
          raw . "/rising-axi-momentum/out" u 1:2 w l ls 7 t 'Basilisk (axi + momentum)'

set output out . "/rising_case2_velocity.svg"
reset
set style line 1 lc rgb "#222222" lw 1.9
set style line 2 lc rgb "#0b6e69" lw 1.8
set style line 3 lc rgb "#b23a48" lw 1.8
set style line 4 lc rgb "#3b5b92" lw 1.8
set grid
set xlabel 'Time'
set key bottom right
plot [0:3][0:] src . "/c2g3l4.txt" u 1:5 w l ls 1 t 'MooNMD', \
              raw . "/rising2/out" u 1:5 w l ls 2 t 'Basilisk', \
              raw . "/rising2-levelset/out" u 1:5 w l ls 3 t 'Basilisk (levelset)', \
              raw . "/rising2-clsvof/out" u 1:5 w l ls 4 t 'Basilisk (CLSVOF)'

set output out . "/rising_case2_volume.svg"
reset
set style line 2 lc rgb "#0b6e69" lw 1.8
set style line 3 lc rgb "#b23a48" lw 1.8
set style line 4 lc rgb "#3b5b92" lw 1.8
set grid
set xlabel 'Time'
set ylabel '(vb - vb_0)/vb_0'
set key top left
plot [0:3] raw . "/rising2/out" u 1:2 w l ls 2 t 'Basilisk', \
          raw . "/rising2-levelset/out" u 1:2 w l ls 3 t 'Basilisk (levelset)', \
          raw . "/rising2-clsvof/out" u 1:2 w l ls 4 t 'Basilisk (CLSVOF)'
