"""Export a standardised 11D/19D/27D checkpoint for the shared C runtime."""
import argparse, hashlib, json
from pathlib import Path
import numpy as np
import torch
from feature_contract import CONTRACTS

def export(checkpoint, output, name):
    bundle=torch.load(checkpoint,map_location="cpu",weights_only=False)
    ft=bundle["feature_transform"]; cfg=bundle["model_config"]; dim=int(cfg["input_dim"])
    assert (dim,ft["feature_order"]) in CONTRACTS.values()
    assert ft["transform_kind"]=="standardize" and ft["raw_feature_dim"]==ft["output_dim"]==dim
    assert cfg["hidden_units"]==128 and bundle["model_type"]=="mlp"
    assert not output.exists(), f"Refusing to overwrite {output}"
    arrays={"mean":np.asarray(ft["mean"],dtype=np.float32),"std":np.asarray(ft["std"],dtype=np.float32)}
    assert arrays["mean"].shape==(dim,) and arrays["std"].shape==(dim,) and np.all(arrays["std"]>0)
    for i,j in enumerate((0,2,4,6,8)):
        for prefix,key in (("w","weight"),("b","bias")):
            arrays[f"{prefix}{i}"]=bundle["state_dict"][f"net.{j}.{key}"].numpy().astype(np.float32)
    def literal(a):
        if a.ndim==1: return "{"+", ".join(float(v).hex()+"f" for v in a)+"}"
        return "{\n"+",\n".join(literal(row) for row in a)+"\n}"
    text=["#ifndef CLSVOF_NN_WEIGHTS_H","#define CLSVOF_NN_WEIGHTS_H",f"#define CLSVOF_NN_INPUT_DIM {dim}",f"#define CLSVOF_NN_RAW_FEATURE_DIM {dim}","#define CLSVOF_NN_HIDDEN_UNITS 128",f'#define CLSVOF_NN_FEATURE_ORDER "{ft["feature_order"]}"','#define CLSVOF_NN_OUTPUT_CONTRACT "h*kappa"','#define CLSVOF_NN_NUMERIC_STORAGE "float32_hex"','#define CLSVOF_NN_INFERENCE_DTYPE "float32"']
    for key,a in arrays.items():
        assert np.all(np.isfinite(a))
        text.append("static const float clsvof_nn_"+key+"".join(f"[{n}]" for n in a.shape)+" = "+literal(a)+";")
    text.append("#endif");output.mkdir(parents=True)
    (output/"nn_weights.h").write_text("\n".join(text)+"\n")
    manifest={"name":name,"source_checkpoint":str(checkpoint.resolve()),"checkpoint_sha256":hashlib.sha256(checkpoint.read_bytes()).hexdigest(),"model_config":cfg,"feature_transform":{k:v for k,v in ft.items() if k not in ("mean","std","components")},"numeric_storage":"C float arrays with C99 hexadecimal float literals","inference_dtype":"selected by KAPPA_OFFSET_INFERENCE_DOUBLE at compilation","output_contract":"h*kappa","files":{"weights_header":"nn_weights.h"}}
    (output/"export_manifest.json").write_text(json.dumps(manifest,indent=2)+"\n")
    print(output)
if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("--checkpoint",type=Path,required=True);p.add_argument("--output",type=Path,required=True);p.add_argument("--name",required=True);a=p.parse_args();export(a.checkpoint,a.output,a.name)
