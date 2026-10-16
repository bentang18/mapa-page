"""Explicit procedural candidate, separate from every production training recipe."""
import hashlib
import json
import numpy as np
from cores import BASE as ORIGINAL
from cores import EXTRA

CORES = dict(ORIGINAL, **EXTRA)
GROUPS = {'statistical': ['linear', 'kernel'], 'switching': ['switching', 'rslds'],
          'spatial': ['local', 'ei'], 'oscillatory': ['oscillator']}
NAMES = {'linear': 'Multiscale stochastic memory', 'kernel': 'Kernel + nonlinear graph',
         'switching': 'Switching recurrent network', 'rslds': 'State-dependent switching',
         'local': 'Driven local field', 'ei': 'Excitation, inhibition + recovery',
         'oscillator': 'Coupled oscillators'}

SPEC = {
    'version': 'synthetic-worlds-candidate-v11', 'status': 'candidate; no training',
    'sampling': {'unit': 'continuous world, not independently invented frames',
                 'group_probability': {k: .25 for k in GROUPS}, 'groups': GROUPS,
                 'within_group': 'uniform', 'interpretation': 'balanced mechanism coverage; not estimated biological frequencies',
                 'parameter_prior': 'one common observation prior across all cores and subjects'},
    'observation_prior': {
        'hga_log_gain_uniform': [.25, .40], 'slow_mid_log_gain': .65,
        'extra_spatial_sigma_cells_uniform': [[1.0, 1.3], [1.0, 1.3], [.25, .65]],
        'inherited_carrier_blur_cells_uniform': [.3, .75],
        'shared_core_weight_uniform': [.35, .8],
        'explicit_coupling': {'absent_probability': .6, 'weak_probability': .4,
                             'weak_theta_log_gain_uniform': [.02, .08],
                             'weak_beta_coefficient_scale_uniform': [.1, .3]},
        'broad_gain': 0,
        'rationale': 'Weaker HGA gain and reduced explicit coupling follow v9/v10 diagnostics. Spatial/drive intervals are bounded engineering diversity, not identified neural parameters. Extra global gain remains excluded.',
        'excluded': ['strong coherent coupling package', 'HGA whitening', 'output blur',
                     'histogram matching', 'per-clip normalizer', 'synthetic anatomical labels',
                     'clinical artifacts without an explicit validated prior']},
    'frontend': {'raw_rate_hz': 2048, 'cache_rate_hz': 32, 'fft_lengths': [1024, 256, 128],
                 'inclusive_bins': [[1, 7], [2, 7], [4, 10]], 'window': 'periodic Hann',
                 'token_rates_hz': [4, 16, 32], 'native_point_selection_strides': [8, 2, 1],
                 'reference': 'common average over observed contacts',
                 'filters': 'canonical 60..300Hz notches and 0.5Hz high-pass',
                 'normalizer': 'per-contact/bin lower median and 1.4826 lower MAD; floor 1e-6',
                 'g3': 'clip normalized content to [-15,15]; complete synthetic availability'},
    'session': {'interior_s': 64, 'raw_context_each_side_s': 8,
                'normalizer_fit_s': [0, 24], 'buffer_s': [24, 32], 'content_s': [32, 64],
                'crop_s': 2, 'crop_alignment_cache_frames': 8,
                'statistical_scope': 'offline world; generator field standardization uses the simulated trajectory. This is not a causal online simulator.'},
    'provenance': {'seed_namespaces': ['public', 'qualification', 'future_train', 'future_valid'],
                   'group_id': 'namespace/core/core_seed; group every geometry, renderer and crop sharing a rule',
                   'separation': 'no world group may cross train/validation; reserve namespaces before generating',
                   'core_rule': 'generator functions sample parameters and initial conditions together; retain arrays plus full source hashes, not seed alone',
                   'anatomy': 'unknown; no fabricated atlas labels. Training integration is a separate contract.'},
    'claims': {'can_establish': ['input interface', 'reproducibility', 'descriptive dependence coverage'],
               'cannot_establish': ['speech semantics', 'physiological fidelity', 'useful learned representations', 'pretraining transfer']},
}


def seed(namespace, core, draw, purpose):
    return int.from_bytes(hashlib.sha256(f'v11/{namespace}/{core}/{draw}/{purpose}'.encode()).digest()[:4], 'little')


def draw_recipe(namespace, core, draw):
    rng = np.random.default_rng(seed(namespace, core, draw, 'recipe'))
    coupled = bool(rng.random() >= .6)
    return dict(hga_gain=float(rng.uniform(.25, .4)),
                spatial_sigma_cells=[float(rng.uniform(1, 1.3)), float(rng.uniform(1, 1.3)), float(rng.uniform(.25, .65))],
                shared_core_weight=float(rng.uniform(.35, .8)), theta_pac=float(rng.uniform(.02, .08)) if coupled else 0.,
                beta_scale=float(rng.uniform(.1, .3)) if coupled else 0., broad_gain=0.,
                coupling_profile='weak' if coupled else 'absent')


def write_spec(path):
    path.write_text(json.dumps(SPEC, indent=2) + '\n')
