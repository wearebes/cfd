# Elliptical Droplet Oscillation: Official VOF-HF and Matched CLSVOF Reproduction Plan

Date: 2026-07-14  
Status: planning only; no case implementation or solver run is authorised by this document  
Case identity: Basilisk two-dimensional inviscid elliptical-droplet shape oscillation  
Official host: `basilisk/src/test/oscillation.c`  
First comparison: official standard VOF-HF versus a matched CLSVOF-LS port  

## 1. Decision summary

The requested case is the official Basilisk **shape oscillation of an
inviscid droplet**. It starts from a weakly deformed, mode-2 droplet and follows
its surface-tension-driven oscillation about the circular equilibrium shape.
In this plan, “elliptical oscillation”, “elliptical droplet oscillation”, and
“oscillating droplet” refer to this one benchmark.

The first campaign will contain two report-facing methods:

1. `VOF_HF_OFFICIAL`: the unmodified standard incompressible branch of the
   official `oscillation.c` case;
2. `CLSVOF_LS_MATCHED`: the same geometry, physical parameters, grid levels,
   time horizon, tolerance, property filtering and initial perturbation, but
   with Basilisk's coupled VOF/level-set interface representation and integral
   surface-tension formulation.

The second method is an **official-component matched port**, not an existing
official `oscillation-clsvof.c` benchmark. That distinction must appear in
manifests, reports and figure captions.

No NN method, momentum branch, compressible branch, viscosity sweep, full-domain
variant, redistance sweep or alternative curvature provider belongs to the
first campaign.

## 2. What methods the official oscillation source contains

The single official source selects one of three solver branches at compile
time.

| Official branch | Compile selection | Interface and surface tension | Role here |
|---|---|---|---|
| Standard incompressible | no method macro | `centered.h` + `two-phase.h` + `tension.h`; filtered material properties; Basilisk VOF curvature with height-function path and native fallbacks | selected official baseline |
| Momentum-conserving incompressible | `-DMOMENTUM=1` | `momentum.h` + VOF + `tension.h` | official but excluded from first campaign |
| Compressible two-phase | `-DCOMPRESSIBLE=1` | compressible two-phase solver, Mie-Gruneisen EOS and compressible surface tension | official but excluded from first campaign |

The official Makefile creates `oscillation-momentum.c` and
`oscillation-compressible.c` as links to the same source and supplies the
corresponding macros. There is no equivalent official Makefile target for
`oscillation-clsvof.c`.

The label `VOF-HF` is useful report shorthand, but it must not imply that every
interfacial curvature value is guaranteed to come from a valid height stencil.
The precise method name is **Basilisk standard VOF surface-tension method with
height-function curvature and native fallbacks**.

There is one documentation inconsistency in the tracked official source: the
embedded plotting block refers to files such as `k-8`, while the executable
loop is explicitly `LEVEL=4..7` and the tracked `.ref` contains the associated
`6.4..51.2` cells-per-diameter rows. The executable loop and `.ref` define this
plan's matrix. No `LEVEL=8` row will be inferred from the plotting comment.

## 3. Scientific question and comparison boundary

### 3.1 Primary question

Under the official inviscid mode-2 droplet-oscillation conditions, how do the
standard VOF-HF formulation and the matched CLSVOF-LS/integral formulation
compare in:

- oscillation frequency;
- numerical damping;
- conservation of droplet area;
- phase and deformation history;
- grid-convergence behaviour?

### 3.2 What this comparison can establish

It can establish solver-level behaviour for two complete interfacial methods on
the same physical case and mesh family.

### 3.3 What it cannot isolate

This is not a curvature-only ablation. The treatment changes together are:

- interface representation and maintenance;
- curvature construction;
- surface-tension force assembly;
- the presence of the signed-distance field and redistancing.

Accordingly, a difference cannot be attributed only to “HF versus level-set
curvature”. A later curvature-only intervention would require a separate host
and a new experiment identity.

## 4. Locked physical and numerical settings

These values are copied from the official standard oscillation source and are
invariants for both methods unless an unresolved decision in Section 15 is
explicitly changed before implementation.

