"""Metadata-only future candidate planner; does not generate recordings or train.

Preserves the v11 parameter DISTRIBUTIONS and four equal groups. This is a new
seed-address version, not a replay of v11. Seeds are128bit hex strings in JSON.
The HGA observation prior remains unqualified; output is NOT a training manifest.
"""
from collections import Counter
import hashlib
import json
from pathlib import Path
import numpy as np
from recipes import GROUPS,SPEC

VERSION='uecog-candidate-plan-v13-identity1'
# One eight-world block realizes the proposed .25 group weights and uniform
# conditional core weights exactly. This block is a coverage unit, not an epoch.
BLOCK=('linear','kernel','switching','rslds','local','ei','oscillator','oscillator')
GROUP={core:group for group,cores in GROUPS.items() for core in cores}
SEED_KEYS=('core_seed_hex','renderer_seed_hex','recipe_seed_hex')


def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()


def seed_hex(*address):
    return digest([VERSION,*address])[:32]


def seed_int(value):
    if not isinstance(value,str) or len(value)!=32 or any(c not in '0123456789abcdef' for c in value):
        raise ValueError('Seed must be exactly32 lowercase hex digits; never a JSON number.')
    return int(value,16)


def settings_from_seed(value):
    # Same draw order, branches and priors as frozen v11 draw_recipe. Only the
    # versioned seed addressing is new; v11 source/payloads remain untouched.
    rng=np.random.default_rng(seed_int(value));coupled=bool(rng.random()>=.6)
    return dict(hga_gain=float(rng.uniform(.25,.4)),
                spatial_sigma_cells=[float(rng.uniform(1,1.3)),float(rng.uniform(1,1.3)),float(rng.uniform(.25,.65))],
                shared_core_weight=float(rng.uniform(.35,.8)),theta_pac=float(rng.uniform(.02,.08)) if coupled else 0.,
                beta_scale=float(rng.uniform(.1,.3)) if coupled else 0.,broad_gain=0.,
                coupling_profile='weak' if coupled else 'absent')


def plan_worlds(plan_seed,split,blocks):
    seed_int(plan_seed)
    if split not in ('future_train','future_valid','public','qualification'):
        raise ValueError('Unknown namespace')
    if isinstance(blocks,bool) or not isinstance(blocks,int) or blocks<1:
        raise ValueError('Choose an explicit positive count of eight-world blocks.')
    worlds=[]
    for block in range(blocks):
        order=np.random.default_rng(seed_int(seed_hex('order',plan_seed,split,block))).permutation(8)
        for slot,i in enumerate(order):
            family=BLOCK[int(i)];address=[plan_seed,split,block,slot,family]
            seeds={key:seed_hex(purpose,*address) for key,purpose in zip(SEED_KEYS,['core','renderer','recipe'])}
            group_id=f"world/{family}/{seeds['core_seed_hex']}"  # split is NOT part of identity
            worlds.append(dict(world_id=f'{split}/{block}/{slot}',split=split,block=block,slot=slot,family=family,group=GROUP[family],
                               world_group_id=group_id,**seeds,settings=settings_from_seed(seeds['recipe_seed_hex'])))
    return worlds


def validate_worlds(worlds):
    seen_ids=set();core_identities={};streams={};counts=Counter();blocks={}
    for w in worlds:
        if w['world_id'] in seen_ids:raise ValueError('Duplicate world_id')
        seen_ids.add(w['world_id']);counts[w['group']]+=1
        core_identity=(w['family'],seed_int(w['core_seed_hex']))
        prior=core_identities.get(core_identity)
        if prior is not None:
            raise ValueError(f"Repeated core stream across world groups or splits: {prior} and {w['world_id']}")
        core_identities[core_identity]=w['world_id']
        if w['world_group_id']!=f"world/{w['family']}/{w['core_seed_hex']}":raise ValueError('Incorrect split-independent group identity')
        if w['group']!=GROUP[w['family']]:raise ValueError('Core/group mismatch')
        for key in SEED_KEYS:
            value=seed_int(w[key])
            if value in streams:raise ValueError(f'Reused RNG stream: {streams[value]} and {(w["world_id"],key)}')
            streams[value]=(w['world_id'],key)
        if w['settings']!=settings_from_seed(w['recipe_seed_hex']):raise ValueError('Recipe differs from bound seed')
        blocks.setdefault((w['split'],w['block']),[]).append(w['family'])
    for key,families in blocks.items():
        if Counter(families)!=Counter(BLOCK):raise ValueError(f'Incomplete/imbalanced coverage block {key}')
    return dict(worlds=len(worlds),distinct_core_streams=len(core_identities),distinct_rng_streams=len(streams),group_counts=dict(counts),blocks=len(blocks),
                scope='Seed-stream/group identity only; compare realized core-parameter fingerprints as well when data are generated. Distinct seeds do not prove different mechanisms.')


def build_plan(plan_seed,train_blocks,valid_blocks):
    worlds=plan_worlds(plan_seed,'future_train',train_blocks)+plan_worlds(plan_seed,'future_valid',valid_blocks)
    checked=validate_worlds(worlds)
    return dict(version=VERSION,status='METADATA ONLY; HGA prior unqualified; not a training manifest',plan_seed_hex=plan_seed,
                candidate_spec_sha256=digest(SPEC),sampling='exactly balanced eight-world blocks; random order within each block',
                seeds='128bit lowercase hex strings; parse with int(value,16) in Python. No JSNumber round trip.',
                split_rule='Keep every renderer, geometry and crop sharing a world_group_id in the same split. Split-independent identity checks reject equal core streams.',
                training=False,recordings_generated=False,worlds=worlds,verification=checked)


if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--plan-seed-hex',required=True);p.add_argument('--train-blocks',type=int,required=True);p.add_argument('--valid-blocks',type=int,required=True);p.add_argument('--output',type=Path,required=True);args=p.parse_args()
    args.output.write_text(json.dumps(build_plan(args.plan_seed_hex,args.train_blocks,args.valid_blocks),indent=2)+'\n')
