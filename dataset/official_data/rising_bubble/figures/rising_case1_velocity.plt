set terminal svg enhanced size 900,600
set output 'rising_case1_velocity.svg'
set grid
set xlabel 'Time'
set key bottom right
plot [0:3][0:]'../../basilisk/src/test/c1g3l4.txt' u 1:5 w l t 'MooNMD', \
              '../rising_official_20260709/rising/out' u 1:5 w l t 'Basilisk', \
              '../rising_official_20260709/rising-levelset/out' u 1:5 w l t 'Basilisk (levelset)', \
              '../rising_official_20260709/rising-clsvof/out' u 1:5 w l t 'Basilisk (CLSVOF)',     \
              '../rising_official_20260709/rising-axi/out' u 1:5 w l t 'Basilisk (axisymmetric)',  \
              '../rising_official_20260709/rising-axi-clsvof/out' u 1:5 w l t 'Basilisk (axi + CLSVOF)',  \
              '../rising_official_20260709/rising-axi-momentum/out' u 1:5 w l t 'Basilisk (axi + momentum)'
