"""ForecastService operator (kopf).

Watches the inference service's semantic health and chooses a recovery action.
Policies: 'rules' (restart when persistently invalid) or 'bandit' (action values learned in the digital twin,
analysis/twin_bandit.py -> policy.json mounted at /policy/policy.json).

Run: kopf run operator/forecast_operator.py --namespace climate
"""
import datetime
import json
import os
import random

import kopf
import kubernetes
import requests

ACTIONS = ['none', 'restart', 'scale_up']


def _policy_table():
    p = os.environ.get('POLICY_FILE', '/policy/policy.json')
    try:
        return json.load(open(p))
    except Exception:
        return {}


def signature(health):
    """Observable fault signature from /health/semantic (or connection failure)."""
    if health is None:
        return 'unreachable'
    if health.get('semantic_ok'):
        return 'ok'
    be = health.get('backends', {})
    bad = sorted(k for k, v in be.items() if not v.get('valid'))
    return 'invalid:' + ','.join(bad)


def choose(policy, sig, table):
    if sig == 'ok':
        return 'none'
    if policy == 'bandit' and sig in table:
        vals = table[sig]            # {twin action: expected cost}
        best = min(vals, key=vals.get)
        # twin action names -> operator actions (tier_switch is performed by the service itself, no restart)
        return {'restart_only': 'restart', 'tier_switch': 'none', 'switch_then_restart': 'restart'}.get(best, 'restart')
    return 'restart'                 # rules policy / unseen signature


@kopf.on.startup()
def configure(settings: kopf.OperatorSettings, **_):
    settings.posting.level = 20
    try:
        kubernetes.config.load_incluster_config()
    except Exception:
        kubernetes.config.load_kube_config()


@kopf.timer('climate.example.com', 'v1', 'forecastservices', interval=5.0, initial_delay=10.0)
def reconcile(spec, status, patch, name, namespace, logger, **_):
    url = spec.get('inferenceUrl', 'http://inference-api:5001')
    dep = spec.get('deployment', 'inference-api')
    need = int(spec.get('failureThreshold', 3))
    policy = spec.get('policy', 'rules')
    cooldown = int(spec.get('cooldownSeconds', 60))
    try:
        r = requests.get(url + '/health/semantic', timeout=3)
        health = r.json()
    except Exception:
        health = None
    sig = signature(health)
    st = status or {}
    bad = (st.get('consecutiveBad', 0) + 1) if sig != 'ok' else 0
    patch.status['signature'] = sig
    patch.status['consecutiveBad'] = bad
    patch.status['lastCheck'] = datetime.datetime.utcnow().isoformat() + 'Z'
    if bad < need:
        return
    last = st.get('lastActionAt')
    if last:
        age = (datetime.datetime.utcnow() - datetime.datetime.fromisoformat(last.rstrip('Z'))).total_seconds()
        if age < cooldown:
            return
    action = choose(policy, sig, _policy_table())
    apps = kubernetes.client.AppsV1Api()
    if action == 'restart':
        now = datetime.datetime.utcnow().isoformat() + 'Z'
        apps.patch_namespaced_deployment(dep, namespace, {'spec': {'template': {'metadata': {'annotations': {
            'kubectl.kubernetes.io/restartedAt': now}}}}})
    elif action == 'scale_up':
        cur = apps.read_namespaced_deployment_scale(dep, namespace).spec.replicas or 1
        apps.patch_namespaced_deployment_scale(dep, namespace, {'spec': {'replicas': min(cur + 1, 4)}})
    logger.info(f'signature={sig} bad={bad} action={action}')
    patch.status['lastAction'] = action
    patch.status['lastActionAt'] = datetime.datetime.utcnow().isoformat() + 'Z'
    patch.status['consecutiveBad'] = 0
    hist = (st.get('history') or [])[-19:]
    hist.append({'t': datetime.datetime.utcnow().isoformat() + 'Z', 'signature': sig, 'action': action})
    patch.status['history'] = hist
