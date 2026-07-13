set terminal svg enhanced size 900,450
set output 'rising_case2_shape.svg'
set size ratio -1
set grid
set key bottom left
plot [][0:0.4]'../../basilisk/src/test/c2g3l4s.txt' u 2:($1-0.5) w l t 'MooNMD', \
              '../rising_official_20260709/rising2/log' u 1:2 w l t 'Basilisk', \
              '../rising_official_20260709/rising2-levelset/log' u 1:2 w l t 'Basilisk (levelset)', \
              '../rising_official_20260709/rising2-clsvof/log' u 1:2 w l t 'Basilisk (CLSVOF)'
