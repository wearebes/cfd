# Model Checkpoints and C Exports

This directory contains the PyTorch checkpoints, their feature-standardization
CSVs, and generated C-readable model data.

Generated C data lives under:

```text
dataset/model/c_exports/<model-name>/
  nn_weights.h
  export_manifest.json
```

The generated headers store the original float32 checkpoint values as C
`float` arrays using C99 hexadecimal float literals. This preserves the
float32 model data exactly as C source and keeps the C inference path aligned
with PyTorch's float32 model path.

Exporter and validation code lives outside this directory:

```text
tools/clsvof_model/
```

The exported model output contract is the zero-level-set quantity
`q_gamma = h*kappa_gamma`. At the cell-local Basilisk `integral.h` insertion
site, use `q_cell = q_gamma/(1 + (d/Delta)*q_gamma)` and then
`kappa_cell = q_cell/Delta`. Direct `q_gamma/Delta` deployment is unsupported.