| Category | Setting | Exact value or definition |
|---|---|---|
| Dimension | spatial model | 2D Cartesian |
| Computed geometry | domain | quadrant `[0, 0.5] x [0, 0.5]` |
| Symmetry interpretation | full physical view | reflection about `x=0` and `y=0` |
| Far boundaries | location | `x=0.5`, `y=0.5` |
| Boundary conditions | all boundaries | Basilisk defaults used by official case; symmetry/no normal flow, with pressure compatibility supplied by centered solver |
| Equilibrium diameter | `D` | `0.2` |
| Equilibrium radius | `R0` | `D/2 = 0.1` |
| Mode number | `n` | `2` |
| Perturbation | radial interface | `r(theta) = R0*(1 + 0.05*cos(2*theta))` |
| Perturbation amplitude | `epsilon` | `0.05` (5%) |
| x-direction radius | `r(0)` | `R0*(1+epsilon) = 0.105` |
| y-direction radius | `r(pi/2)` | `R0*(1-epsilon) = 0.095` |
| Initial major/minor diameters | `Dx`, `Dy` | `0.210` / `0.190` |
| Axis ratio | `r(0)/r(pi/2)` | `0.105/0.095 = 1.105263...` |
| Initial directional deformation | `(Dx-Dy)/(Dx+Dy)` | `0.05` |
| Initial velocity | `u` | zero |
| Droplet density | `rho1` | `1` |
| Ambient density | `rho2` | `1e-3` |
| Density ratio | droplet/ambient | `1000` |
| Dynamic viscosity | `mu1`, `mu2` | zero |
| Surface tension | `sigma` | `1` |
| Gravity | body force | none |
| Pressure tolerance | `TOLERANCE` | `1e-4` |
| End time | `t_end` | `1` |
| Property treatment | density/specific volume | `FILTERED=1` for both methods |
| Grid family | quadtree | levels `4, 5, 6, 7` |
| Base cell counts | `N=2^LEVEL` | `16, 32, 64, 128` per computed-domain side |
| Cells per equilibrium diameter | `D/L0*N` | `6.4, 12.8, 25.6, 51.2` |
| Adaptivity | official conditional event | retain official code path; with the local quadtree build, use the same `adapt_wavelet({f,u}, {5e-3,1e-3,1e-3}, LEVEL)` contract in both methods |
| Output horizon | kinetic energy | every solver iteration while `t <= 1` |

The initial polar perturbation is “slightly elliptical” in the small-amplitude
sense; it is not an exact algebraic ellipse. Reports should say
**mode-2 elliptical perturbation**, not claim an exact ellipse equation.

### 4.1 Exact interpretation of the “ellipse” parameters

The official interface is exactly

```text
r(theta) = 0.1*(1 + 0.05*cos(2*theta)).
```

Consequently, its extreme radii and diameters are exactly

```text
r_x = 0.105,  D_x = 0.210
r_y = 0.095,  D_y = 0.190
axis ratio = r_x/r_y = 1.1052631579
deformation = (D_x-D_y)/(D_x+D_y) = 0.05.
```

If one uses `a=0.105` and `b=0.095` as descriptive semi-axes, they describe
the axial extrema but do **not** turn the official polar curve into the strict
ellipse

```text
x^2/a^2 + y^2/b^2 = 1.
```

The official polar curve has area

```text
A0 = pi*R0^2*(1 + epsilon^2/2)
   = pi*0.1^2*1.00125
   = 0.0100125*pi
   approximately 0.0314551964,
```

and area-equivalent radius

```text
R_area = R0*sqrt(1 + epsilon^2/2)
       approximately 0.1000624805.
```

For comparison only, a strict ellipse with `a=0.105`, `b=0.095` would have
area `pi*a*b = 0.009975*pi`, approximately `0.0313373867`. That strict ellipse
must not replace the official initial condition in the reproduction campaign.

## 5. Theoretical reference

For a two-dimensional inviscid mode-`n` oscillation, the official case uses

```text
omega0 = sqrt((n^3 - n)*sigma/((rho1 + rho2)*R0^3))
```

With the locked settings:

```text
omega0                 = 77.420966114
shape period           = 2*pi/omega0 = 0.081156121
kinetic-energy pulsation c_theory = 2*omega0 = 154.841932228
kinetic-energy period  = pi/omega0 = 0.040578061
```

