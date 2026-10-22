import base64
import hashlib
import json
import os
import shutil
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import signed_golden as sg  # noqa: E402

FIX = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'fixtures', 'cosign_sample')


def _copy_fixture(tmp_path):
    d = tmp_path / 'g'
    shutil.copytree(FIX, d)
    return str(d)


def _own_signed(tmp_path, manifest):
    """Sign with a fresh ECDSA P-256 key and write a cosign-style bundle (same structure cosign sign-blob --bundle writes)."""
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import ec
    key = ec.generate_private_key(ec.SECP256R1())
    raw = json.dumps(manifest).encode()
    sig = key.sign(raw, ec.ECDSA(hashes.SHA256()))
    d = tmp_path / 'own'
    d.mkdir()
    (d / 'golden.json').write_bytes(raw)
    (d / 'cosign.pub').write_bytes(key.public_key().public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo))
    (d / 'golden.json.bundle').write_text(json.dumps({'messageSignature': {
        'messageDigest': {'algorithm': 'SHA2_256', 'digest': base64.b64encode(hashlib.sha256(raw).digest()).decode()},
        'signature': base64.b64encode(sig).decode()}}))
    return str(d)


def test_real_cosign_bundle_verifies():
    m = sg.verify(FIX)
    assert m['golden']['sarima']['Rainfall'] == [1.0, 2.0]


def test_real_cosign_bundle_tampered_golden_rejected(tmp_path):
    d = _copy_fixture(tmp_path)
    p = os.path.join(d, 'golden.json')
    open(p, 'wb').write(open(p, 'rb').read().replace(b'2.0', b'2.1'))
    with pytest.raises(sg.SignatureError):
        sg.verify(d)


def test_wrong_public_key_rejected(tmp_path):
    d = _copy_fixture(tmp_path)
    other = _own_signed(tmp_path, {'x': 1})
    shutil.copy(os.path.join(other, 'cosign.pub'), os.path.join(d, 'cosign.pub'))
    with pytest.raises(sg.SignatureError):
        sg.verify(d)


def test_missing_signature_rejected(tmp_path):
    d = _copy_fixture(tmp_path)
    os.remove(os.path.join(d, 'golden.json.bundle'))
    with pytest.raises(sg.SignatureError):
        sg.verify(d)


def test_own_signature_roundtrip_and_digest_mismatch(tmp_path):
    d = _own_signed(tmp_path, {'files': {}, 'golden': {}})
    assert sg.verify(d) == {'files': {}, 'golden': {}}
    b = json.load(open(os.path.join(d, 'golden.json.bundle')))
    b['messageSignature']['messageDigest']['digest'] = base64.b64encode(b'0' * 32).decode()
    json.dump(b, open(os.path.join(d, 'golden.json.bundle'), 'w'))
    with pytest.raises(sg.SignatureError):
        sg.verify(d)


def test_file_hashes(tmp_path):
    (tmp_path / 'a.bin').write_bytes(b'weights')
    (tmp_path / 'b.bin').write_bytes(b'scaler')
    man = {'files': {'a.bin': sg.sha256_file(str(tmp_path / 'a.bin')), 'b.bin': sg.sha256_file(str(tmp_path / 'b.bin'))}}
    assert sg.check_files(str(tmp_path), man) == []
    (tmp_path / 'a.bin').write_bytes(b'weightz')              # one flipped byte
    assert sg.check_files(str(tmp_path), man) == ['a.bin']
    os.remove(tmp_path / 'b.bin')
    assert sorted(sg.check_files(str(tmp_path), man)) == ['a.bin', 'b.bin']
