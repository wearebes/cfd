if (!exists("ROOT")) ROOT = "../.."

data = ROOT . "/dataset/official_data/capwave/raw"
src = ROOT . "/dataset/official_data/capwave/sources"
out = ROOT . "/dataset/official_data/capwave/figures/author_style"

set terminal svg enhanced size 640,480 font "Arial,12"

set style line 1 lc rgb "#222222" lw 2.0
set style line 2 lc rgb "#0b6e69" lw 1.7 pt 7 ps 0.55
set style line 3 lc rgb "#b23a48" lw 1.7 pt 5 ps 0.55
set style line 4 lc rgb "#666666" lw 1.3 dt 2

set output out . "/capwave_amplitude.svg"
set xlabel 'tau'
set ylabel 'Relative amplitude'
plot src . "/prosperetti.h" u 2:4 w l ls 1 t "Prosperetti", \
     data . "/official_vof/wave-128" every 10 w p ls 2 t "Basilisk", \
     data . "/official_clsvof/wave-128" every 10 w p ls 3 t "Basilisk (CLSVOF)"

set output out . "/capwave_rms_convergence.svg"
set xlabel 'Number of grid points'
set ylabel 'Relative RMS error'
set logscale y
set logscale x 2
set grid
plot [5:200][1e-4:1] \
     data . "/official_vof/log" t "Basilisk" w lp ls 2, 2./x**2 t "Second order" w l ls 4, \
     data . "/official_clsvof/log" t "Basilisk (CLSVOF)" w lp ls 3, \
     2./x**2 notitle w l ls 4

set output out . "/capwave_rms_convergence_extended.svg"
set xlabel 'Number of grid points'
set ylabel 'Relative RMS error'
set logscale y
set logscale x 2
set grid
plot [10:600][1e-4:1] \
     data . "/extended_vof/log" u ($1*2):2 t "Basilisk" w lp ls 2, 8./x**2 t "Second order" w l ls 4, \
     data . "/extended_clsvof/log" u ($1*2):2 t "Basilisk (CLSVOF)" w lp ls 3, \
     8./x**2 notitle w l ls 4
