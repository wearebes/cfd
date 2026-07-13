set terminal svg enhanced size 900,600
set output 'rising_case2_velocity.svg'
set grid
set xlabel 'Time'
set key bottom right
plot [0:3][0:]'../../basilisk/src/test/c2g3l4.txt' u 1:5 w l t 'MooNMD', \
              '../rising_official_20260709/rising2/out' u 1:5 w l t 'Basilisk', \
              '../rising_official_20260709/rising2-levelset/out' u 1:5 w l t 'Basilisk (levelset)', \
              '../rising_official_20260709/rising2-clsvof/out' u 1:5 w l t 'Basilisk (CLSVOF)'