The official kinetic-energy fit is

```text
K(t) = a*exp(-b*t)*(1 - cos(c*t))
```

where `c/2` estimates the shape pulsation and `b` measures numerical damping.
Since physical viscosity is zero, damping must be described as numerical
dissipation, not physical viscous damping.

## 6. Method definitions

### 6.1 `VOF_HF_OFFICIAL`

This arm is the official default source path:

```c
#include "navier-stokes/centered.h"
#define FILTERED 1
#include "two-phase.h"
#include "tension.h"
```

The official initialisation remains:

```c
fraction (f, D/2.*(1. + 0.05*cos(2.*atan2(y,x)))
             - sqrt(sq(x) + sq(y)));
```

The canonical authority is the tracked file
`basilisk/src/test/oscillation.c`. It must not be edited.

### 6.2 `CLSVOF_LS_MATCHED`

This arm keeps `centered.h` but uses the official CLSVOF-LS and integral
surface-tension components:

```c
#include "navier-stokes/centered.h"
#define FILTERED 1
#include "two-phase-clsvof.h"
#include "integral.h"
```

Surface tension is attached to the distance tracer:

```c
const scalar sigma[] = 1.;
d.sigmaf = sigma;
```

The initial signed field is locked to

```c
d[] = D/2.*(1. + 0.05*cos(2.*atan2(y,x)))
      - sqrt(sq(x) + sq(y));
```

This makes `d > 0` inside the droplet, matching `f=1` and `rho1=1` in the
official VOF arm. The stock `two-phase-clsvof.h` then constructs `f` from `d`.

The first campaign keeps the stock CLSVOF maintenance contract:

```text
VOF relaxation weight = 0.1
redistance imax        = 3
redistance phixxmin    = HUGE
integral CURVATURE     = 1
```

No generated or modified copy of `two-phase-clsvof.h`, `integral.h` or
`redistance.h` is allowed in the formal baseline. Non-default `imax` values are
out of scope.

## 7. Repository layout to create during implementation

Implementation should remain case-centred and keep the Basilisk tree immutable.

```text
cases/oscillating_droplet/
  summary.yaml
  src/
    oscillation-clsvof.c
    oscillation-observers.h
  generate/
    official_vof_hf.sh
    matched_clsvof.sh
  tests/
    test_case_contract.py

tem/oscillating_droplet/
  <UTC smoke timestamp>/
    vof_hf_level6/
    clsvof_level6/

dataset/oscillating_droplet/
  official_reproduction/
    manifest.json
    vof_hf/
      level_4/
      level_5/
      level_6/
      level_7/
    clsvof/
      level_4/
      level_5/
      level_6/
      level_7/
    summary.csv
    timeseries.csv.gz

figures/oscillating_droplet/official_reproduction/
  plot_reproduction.py
  frequency_error.png
  kinetic_energy.png
  damping.png
  deformation.png
  area_drift.png
  method_comparison.csv

report/figures/
  # only selected, report-ready copies after formal closure
```

`tem/` is for canary history. The formal dataset uses scientific identity and
must not be named only by timestamp. Figure-generation code stays beside its
figure outputs. No formal result is promoted into `report/` until the closure
audit passes.

## 8. Source and immutability contract

Before implementation:

1. record the current dirty-worktree inventory;
2. hash `oscillation.c`, `oscillation.ref`, `two-phase.h`, `tension.h`,
   `two-phase-clsvof.h`, `integral.h`, `redistance.h`, `centered.h` and the
   active Basilisk configuration;
3. record the qcc, compiler and gnuplot versions;
4. prohibit writes beneath `basilisk/src`;
5. build and run only in row-isolated work directories.

The VOF generator copies the official source into a work directory and applies
no physical or solver edit. Level isolation and observers must be implemented
outside the authority source and recorded by hash/diff.

The CLSVOF source is a minimal explicit port. Its audit diff against the
official source must show only:

- method includes;
- surface-tension attachment to `d`;
- initialisation of `d` instead of direct `fraction(f, ...)`;
- method-neutral row selection and observers;
- method label/provenance output.

Any change to geometry, physical properties, tolerance, end time, grid or
adaptation thresholds invalidates the matched comparison.

## 9. Execution matrix and staging

