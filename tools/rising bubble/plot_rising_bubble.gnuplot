if (!exists("ROOT")) ROOT = "../.."

data = ROOT . "/dataset/rising_bubble"
out = ROOT . "/figures/rising_bubble/official_reproduction"

set style line 1 lc rgb "#222222" lw 1.9
set style line 2 lc rgb "#0b6e69" lw 1.8
set style line 3 lc rgb "#3b5b92" lw 1.8
set style line 4 lc rgb "#b23a48" lw 1.8 dt 2

set terminal svg enhanced size 640,320 font "Arial,12"
set size ratio -1
set grid

set output out . "/rising_case1_shape.svg"
plot [][0:0.4] data . "/case1/reference/hysing/interface.dat" u 2:($1-0.5) w l ls 1 t 'Hysing/MooNMD', \
     data . "/case1/reference/csf_default/N0256/interface.dat" u 1:2 w l ls 2 t 'CSF default', \
     data . "/case1/N0256/imax03/clsvof/interface.dat" u 1:2 w l ls 3 t 'Native', \
     data . "/case1/N0256/imax03/nn/interface.dat" u 1:2 w l ls 4 t 'NN cell offset'

set output out . "/rising_case2_shape.svg"
plot [][0:0.4] data . "/case2/reference/hysing/interface.dat" u 2:($1-0.5) w l ls 1 t 'Hysing/MooNMD', \
     data . "/case2/reference/csf_default/N0256/interface.dat" u 1:2 w l ls 2 t 'CSF default', \
     data . "/case2/N0256/imax03/clsvof/interface.dat" u 1:2 w l ls 3 t 'Native', \
     data . "/case2/N0256/imax03/nn/interface.dat" u 1:2 w l ls 4 t 'NN cell offset'

set terminal svg enhanced size 640,480 font "Arial,12"
unset size
set xlabel 'Time'

set output out . "/rising_case1_velocity.svg"
plot [0:3][0:] data . "/case1/reference/hysing/history.dat" u 1:5 w l ls 1 t 'Hysing/MooNMD', \
     data . "/case1/reference/csf_default/N0256/history.dat" u 1:5 w l ls 2 t 'CSF default', \
     data . "/case1/N0256/imax03/clsvof/history.dat" u 1:5 w l ls 3 t 'Native', \
     data . "/case1/N0256/imax03/nn/history.dat" u 1:5 w l ls 4 t 'NN cell offset'

set output out . "/rising_case1_volume.svg"
set ylabel '(vb - vb_0)/vb_0'
plot [0:3] data . "/case1/reference/csf_default/N0256/history.dat" u 1:2 w l ls 2 t 'CSF default', \
     data . "/case1/N0256/imax03/clsvof/history.dat" u 1:2 w l ls 3 t 'Native', \
     data . "/case1/N0256/imax03/nn/history.dat" u 1:2 w l ls 4 t 'NN cell offset'

set output out . "/rising_case2_velocity.svg"
unset ylabel
plot [0:3][0:] data . "/case2/reference/hysing/history.dat" u 1:5 w l ls 1 t 'Hysing/MooNMD', \
     data . "/case2/reference/csf_default/N0256/history.dat" u 1:5 w l ls 2 t 'CSF default', \
     data . "/case2/N0256/imax03/clsvof/history.dat" u 1:5 w l ls 3 t 'Native', \
     data . "/case2/N0256/imax03/nn/history.dat" u 1:5 w l ls 4 t 'NN cell offset'

set output out . "/rising_case2_volume.svg"
set ylabel '(vb - vb_0)/vb_0'
plot [0:3] data . "/case2/reference/csf_default/N0256/history.dat" u 1:2 w l ls 2 t 'CSF default', \
     data . "/case2/N0256/imax03/clsvof/history.dat" u 1:2 w l ls 3 t 'Native', \
     data . "/case2/N0256/imax03/nn/history.dat" u 1:2 w l ls 4 t 'NN cell offset'
