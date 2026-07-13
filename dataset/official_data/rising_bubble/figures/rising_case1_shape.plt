set terminal svg enhanced size 900,450
set output 'rising_case1_shape.svg'
set size ratio -1
set grid
plot [][0:0.4]'../../basilisk/src/test/c1g3l4s.txt' u 2:($1-0.5) w l t 'MooNMD', \
              '../rising_official_20260709/rising/log' u 1:2 w l t 'Basilisk', \
              '../rising_official_20260709/rising-levelset/log' u 1:2 w l t 'Basilisk (levelset)', \
              '../rising_official_20260709/rising-clsvof/log' u 1:2 w l t 'Basilisk (CLSVOF)', \
              '../rising_official_20260709/rising-axi/log' u 1:2 w l t 'Basilisk (axisymmetric)', \
              '../rising_official_20260709/rising-axi-clsvof/log' u 1:2 w l t 'Basilisk (axi + CLSVOF)', \
              '../rising_official_20260709/rising-axi-momentum/log' u 1:2 w l t 'Basilisk (axi + momentum)'
