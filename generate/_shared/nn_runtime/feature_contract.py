"""Validate the exported model against the requested CFD normal stencil."""
import argparse
import json
CONTRACTS = {"phi9_local_normal": (15, "phi9+nx_center+ny_center+ny_left+ny_right+nx_top+nx_bottom"), "phi9": (9, "phi9"), "phi9_full_normal": (27, "phi9+nx9+ny9"), "phi9_center_normal": (11, "phi9+nx_center+ny_center"), "phi9_cross_normal": (19, "phi9+nx_cross5+ny_cross5")}
if __name__ == "__main__":
    p=argparse.ArgumentParser();p.add_argument("--manifest",required=True);p.add_argument("--feature-mode",choices=CONTRACTS,required=True);a=p.parse_args()
    with open(a.manifest) as f: m=json.load(f)
    dim,order=CONTRACTS[a.feature_mode];ft=m["feature_transform"]
    if (ft["raw_feature_dim"],ft["output_dim"],ft["feature_order"],ft["transform_kind"],m["model_config"]["input_dim"]) != (dim,dim,order,"standardize",dim):
        raise SystemExit("Model export does not match requested feature mode")
