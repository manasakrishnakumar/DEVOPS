"""Signed golden outputs: a release-time reference that does not depend on the model being healthy at start-up.

golden.json   : reference forecasts (24 steps, every tier) + sha256 of every model file, written at release time
golden.json.bundle : cosign sign-blob bundle (ECDSA P-256 over SHA-256 of golden.json; the private key never leaves the release machine)
cosign.pub    : public key (PEM)

verify(dir) checks the signature with the public key only (no network, no transparency log) and returns the parsed manifest.
check_files(base, manifest) re-hashes the model files and returns the list of files whose hash differs from the signed one.
"""
import base64
import hashlib
import json
import os


class SignatureError(Exception):
    pass


def _load_signature(d, raw):
    bundle_path = os.path.join(d, 'golden.json.bundle')
    sig_path = os.path.join(d, 'golden.json.sig')
    if os.path.exists(bundle_path):
        b = json.load(open(bundle_path, encoding='utf8'))
        ms = b['messageSignature']
        dig = ms.get('messageDigest', {}).get('digest')
        if dig and base64.b64decode(dig) != hashlib.sha256(raw).digest():
            raise SignatureError('digest in bundle does not match golden.json')
        return base64.b64decode(ms['signature'])
    if os.path.exists(sig_path):
        return base64.b64decode(open(sig_path, 'rb').read())
    raise SignatureError('no signature file (golden.json.bundle or golden.json.sig)')


def verify(d):
    from cryptography.exceptions import InvalidSignature
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import ec
    try:
        raw = open(os.path.join(d, 'golden.json'), 'rb').read()
        sig = _load_signature(d, raw)
        pub = serialization.load_pem_public_key(open(os.path.join(d, 'cosign.pub'), 'rb').read())
        pub.verify(sig, raw, ec.ECDSA(hashes.SHA256()))
    except InvalidSignature:
        raise SignatureError('signature does not match golden.json')
    except SignatureError:
        raise
    except Exception as e:  # missing file, malformed key or bundle
        raise SignatureError(type(e).__name__ + ': ' + str(e)[:80])
    return json.loads(raw)


def sha256_file(path, chunk=1 << 20):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        while True:
            b = f.read(chunk)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def check_files(base, manifest):
    """Return the relative paths whose current sha256 differs from (or is missing against) the signed manifest."""
    bad = []
    for rel, want in manifest.get('files', {}).items():
        p = os.path.join(base, rel)
        if not os.path.exists(p) or sha256_file(p) != want:
            bad.append(rel)
    return bad
