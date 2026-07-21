set terminal pngcairo size 1400,900 enhanced font "Arial,18" background rgb 'white'
set output output_file
set xlabel 'Diameter (grid points)'
set ylabel 'Absolute frequency error (%)'
set logscale x 2
unset grid
set xzeroaxis
set key spacing 1.25 top right

standard_color = '#7B2CBF'
momentum_color = '#009E73'
compressible_color = '#56B4E9'
clsvof_color = '#D55E00'

ftitle(a,b,c) = sprintf("%.3g*x^(%+.2f) (%s)", exp(a), b, c)
f0(x)=a0+b0*x
fit f0(x) standard_file u (log($1)):(log(abs($2)*100.)) via a0,b0
f1(x)=a1+b1*x
fit f1(x) momentum_file u (log($1)):(log(abs($2)*100.)) via a1,b1
f2(x)=a2+b2*x
fit f2(x) compressible_file u (log($1)):(log(abs($2)*100.)) via a2,b2
f3(x)=a3+b3*x
fit f3(x) clsvof_file u (log($1)):(log(abs($2)*100.)) via a3,b3

plot standard_file u ($1):(abs($2)*100.) t '' w p pt 5 ps 1.25 lc rgb standard_color, \
     momentum_file u ($1):(abs($2)*100.) t '' w p pt 7 ps 1.25 lc rgb momentum_color, \
     compressible_file u ($1):(abs($2)*100.) t '' w p pt 9 ps 1.25 lc rgb compressible_color, \
     clsvof_file u ($1):(abs($2)*100.) t '' w p pt 13 ps 1.25 lc rgb clsvof_color, \
     exp(f0(log(x))) t ftitle(a0,b0,'Standard (official)') w l lw 2 lc rgb standard_color, \
     exp(f1(log(x))) t ftitle(a1,b1,'Momentum (official)') w l lw 2 lc rgb momentum_color, \
     exp(f2(log(x))) t ftitle(a2,b2,'Compressible (official)') w l lw 2 lc rgb compressible_color, \
     exp(f3(log(x))) t ftitle(a3,b3,'CLSVOF extension') w l lw 2 lc rgb clsvof_color
