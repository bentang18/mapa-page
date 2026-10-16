"""Split identity and exact scheduling regressions; no voltage or training."""
import copy,json
import numpy as np
import pytest
from candidate_sampling_identity import build_plan,plan_worlds,seed_hex,seed_int,validate_worlds

ROOT_SEED='98adf1a93fa4ec892c366979d1bdfc22'


def test_json_preserves_full_seed_and_numpy_rng_stream():
    p=build_plan(ROOT_SEED,1,1);q=json.loads(json.dumps(p))
    assert p==q
    for w in p['worlds']:
        for key in ['core_seed_hex','renderer_seed_hex','recipe_seed_hex']:
            value=w[key];assert isinstance(value,str) and len(value)==32
            np.testing.assert_array_equal(np.random.default_rng(seed_int(value)).normal(size=8),np.random.default_rng(int(q['worlds'][p['worlds'].index(w)][key],16)).normal(size=8))


def test_same_core_cannot_hide_behind_different_split_names():
    worlds=build_plan(ROOT_SEED,1,1)['worlds'];a=worlds[0];b=next(w for w in worlds if w['split']=='future_valid' and w['family']==a['family'])
    b['core_seed_hex']=a['core_seed_hex'];b['world_group_id']=a['world_group_id']
    with pytest.raises(ValueError,match='Repeated core stream'):validate_worlds(worlds)


def test_extension_preserves_existing_world_addresses_and_exact_group_weights():
    initial=plan_worlds(ROOT_SEED,'future_train',2);extended=plan_worlds(ROOT_SEED,'future_train',4)
    assert initial==extended[:len(initial)]
    checked=validate_worlds(extended);assert set(checked['group_counts'].values())=={8}
    counts={f:sum(w['family']==f for w in extended) for f in ['linear','kernel','switching','rslds','local','ei','oscillator']}
    assert counts==dict(linear=4,kernel=4,switching=4,rslds=4,local=4,ei=4,oscillator=8)


def test_incomplete_coverage_and_recipe_tampering_are_rejected():
    worlds=build_plan(ROOT_SEED,1,1)['worlds']
    with pytest.raises(ValueError,match='Incomplete'):validate_worlds(worlds[:-1])
    bad=copy.deepcopy(worlds);bad[0]['settings']['hga_gain']=1
    with pytest.raises(ValueError,match='Recipe differs'):validate_worlds(bad)


def test_rng_stream_reuse_is_rejected_even_between_different_purposes():
    worlds=build_plan(ROOT_SEED,1,1)['worlds'];worlds[1]['renderer_seed_hex']=worlds[0]['recipe_seed_hex']
    with pytest.raises(ValueError,match='Reused RNG stream'):validate_worlds(worlds)


def test_seed_numbers_and_invalid_addresses_do_not_silently_round():
    with pytest.raises(ValueError):seed_int(2**127+1)
    with pytest.raises(ValueError):seed_int('0'*31)
    with pytest.raises(ValueError):plan_worlds(ROOT_SEED,'unknown',1)


def test_real_legacy_collision_is_rejected_by_new_identity_guard():
    from recipes import seed
    a=seed('future_train','switching',129637,'core');b=seed('future_valid','switching',7906,'core')
    assert a==b==566600193
    worlds=build_plan(ROOT_SEED,1,1)['worlds']
    for split in ['future_train','future_valid']:
        w=next(w for w in worlds if w['split']==split and w['family']=='switching')
        w['core_seed_hex']=f'{a:032x}';w['world_group_id']='world/switching/'+w['core_seed_hex']
    with pytest.raises(ValueError,match='Repeated core stream'):validate_worlds(worlds)


def test_frozen_parameter_draw_order_and_priors_are_preserved(monkeypatch):
    import recipes
    from candidate_sampling_identity import settings_from_seed
    for i in range(16):
        value=seed_hex('prior-parity',ROOT_SEED,i)
        monkeypatch.setattr(recipes,'seed',lambda *args:seed_int(value))
        assert recipes.draw_recipe('future_train','switching',i)==settings_from_seed(value)