### Phase 0 — static contract audit

No solver run is allowed until automated checks prove:

- official source hash is recorded;
- exactly three official compile branches are documented;
- the formal selected official branch is the default standard branch;
- both method sources resolve the same `D`, `L0`, densities, viscosities,
  `sigma`, `TOLERANCE`, `t_end`, levels and adaptation tolerances;
- CLSVOF initial `d` has the same zero contour and phase orientation as the
  official VOF fraction expression;
- formal stock CLSVOF headers are unmodified;
- all formal rows have deterministic identities.

### Phase 1 — official stock reproduction

Run the untouched official default case once in an isolated work directory.
This run executes the official `LEVEL=4..7` loop and establishes local reference
behaviour against `basilisk/src/test/oscillation.ref`.

Expected local reference values from the tracked official `.ref` are:

| cells per `D` | fitted `a` | fitted `b` | fitted `c` |
|---:|---:|---:|---:|
| 6.4 | 0.000296 | 1.97 | 157 |
| 12.8 | 0.000288 | 0.91 | 154 |
| 25.6 | 0.000290 | 0.23 | 155 |
| 51.2 | 0.000293 | 0.00 | 155 |

These values are regression references, not universal bitwise constants across
compilers. Raw time series and the local ref comparison must be preserved.

### Phase 2 — paired N64 canary

Run only these two smoke rows:

| row | method | LEVEL | N | cells per `D` | end time |
|---|---|---:|---:|---:|---:|
| canary-vof-hf-L6 | `VOF_HF_OFFICIAL` | 6 | 64 | 25.6 | 1 |
| canary-clsvof-L6 | `CLSVOF_LS_MATCHED` | 6 | 64 | 25.6 | 1 |

Each row is a separate single-threaded Basilisk process. Run sequentially on
the first attempt. A canary is accepted only when it compiles, reaches `t=1`,
produces finite outputs, preserves nonzero droplet area and yields a parseable
frequency/damping fit.

Canary outputs remain under `tem/`; they are not formal evidence and are not
silently reused as formal rows.

### Phase 3 — formal two-method matrix

The formal matrix contains exactly eight independently executable rows:

```text
2 methods x 4 levels = 8 rows
```

| method | LEVEL values | row count |
|---|---|---:|
| `VOF_HF_OFFICIAL` | 4, 5, 6, 7 | 4 |
| `CLSVOF_LS_MATCHED` | 4, 5, 6, 7 | 4 |

Every row remains single-threaded and row-isolated. Initial formal execution is
sequential. Parallel `--jobs` execution may be added later only as scheduling;
it must not change the row identity, compile flags or numerical settings.

### Phase 4 — analysis and report promotion

Only after all eight rows have terminal states:

1. rebuild all summaries directly from raw files;
2. verify method/level pairing and hashes;
3. generate the complete figure set;
4. write an evidence-first comparison table;
5. promote only report-ready figures into `report/figures`;
6. retain failures in the matrix rather than deleting or silently retrying them
   with changed settings.

### Phase 5 — command contract

The implementation scripts should resolve absolute paths but execute from the
row work directory. The intended single-thread environment is:

```text
BASILISK=/Users/jcy/research/cfd/basilisk/src
OMP_NUM_THREADS=1
```

The baseline compile shape is:

```text
$BASILISK/qcc -O2 -Wall source.c -o oscillation -lm
```

For the untouched official stock run, preserve the filenames expected by the
source itself:

```text
./oscillation > out 2> log
```

The work directory is mandatory because the official executable removes and
rewrites `error` and `laplace`, creates `k-<LEVEL>` and fit files, and appends
from `out` into `log`. After completion, the runner may copy these into the
canonical per-row filenames without deleting the originals.

The implementation preflight must verify that `qcc`, the configured C
compiler and `gnuplot` are callable before any solver row starts.

## 10. Per-row outputs and manifest

Each row must contain:

```text
source.c
executable
command.txt
stdout.txt
stderr.txt
kinetic_energy.csv
shape_metrics.csv
interface_samples/          # nearest-step, non-time-forcing samples
fit.json
manifest.json
status.json
```

The manifest must record at least:

