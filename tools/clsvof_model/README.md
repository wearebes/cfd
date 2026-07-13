# CLSVOF Model Export Tools

This directory contains tools and smoke-test code for exporting trained
PyTorch MLP checkpoints into C-readable model data.

Boundary:

- `dataset/model/c_exports/<model-name>/` stores exported model data only.
- `tools/clsvof_model/` stores exporter and validation code.
- Existing Basilisk/CLSVOF sources are not modified by this export step.

Default export target:

```bash
env KMP_DUPLICATE_LIB_OK=TRUE /opt/anaconda3/envs/pinn/bin/python \
  tools/clsvof_model/export_model_to_c.py \
  --all-from dataset/model \
  --output-root dataset/model/c_exports
```

Smoke compile:

```bash
cc -std=c99 -Wall -Wextra -Werror \
  -I dataset/model/c_exports/baseline_128_hgradient \
  -I tools/clsvof_model/include \
  tools/clsvof_model/tests/smoke_infer.c \
  -o /tmp/clsvof_smoke_infer
```

The generated weights are C `float` arrays written with C99 hexadecimal float
literals, so the checkpoint's float32 values are preserved as C source without
decimal text truncation.

The model output is the zero-level-set quantity
`q_gamma = h*kappa_gamma`. At the cell-local Basilisk `integral.h` insertion
site, the only supported deployment map is
`q_cell = q_gamma/(1 + (d/Delta)*q_gamma)` followed by
`kappa_cell = q_cell/Delta`. Direct `q_gamma/Delta` deployment is unsupported.
