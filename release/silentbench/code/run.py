"""Experiment runner. Usage:
  python chaos/run.py --configs B C --faults crash hang oom corrupt --trials 3
  python chaos/run.py --load --configs A B C
Results are appended to results/fault_trials.jsonl and results/load.jsonl (one JSON object per line).
Configs: A = monolith (compose profile mono), B = microservices in Docker Compose, C = microservices on Kubernetes.
"""
import argparse
import datetime
import json
import os
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RES = os.path.join(ROOT, 'results')
os.makedirs(RES, exist_ok=True)
NET = 'devops_project_default'
IMG = 'climate-frontend:2'
KNS = 'climate'
K8S_CFGS = ('C', 'D', 'C4', 'D4', 'E4')


def sh(cmd, check=False, capture=True):
    r = subprocess.run(cmd, capture_output=capture, text=True, cwd=ROOT)
    if check and r.returncode:
        raise RuntimeError(f'{cmd}\n{r.stderr}')
    return r


def compose(*a):
    return sh(['docker', 'compose', *a])


def kube(*a):
    return sh(['kubectl', *a])


CFG4 = {'C4': ('0', 'envelope'), 'D4': ('1', 'envelope'), 'E4': ('1', 'envelope+inv')}   # image :4 variants


def switch_cfg4(cfg):
    """Image :4 with the guard off / envelope / envelope+invariants. Verifies image and env before returning."""
    guard, mode = CFG4[cfg]
    compose('--profile', 'mono', 'stop')
    kube('-n', KNS, 'set', 'image', 'deploy/inference-api', f'inference-api=climate-inference:{os.environ.get("INFER_TAG", "4")}')
    kube('-n', KNS, 'set', 'env', 'deploy/inference-api', f'SEMANTIC_GUARD={guard}', f'GUARD_MODE={mode}',
         'FAULT_INJECTION=1')
    kube('-n', KNS, 'rollout', 'restart', 'deploy/inference-api')
    kube('-n', KNS, 'scale', 'deploy/frontend', 'deploy/inference-api', '--replicas=1')
    ok = False
    for _ in range(8):
        time.sleep(10)
        r = kube('-n', KNS, 'rollout', 'status', 'deploy/inference-api', '--timeout=120s')
        if r.returncode == 0:
            ok = True
            break
    if not ok:
        raise RuntimeError(f'{cfg}: rollout did not complete')
    time.sleep(15)
    img = kube('-n', KNS, 'get', 'pods', '-l', 'app=inference-api', '-o',
               'jsonpath={.items[*].spec.containers[0].image}').stdout
    env = kube('-n', KNS, 'get', 'deploy/inference-api', '-o',
               'jsonpath={.spec.template.spec.containers[0].env}').stdout
    if f'climate-inference:{os.environ.get("INFER_TAG", "4")}' not in img or f'"value":"{guard}"' not in env.replace(' ', ''):
        raise RuntimeError(f'{cfg}: pod verification failed image={img} env={env}')
    print(f'  [{cfg}] verified image={img} guard={guard} mode={mode}')


def switch_to(cfg):
    if cfg in CFG4:
        return switch_cfg4(cfg)
    """Only one environment runs at a time (laptop RAM)."""
    if cfg in K8S_CFGS:
        compose('--profile', 'mono', 'stop')
        if cfg == 'D':   # same cluster, new image + semantic guard on
            kube('-n', KNS, 'set', 'image', 'deploy/inference-api', 'inference-api=climate-inference:3')
            kube('-n', KNS, 'set', 'env', 'deploy/inference-api', 'SEMANTIC_GUARD=1')
        else:
            kube('-n', KNS, 'set', 'image', 'deploy/inference-api', 'inference-api=climate-inference:2')
            kube('-n', KNS, 'set', 'env', 'deploy/inference-api', 'SEMANTIC_GUARD-')
        kube('-n', KNS, 'scale', 'deploy/frontend', 'deploy/inference-api', '--replicas=1')
        kube('-n', KNS, 'rollout', 'status', 'deploy/inference-api', '--timeout=300s')
        kube('-n', KNS, 'rollout', 'status', 'deploy/frontend', '--timeout=300s')
    else:
        kube('-n', KNS, 'scale', 'deploy/frontend', 'deploy/inference-api', '--replicas=0')
        compose('--profile', 'mono', 'stop')
        if cfg == 'A':
            compose('--profile', 'mono', 'up', '-d', 'monolith')
        else:
            compose('up', '-d', 'postgres', 'inference-api', 'frontend')