- case and method identity;
- evidence level (`official_stock` or `official_component_port`);
- LEVEL, N, cells per diameter and grid type;
- all locked physical settings;
- end time and actual final time;
- qcc/compiler/gnuplot versions;
- source and dependency hashes;
- compile command and run command;
- start/end timestamps and wall time;
- thread count;
- terminal state and failure reason;
- stock/default CLSVOF parameters (`weight=0.1`, `imax=3`,
  `phixxmin=HUGE`, `CURVATURE=1`).

Allowed terminal states are:

```text
completed
failed_compile
failed_runtime
failed_nonfinite
failed_missing_output
blocked_resource
```

## 11. Observer definitions

Observers must not force new physical output times. They run on the solver's
existing iterations and may save a nearest-step interface sample only after a
requested phase time is crossed.

### 11.1 Kinetic energy

Preserve the official definition for each method. The canonical columns are:

```text
t, kinetic_energy, pressure_iterations
```

### 11.2 Area conservation

For the computed quadrant:

```text
A(t) = integral f dA
area_rel_drift(t) = (A(t) - A(0))/A(0)
```

Use `max_abs_area_rel_drift` as the row summary. It is recorded in the first
campaign but does not receive an invented pass threshold before canary evidence
is inspected.

### 11.3 Deformation

Reconstruct full-domain moments from the computed quadrant. Reflection gives

```text
A_full = 4*integral f dA
Ixx_full = 4*integral f*x^2 dA
Iyy_full = 4*integral f*y^2 dA
Ixy_full = 0
```

The reflected full-domain centroid is the origin. Define oriented,
method-neutral moment extents

```text
a_x(t) = 2*sqrt(Ixx_full/A_full)
a_y(t) = 2*sqrt(Iyy_full/A_full)
```

and then

```text
deformation(t) = (a_x(t) - a_y(t))/(a_x(t) + a_y(t))
```

The sign is retained so the deformation history crosses zero and reverses as
the major axis changes orientation. The precise moment-to-extent scale cancels
in the ratio. Quadrant centroids may be recorded for audit, but must not be
misinterpreted as full-domain centroid drift.

### 11.4 Frequency and damping

Retain the official kinetic-energy fit on `[0,1]`. Also perform an independent
re-fit from the saved raw series so the summary is not dependent only on
gnuplot console text.

Record:

```text
c_fit
omega_fit = c_fit/2
frequency_rel_error = c_fit/(2*omega0) - 1
b_fit
equivalent_La = sigma*C^2/(rho1*b_fit^2*D^3), C=30
```

If `b_fit` is statistically indistinguishable from zero or slightly negative,
report it as an unresolved near-zero numerical damping fit; do not turn it into
an infinite or signed physical Laplace number without qualification.

### 11.5 CLSVOF-only diagnostics

Record, without changing the physical update:

- signed-distance gradient error `abs(|grad d|-1)` in `1.5*Delta` and
  `3*Delta` bands;
- mean, RMS, maximum and 95th percentile of the gradient error;
- redistance calls and returned iteration counts;
- difference between the `d`-reconstructed and transported-VOF area;
- sign/orientation consistency at initialisation.

These are diagnostic columns. They are not available for VOF-HF and must not be
filled with fabricated zeros.

## 12. Acceptance gates

### 12.1 Official stock reproduction gate

The local official run passes when:

- compilation succeeds with the local Basilisk toolchain;
- all four levels reach `t=1`;
- all kinetic-energy samples are finite;
- four parseable fit rows are produced;
- fitted `c` is within 3% of `c_theory` for every level;
- the level-7 frequency error is no worse than the level-4 error by more than
  0.5 percentage points;
- level-7 fitted damping is below level-4 fitted damping;
- differences from the tracked `.ref` are reported rather than hidden.

### 12.2 Per-row completion gate

A formal row is `completed` only when:

- expected method and level match the manifest;
- actual final time reaches `1`;
- kinetic energy, area and deformation histories are non-empty and finite;
- the fit is parseable and uses the saved row data;
- source/dependency hashes are present;
- no source beneath `basilisk/src` changed during the row.

### 12.3 VOF formal-equivalence gate

The row-isolated VOF-HF implementation must reproduce the corresponding local
official stock row within documented parser precision for sample times,
kinetic-energy history and fitted `c`/`b`. Any mismatch must be resolved before
using VOF-HF as the paired baseline.

