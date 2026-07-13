set terminal svg enhanced size 900,600
set output 'rising_case2_volume.svg'
set grid
set xlabel 'Time'
set ylabel '(vb - vb_0)/vb_0'
set key top left
plot [0:3]'../rising_official_20260709/rising2/out' u 1:2 w l t 'Basilisk',		       \
          '../rising_official_20260709/rising2-levelset/out' u 1:2 w l t 'Basilisk (levelset)', \
	  '../rising_official_20260709/rising2-clsvof/out' u 1:2 w l t 'Basilisk (CLSVOF)'
