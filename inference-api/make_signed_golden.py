"""Release step: compute the signed-golden manifest from the HEALTHY models of this image.

    python make_signed_golden.py OUT_DIR          (run inside the image, working directory = the app directory)
    cosign sign-blob --key cosign.key --use-signing-config=false --tlog-upload=false \
           --new-bundle-format --bundle OUT_DIR/golden.json.bundle OUT_DIR/golden.json

golden.json holds the 24-step reference forecast of every tier and the sha256 of every model file. The private key
stays on the release machine; the service only gets the public key (cosign.pub) and verifies the signature at start-up.
"""
import datetime
import json
import os
import sys

for k in ('SIGNED_GOLDEN_DIR', 'CORRUPT_AT_STARTUP'):          # the reference must come from the healthy, unmodified models
    os.environ.pop(k, None)
os.environ.setdefault('SEMANTIC_GUARD', '0')

import app as A  # noqa: E402
import backends as bk  # noqa: E402
import signed_golden as sg  # noqa: E402

out = sys.argv[1]
os.makedirs(out, exist_ok=True)
files = {}
for root, _, fs in os.walk(bk.MODEL_DIR):
    for f in sorted(fs):
        p = os.path.join(root, f)
        files[os.path.relpath(p, bk.MODEL_DIR).replace(os.sep, '/')] = sg.sha256_file(p)
manifest = {
    'version': 1,
    'created': datetime.datetime.utcnow().isoformat(timespec='seconds') + 'Z',
    'steps': 24,
    'tolerance_history_std': A.GOLDEN_TOL,
    'files': files,
    'golden': {n: {v: [float(x) for x in A.GOLDEN[n][v]] for v in bk.VARS} for n in A.GOLDEN},
}
with open(os.path.join(out, 'golden.json'), 'w', encoding='utf8') as f:
    json.dump(manifest, f, indent=1, sort_keys=True)
print('wrote', os.path.join(out, 'golden.json'), '| tiers:', list(manifest['golden']), '| model files hashed:', len(files))
