"""
Kubernetes dry-run executor. Always uses dry_run='All' — no real changes made.
Logs full diff of what *would* change to the audit_log.
"""
import logging
import os

log = logging.getLogger(__name__)

_K8S_AVAILABLE = False
try:
    from kubernetes import client as k8s_client, config as k8s_config
    _K8S_AVAILABLE = True
except ImportError:
    log.warning("kubernetes package not available — dry-run will simulate only")

# Action → K8s operation mapping
_ACTION_MAP = {
    "scale_up":    "patch_namespaced_deployment_scale",
    "scale_down":  "patch_namespaced_deployment_scale",
    "restart":     "patch_namespaced_deployment",
    "rollout":     "patch_namespaced_deployment",
    "alert_on_call": None,  # No K8s op needed
}

K8S_NAMESPACE = os.getenv("K8S_NAMESPACE", "default")


def _load_k8s_config() -> bool:
    if not _K8S_AVAILABLE:
        return False
    try:
        k8s_config.load_incluster_config()
        return True
    except Exception:
        try:
            k8s_config.load_kube_config()
            return True
        except Exception:
            return False


def execute_dry_run(action: str, target_kind: str, target_name: str) -> dict:
    """
    Simulate a K8s operation with dry_run='All'.
    Returns a diff dict describing what would change.
    """
    if action == "alert_on_call":
        log.info("[DRY-RUN] Would page on-call for %s/%s", target_kind, target_name)
        return {
            "action": action,
            "target": {"kind": target_kind, "name": target_name},
            "dry_run": True,
            "result": "alert_sent_to_oncall",
            "diff": "No K8s change — alerting only",
        }

    if not _load_k8s_config():
        log.info("[DRY-RUN] K8s unavailable — simulating %s on %s/%s", action, target_kind, target_name)
        return {
            "action": action,
            "target": {"kind": target_kind, "name": target_name},
            "dry_run": True,
            "result": "simulated",
            "diff": f"Would {action} {target_kind}/{target_name} in namespace {K8S_NAMESPACE}",
        }

    apps_v1 = k8s_client.AppsV1Api()
    diff_str = f"Would {action} {target_kind}/{target_name}"

    try:
        if action in ("restart", "rollout") and target_kind == "Deployment":
            import datetime
            patch = {
                "spec": {
                    "template": {
                        "metadata": {
                            "annotations": {
                                "kubectl.kubernetes.io/restartedAt": datetime.datetime.utcnow().isoformat()
                            }
                        }
                    }
                }
            }
            apps_v1.patch_namespaced_deployment(
                name=target_name,
                namespace=K8S_NAMESPACE,
                body=patch,
                dry_run="All",
            )
            diff_str = f"Would restart Deployment/{target_name} via rollout annotation"

        elif action == "scale_up" and target_kind == "Deployment":
            scale = apps_v1.read_namespaced_deployment_scale(target_name, K8S_NAMESPACE)
            current = scale.spec.replicas or 1
            apps_v1.patch_namespaced_deployment_scale(
                name=target_name,
                namespace=K8S_NAMESPACE,
                body={"spec": {"replicas": current + 1}},
                dry_run="All",
            )
            diff_str = f"Would scale Deployment/{target_name} from {current} → {current + 1} replicas"

        log.info("[DRY-RUN] %s", diff_str)
    except Exception as exc:
        log.warning("[DRY-RUN] K8s call failed (may not exist in dev): %s", exc)
        diff_str = f"Would {action} {target_kind}/{target_name} — K8s object not found in dev"

    return {
        "action": action,
        "target": {"kind": target_kind, "name": target_name},
        "dry_run": True,
        "result": "dry_run_ok",
        "diff": diff_str,
    }
