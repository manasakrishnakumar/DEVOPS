"""Test of the ValidatingAdmissionPolicy k8s/policy/vap-require-signed-golden.yaml on the live cluster.
All changes are SERVER-SIDE DRY RUNS: they go through admission but are never stored, so no pod is touched.
    python chaos/test_admission_policy.py      -> results/admission_policy_test.json
"""
import json
import os
import subprocess
import sys
import tempfile
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NS = 'climate'


def k(*a, stdin=None):
    r = subprocess.run(['kubectl', *a], capture_output=True, text=True, input=stdin, timeout=120)
    return r.returncode, (r.stdout + r.stderr).strip()


def patch_json(ops):
    f = tempfile.NamedTemporaryFile('w', suffix='.json', delete=False, encoding='utf8')
    json.dump(ops, f)
    f.close()
    try:
        return k('-n', NS, 'patch', 'deploy/inference-api', '--type=json', '--patch-file', f.name, '--dry-run=server')
    finally:
        os.unlink(f.name)


def main():
    rc, out = k('apply', '-f', os.path.join(ROOT, 'k8s', 'policy', 'vap-require-signed-golden.yaml'))
    print(out)
    time.sleep(8)                                    # the binding becomes active after a short delay
    dep = json.loads(k('-n', NS, 'get', 'deploy/inference-api', '-o', 'json')[1])
    vols = dep['spec']['template']['spec'].get('volumes', [])
    vidx = next(i for i, v in enumerate(vols) if (v.get('configMap') or {}).get('name') == 'signed-golden')
    envs = dep['spec']['template']['spec']['containers'][0].get('env', [])
    eidx = next(i for i, e in enumerate(envs) if e['name'] == 'SIGNED_GOLDEN_DIR')
    cases = []

    def case(name, expect, rc_out):
        rc, out = rc_out
        got = 'denied' if ('ValidatingAdmissionPolicy' in out and rc != 0) else ('admitted' if rc == 0 else 'error')
        cases.append({'case': name, 'expected': expect, 'got': got, 'pass': got == expect, 'message': out.splitlines()[-1][:240] if out else ''})
        print(('PASS ' if got == expect else 'FAIL ') + name + ' -> ' + got)

    case('remove SIGNED_GOLDEN_DIR env var from inference-api', 'denied',
         k('-n', NS, 'set', 'env', 'deploy/inference-api', 'SIGNED_GOLDEN_DIR-', '--dry-run=server'))
    mounts = dep['spec']['template']['spec']['containers'][0].get('volumeMounts', [])
    midx = next(i for i, m in enumerate(mounts) if m['name'] == vols[vidx]['name'])      # the mount must go too, or the API rejects the object before admission
    case('remove the signed-golden ConfigMap volume (and its mount)', 'denied',
         patch_json([{'op': 'remove', 'path': f'/spec/template/spec/containers/0/volumeMounts/{midx}'},
                     {'op': 'remove', 'path': f'/spec/template/spec/volumes/{vidx}'}]))
    case('point the volume at a different ConfigMap', 'denied',
         patch_json([{'op': 'replace', 'path': f'/spec/template/spec/volumes/{vidx}/configMap/name', 'value': 'other-golden'}]))
    case('unrelated change that keeps the wiring (extra env var)', 'admitted',
         k('-n', NS, 'set', 'env', 'deploy/inference-api', 'DRYRUN_PROBE=1', '--dry-run=server'))
    case('change the corruption env var (what the rollback experiment does)', 'admitted',
         k('-n', NS, 'set', 'env', 'deploy/inference-api', 'CORRUPT_AT_STARTUP=scaler', '--dry-run=server'))
    case('another Deployment without the wiring (policy must not touch it)', 'admitted',
         k('-n', NS, 'create', 'deployment', 'unrelated-probe', '--image=busybox', '--dry-run=server'))
    res = {'policy': 'require-signed-golden', 'namespace': NS, 'cluster_version': json.loads(k('version', '-o', 'json')[1]).get('serverVersion', {}).get('gitVersion'),
           'cases': cases, 'all_pass': all(c['pass'] for c in cases), 'method': 'kubectl --dry-run=server (admission runs, nothing is stored)'}
    os.makedirs(os.path.join(ROOT, 'results'), exist_ok=True)
    json.dump(res, open(os.path.join(ROOT, 'results', 'admission_policy_test.json'), 'w'), indent=1)
    print(json.dumps({'all_pass': res['all_pass'], 'n': len(cases)}))
    sys.exit(0 if res['all_pass'] else 1)


if __name__ == '__main__':
    main()
