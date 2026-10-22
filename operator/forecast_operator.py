"""ForecastService operator (kopf).

Watches the inference service's semantic health and chooses a recovery action.
Policies:
  rules          restart when persistently invalid (original behaviour)
  bandit         action values learned in the digital twin (analysis/twin_bandit.py -> policy.json mounted at /policy/policy.json);
                 a key 'signature|aN' (N = failed attempts so far in this incident) overrides the plain signature key
  release_aware  roll back to the last known-good release if the service became unhealthy after a release, else restart
  escalate       restart first (cheap, fixes transient faults); if the service is still invalid, roll back to the last
                 known-good release (fixes a bad release, which a restart cannot); as a last resort pin the surviving tier

Last known-good release = the ReplicaSet (pod-template-hash) that was serving while /health/semantic had been valid for
`goodAfter` consecutive checks. Rolling back re-applies that ReplicaSet's pod template (what `kubectl rollout undo` does).

Run: kopf run operator/forecast_operator.py --namespace climate
"""
import datetime
import json
import os

import kopf
import kubernetes
import requests

ACTIONS = ['none', 'restart', 'scale_up', 'rollback', 'pin_tier']


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


def choose(policy, sig, table, attempt=0, new_release=False):
    if sig == 'ok':
        return 'none'
    if policy == 'bandit':
        vals = table.get(f'{sig}|a{attempt}') or table.get(sig)
        if vals:
            best = min(vals, key=vals.get)
            # twin action names -> operator actions (tier_switch is performed by the service itself, no restart)
            return {'restart_only': 'restart', 'tier_switch': 'none', 'switch_then_restart': 'restart',
                    'rollback': 'rollback', 'pin_tier': 'pin_tier'}.get(best, 'restart')
        return 'restart'
    if policy == 'release_aware':
        return 'rollback' if new_release else 'restart'
    if policy == 'escalate':
        if attempt <= 0:
            return 'restart'
        if attempt == 1:
            return 'rollback' if new_release else 'restart'
        return 'pin_tier'
    return 'restart'                 # rules policy / unseen signature


def release_info(apps, namespace, dep):
    """(deployment, replica sets, ReplicaSet of the current revision)."""
    d = apps.read_namespaced_deployment(dep, namespace)
    rev = (d.metadata.annotations or {}).get('deployment.kubernetes.io/revision')
    sel = ','.join(f'{k}={v}' for k, v in (d.spec.selector.match_labels or {}).items())
    rss = apps.list_namespaced_replica_set(namespace, label_selector=sel).items
    cur = next((rs for rs in rss if (rs.metadata.annotations or {}).get('deployment.kubernetes.io/revision') == rev), None)
    return d, rss, cur


def rolled_out(d):
    """True when the Deployment has finished rolling out its current template (no old or extra pods left)."""
    s = d.status
    want = d.spec.replicas or 0
    return bool(s and s.observed_generation is not None and s.observed_generation >= d.metadata.generation
                and (s.replicas or 0) == (s.updated_replicas or 0) == (s.available_replicas or 0) == want)


def template_hash(rs):
    return (rs.metadata.labels or {}).get('pod-template-hash') if rs is not None else None


def rollback_to(apps, namespace, dep, good_hash):
    """Re-apply the pod template of the known-good ReplicaSet (JSON patch, like kubectl rollout undo). False if not possible."""
    d, rss, cur = release_info(apps, namespace, dep)
    target = next((rs for rs in rss if template_hash(rs) == good_hash), None)
    if target is None or template_hash(cur) == good_hash:
        return False
    tmpl = kubernetes.client.ApiClient().sanitize_for_serialization(target.spec.template)
    (tmpl.get('metadata') or {}).get('labels', {}).pop('pod-template-hash', None)
    apps.patch_namespaced_deployment(dep, namespace, [{'op': 'replace', 'path': '/spec/template', 'value': tmpl}])
    return True


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
    good_after = int(spec.get('goodAfter', 6))
    try:
        r = requests.get(url + '/health/semantic', timeout=3)
        health = r.json()
    except Exception:
        health = None
    sig = signature(health)
    st = status or {}
    apps = kubernetes.client.AppsV1Api()
    bad = (st.get('consecutiveBad', 0) + 1) if sig != 'ok' else 0
    patch.status['signature'] = sig
    patch.status['consecutiveBad'] = bad
    patch.status['lastCheck'] = datetime.datetime.utcnow().isoformat() + 'Z'
    if sig == 'ok':                                              # remember the release that is demonstrably healthy
        streak = st.get('okStreak', 0) + 1
        patch.status['okStreak'] = streak
        if streak >= good_after:
            try:
                d, _, cur = release_info(apps, namespace, dep)
                if rolled_out(d):            # only a FULLY ROLLED-OUT release counts: during a rollout the old pod may still be answering
                    patch.status['attempt'] = 0
                    h = template_hash(cur)
                    if h and h != st.get('lastGoodHash'):
                        patch.status['lastGoodHash'] = h
            except Exception as e:
                logger.warning(f'could not record last good release: {e}')
        return
    patch.status['okStreak'] = 0
    if bad < need:
        return
    last = st.get('lastActionAt')
    if last:
        age = (datetime.datetime.utcnow() - datetime.datetime.fromisoformat(last.rstrip('Z'))).total_seconds()
        if age < cooldown:
            return
    attempt = int(st.get('attempt', 0))
    good_hash = st.get('lastGoodHash')
    new_release = False
    try:
        cur_hash = template_hash(release_info(apps, namespace, dep)[2])
        new_release = bool(good_hash and cur_hash and cur_hash != good_hash)
    except Exception as e:
        logger.warning(f'release lookup failed: {e}')
    action = choose(policy, sig, _policy_table(), attempt, new_release)
    if action == 'rollback':
        ok = good_hash is not None and rollback_to(apps, namespace, dep, good_hash)
        if not ok:
            action = 'restart'                                   # nothing to roll back to
    if action == 'restart':
        now = datetime.datetime.utcnow().isoformat() + 'Z'
        apps.patch_namespaced_deployment(dep, namespace, {'spec': {'template': {'metadata': {'annotations': {
            'kubectl.kubernetes.io/restartedAt': now}}}}})
    elif action == 'scale_up':
        cur = apps.read_namespaced_deployment_scale(dep, namespace).spec.replicas or 1
        apps.patch_namespaced_deployment_scale(dep, namespace, {'spec': {'replicas': min(cur + 1, 4)}})
    elif action == 'pin_tier':                                   # last resort: serve only the tiers that are still valid
        bad_tiers = sig.split(':', 1)[1].split(',') if ':' in sig else []
        keep = [t for t in ('sarima', 'lstm') if t not in bad_tiers] or ['sarima']
        apps.patch_namespaced_deployment(dep, namespace, {'spec': {'template': {'spec': {'containers': [
            {'name': dep, 'env': [{'name': 'MODELS', 'value': ','.join(keep)}]}]}}}})
    logger.info(f'signature={sig} bad={bad} attempt={attempt} new_release={new_release} action={action}')
    patch.status['lastAction'] = action
    patch.status['lastActionAt'] = datetime.datetime.utcnow().isoformat() + 'Z'
    patch.status['consecutiveBad'] = 0
    patch.status['attempt'] = attempt + 1
    hist = (st.get('history') or [])[-19:]
    hist.append({'t': datetime.datetime.utcnow().isoformat() + 'Z', 'signature': sig, 'action': action, 'attempt': attempt})
    patch.status['history'] = hist