def reset(cfg):
    if cfg in K8S_CFGS:
        kube('-n', KNS, 'rollout', 'restart', 'deploy/inference-api')
        kube('-n', KNS, 'rollout', 'status', 'deploy/inference-api', '--timeout=300s')
    elif cfg == 'B':
        compose('restart', 'inference-api')
    else:
        compose('--profile', 'mono', 'restart', 'monolith')


def hosts(cfg):
    if cfg == 'A':
        return 'http://monolith:5000', 'http://monolith:5000'
    return 'http://frontend:5000', 'http://inference-api:5001'


def run_probe(cfg, args):
    if cfg in K8S_CFGS:
        ov = json.dumps({'spec': {'containers': [{'name': 'p', 'image': IMG, 'imagePullPolicy': 'Never',
                         'command': ['python', '/probe/probe.py', *args],
                         'volumeMounts': [{'name': 's', 'mountPath': '/probe'}]}],
                         'volumes': [{'name': 's', 'configMap': {'name': 'probe-script'}}]}})
        name = 'probe-' + str(int(time.time()))
        r = kube('-n', KNS, 'run', name, '--rm', '-i', '--restart=Never', f'--image={IMG}',
                 '--image-pull-policy=Never', f'--overrides={ov}', '--quiet')
    else:
        r = sh(['docker', 'run', '--rm', '--network', NET, '-v', f'{os.path.join(ROOT, "chaos")}:/probe:ro', IMG,
                'python', '/probe/probe.py', *args])
    lines = [l for l in r.stdout.splitlines() if l.startswith('{')]
    if not lines:
        print('  probe failed:', r.stderr[-300:])
    return [json.loads(l) for l in lines]


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--configs', nargs='+', default=['B', 'C'])
    p.add_argument('--faults', nargs='+', default=['crash', 'hang', 'oom', 'corrupt'])
    p.add_argument('--trials', type=int, default=3)
    p.add_argument('--load', action='store_true')
    p.add_argument('--silent', action='store_true')
    p.add_argument('--fault-window', type=float, default=30)
    p.add_argument('--heal-window', type=float, default=10)
    p.add_argument('--trial-offset', type=int, default=0)
    p.add_argument('--levels', default='1,2,4,8')
    a = p.parse_args()
    stamp = datetime.datetime.now().isoformat(timespec='seconds')
    for cfg in a.configs:
        print(f'== config {cfg}')
        switch_to(cfg)
        front, infer = hosts(cfg)
        if a.silent:
            sfaults = a.faults if a.faults != ['crash', 'hang', 'oom', 'corrupt'] else                 ['corrupt', 'bitflip', 'bitflip_severe', 'stale', 'scaler', 'unitchange', 'flatline', 'delay']
            for fault in sfaults:
                for t in range(a.trials):
                    res = run_probe(cfg, ['--mode', 'silent', '--base', infer, '--probe-path',
                                          '/predict?model=auto&steps=6', '--fault', fault, '--rps', '5',
                                          '--warmup', '15', '--fault-window', str(a.fault_window),
                                          '--heal-window', str(a.heal_window)])
                    for r in res:
                        r.update(config=cfg, trial=a.trial_offset + t + 1, ts=stamp)
                        with open(os.path.join(RES, 'silentbench.jsonl'), 'a') as f:
                            f.write(json.dumps(r) + chr(10))
                        print('  ', cfg, fault, a.trial_offset + t + 1, r.get('fault_window'), r.get('detect_s'))
            continue
        if a.load:
            for flow, base, path in (('app', front, '/dashboard'),) + ((('api', infer, '/predict?model=sarima&steps=12'),) if cfg != 'A' else ()):
                res = run_probe(cfg, ['--mode', 'load', '--flow', flow, '--base', base, '--probe-path', path,
                                      '--levels', a.levels, '--duration', '20'])
                with open(os.path.join(RES, 'load.jsonl'), 'a') as f:
                    for r in res:
                        r.update(config=cfg, ts=stamp)
                        f.write(json.dumps(r) + '\n')
                        print('  ', r)
            continue
        for fault in a.faults:
            if cfg == 'A' and fault == 'corrupt':
                continue
            for t in range(a.trials):
                base = infer if cfg != 'A' else front
                path = '/predict?model=sarima&steps=3' if cfg != 'A' else '/healthz'
                res = run_probe(cfg, ['--mode', 'fault', '--base', base, '--probe-path', path, '--fault', fault])
                for r in res:
                    r.update(config=cfg, trial=t + 1, ts=stamp)
                    with open(os.path.join(RES, 'fault_trials.jsonl'), 'a') as f:
                        f.write(json.dumps(r) + '\n')
                    print('  ', r)
                reset(cfg)


if __name__ == '__main__':
    main()

