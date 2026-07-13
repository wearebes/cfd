set terminal svg enhanced size 900,600
set output 'rising_case1_volume.svg'
set grid
set xlabel 'Time'
set ylabel '(vb - vb_0)/vb_0'
set key bottom left
plot [0:3]'../rising_official_20260709/rising/out' u 1:2 w l t 'Basilisk', \
          '../rising_official_20260709/rising-levelset/out' u 1:2 w l t 'Basilisk (levelset)',   \
	  '../rising_official_20260709/rising-clsvof/out' u 1:2 w l t 'Basilisk (CLSVOF)',	\
	  '../rising_official_20260709/rising-axi/out' u 1:2 w l t 'Basilisk (axisymmetric)',	\
	  '../rising_official_20260709/rising-axi-clsvof/out' u 1:2 w l t 'Basilisk (axi + CLSVOF)',	\
	  '../rising_official_20260709/rising-axi-momentum/out' u 1:2 w l t 'Basilisk (axi + momentum)'
