Synthetic worlds candidate v11 — before pretraining

This is a standalone export of the numerical generator functions used for the
gallery. It contains no clinical data, data readers, labels or trainer adapter.
The numerical function bodies are extracted from the frozen implementation;
imports and module paths are adapted for portability. A replay receipt documents
whether this export reproduced the stored gallery packet on the tested platform.

Python 3.12. Install requirements.txt in an isolated environment, then:
  OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=2 python generate_demo.py --core switching --draw 0 --out demo-switching-0

The destination must be new. A typical world uses several GB of RAM and tens of
seconds of CPU time. Other choices: local, oscillator, kernel, linear, rslds, ei.
Use --draw 0 or 1 to reproduce the gallery seeds. Further nonnegative draws sample
additional worlds from the same prior. Do not put neighboring crops or geometry
variants of the same sampled rule on opposite sides of an evaluation split.

The packet has [contact, frequency-bin, 1024-frame] arrays for 32 seconds of
content. The first 24 seconds of the 64-second simulated interior are used only
for normalization, followed by an 8-second buffer. The content begins at second
32. All bins use a 32Hz cache; point selections at strides 8/2/1 yield Slow/Mid/HGA
4/16/32Hz tokens. arm0 uses the sampled interaction profile; arm1 removes explicit
theta/beta interactions with all other draws and the prefix statistics frozen.

Known limitation: this candidate can produce insufficient HGA spatial coherence.
These are experimental procedural priors, not fitted neural dynamics or an
approved pretraining corpus. No speech labels or anatomical labels are invented.
No model is trained here. See the accompanying specification and verification.

Numerical repair (v11.1)
The frozen v11 paired spatial operator uses different NumPy/Python scalar
precision across arms. With explicit coupling absent, normalized values differed
by up to1.3709068e-5 units in the audited examples. The exact zero-arm bitwise gate
therefore FAILED; it was not replaced by a looser passing tolerance.

A one-line fix forces consistent float64 scalar multiplication. Apply
precision_fix.patch to renderer.py before using it for new paired comparisons
(e.g. patch -p1 < precision_fix.patch). The repaired large-grid replay made both
raw arms bitwise identical and preserved the original control content under its
original prefix fit. The stored gallery remains frozen v11 for reproducibility.
This numerical issue does not explain the much larger HGA spatial mismatch.


Metadata-only future sampling planner (v13 identity1)
The legacy32bit seed function is retained above for exact gallery replay. Do not
assume different namespace strings alone guarantee distinct sampled rules: a
bounded metadata stress test found cross-split seed collisions. The current
28distinct gallery/qualification core identities have no cross-identity collision.

The optional candidate_sampling_identity.py planner uses128bit seed strings,
checks split-independent core identities, rejects RNG stream reuse, and schedules
exactly balanced eight-world blocks. It preserves v11 parameter distributions,
with a NEW seed-address version. Example (metadata only, no recordings):
  python candidate_sampling_identity.py --plan-seed-hex 98adf1a93fa4ec892c366979d1bdfc22 --train-blocks 4 --valid-blocks 2 --output example-plan.json
This is an illustrative48world metadata plan, NOT a recommended corpus size.
No model is trained and generate_demo.py does NOT consume this plan. HGA prior
qualification and the final data-generation adapter are still open. Do not treat
metadata verification as a pretraining GO or as evidence of useful representations.
Keep every observation/crop of a rule in one split. Compare realized core-rule
fingerprints as well when recordings are eventually generated.