### 12.4 CLSVOF interpretation gate

CLSVOF has no official oscillation `.ref` in this checkout. Therefore its first
formal rows pass on provenance, completion and finite-data integrity, not on an
assumption that they must outperform VOF-HF.

The first report must show the measured result before making any judgement. In
particular:

- lower SDF gradient error does not prove better frequency or damping;
- lower damping is not automatically better if frequency or conservation is
  worse;
- similarity to VOF-HF does not make the port an official Basilisk regression
  case.

## 13. Required evidence products

### 13.1 Summary table

One row per method and level with:

```text
method, evidence_level, LEVEL, N, cells_per_D, status,
c_fit, omega_fit, frequency_rel_error, b_fit, equivalent_La,
max_abs_area_rel_drift, deformation_initial, deformation_peak,
final_time, sample_count, wall_seconds, source_sha256
```

### 13.2 Figures

1. kinetic-energy histories, faceted by level, with both methods overlaid;
2. absolute frequency error versus cells per diameter;
3. fitted numerical damping versus cells per diameter;
4. deformation histories for both methods;
5. maximum area drift versus resolution;
6. selected interface overlays near equivalent oscillation phases;
7. CLSVOF SDF-quality diagnostics as a secondary figure, not the opening
   physical result.

### 13.3 Report ordering

The report should lead with:

1. exact benchmark/method identity;
2. the eight-row evidence table;
3. frequency and kinetic-energy figures;
4. damping, deformation and conservation;
5. CLSVOF-only diagnostics;
6. limitations and next-step decision.

Do not lead with source-code walkthroughs.

## 14. Closure contract

The first campaign is complete only when all of the following are true:

- the untouched official stock reproduction has a terminal result;
- both N64 canaries have terminal results;
- all eight formal row IDs exist and have terminal states;
- every completed row passes the per-row evidence gate;
- every failed row preserves its partial evidence and classified failure;
- VOF row isolation passes the official-equivalence check;
- the CLSVOF port diff contains no unapproved physical drift;
- raw files regenerate the aggregate CSV and all figures;
- method labels distinguish `official_stock` from
  `official_component_port`;
- no file beneath `basilisk/src` was modified;
- only validated, report-ready figures are copied into `report/figures`;
- conclusions are written from the completed table and figures, not from
  expectations.

Until every clause is mapped to a file or audit result, the campaign must be
reported as partial.

## 15. Questions not yet fixed

The plan above adopts conservative defaults so implementation can be reviewed
concretely. These questions remain open and must be answered before formal
execution if the defaults are not accepted.

1. **Primary scientific intent.** Is this only an official reproduction and
   method comparison, or must it ultimately become a paper-facing validation
   case? Default: build report-ready evidence, but make no publication claim in
   the first run.
2. **Filtered properties in CLSVOF.** This plan keeps `FILTERED=1` in both arms
   so the treatment change is not confounded by property filtering. An
   unfiltered CLSVOF arm would follow some other official CLSVOF cases more
   closely but would be a third sensitivity method. Default: filtered in the
   matched arm; no unfiltered arm yet.
3. **Official extra branches.** Should the momentum-conserving and compressible
   official references be reproduced later? Default: exclude them from this
   campaign and list them only as official context.
4. **Quadrant versus full domain.** Should a full-domain symmetry check be added
   later? Default: reproduce the official quadrant only; any full-domain run is
   a separate sensitivity case.
5. **Area-drift threshold.** No threshold is imposed before observing the N64
   canaries. Default: record and compare area drift, then set a formal threshold
   only from numerical evidence and intended publication standard.
6. **Execution host.** Should the eight formal rows run locally or on the Ubuntu
   HPC host after local canaries? Default: local contract/canary first; choose
   the formal host only after measured N64 runtime and environment parity are
   available.
7. **Interface visualisation density.** The physical conclusions do not require
   a movie. Default: save nearest-step contours at initial state and selected
   quarter-period phases; add animation only if explicitly wanted.
8. **Comparison verdict.** No “CLSVOF must beat VOF-HF” gate is defined.
   Default: judge frequency, damping and conservation separately and report
   trade-offs without a forced overall winner.
