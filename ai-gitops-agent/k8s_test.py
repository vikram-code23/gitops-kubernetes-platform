from kubernetes import client, config

config.load_kube_config()

v1 = client.CoreV1Api()
apps_v1 = client.AppsV1Api()

custom_objects = client.CustomObjectsApi()

def get_pods(namespace):
    pods = v1.list_namespaced_pod(namespace)

    results = []
    
    for pod in pods.items:
        results.append ({
            "name" : pod.metadata.name,
            "namespace" : pod.metadata.namespace,
            "status" : pod.status.phase
        })
        
    return results

print(get_pods("gitops-web"))

def get_deployment_status(namespace, deployment):
    deployment_data = apps_v1.read_namespaced_deployment(
        name=deployment,
        namespace=namespace
    )

    return {
        "deployment": deployment_data.metadata.name,
        "namespace": deployment_data.metadata.namespace,
        "desired_replicas": deployment_data.spec.replicas,
        "ready_replicas": deployment_data.status.ready_replicas or 0,
        "available_replicas": deployment_data.status.available_replicas or 0
    }
    
result = get_deployment_status("gitops-web", "gitops-web")
print(result)

def get_pod_logs(namespace, pod_name):
    logs = v1.read_namespaced_pod_log(
        name=pod_name,
        namespace=namespace
    )
    
    return {
        "pod": pod_name,
        "namespace": namespace,
        "logs": logs
    }
    
result = get_pod_logs("gitops-web","gitops-web-786f8bdf6f-dm8fz")

print(result)


def get_pod_events(namespace,pod_name):
    events = v1.list_namespaced_event(
        namespace = namespace,
        field_selector = f"involvedObject.name={pod_name}"
    )
    
    results = []
    
    for event in events.items:
        results.append({
            "reason" : event.reason,
            "message" : event.message,
            "type" : event.type
        })
        
    return results
        
result = get_pod_events("gitops-web", "gitops-web-786f8bdf6f-dm8fz")

print(result)

def troubleshoot_application(namespace, deployment):
    deployment_status = get_deployment_status(
        namespace, deployment
    )
    
    pods= get_pods(namespace)
    
    result = {
        "deployment" : deployment_status,
        "pods" : []
    }
    
    for pod in pods:
        pod_name = pod["name"]
        
        pod_data ={
            "status" : pod["status"],
            "logs" : get_pod_logs(
                namespace,
                pod_name
            ),
            
            "events" : get_pod_events(
                namespace,
                pod_name
            )
        }
        
        result["pods"].append({
            "name" : pod_name,
            **pod_data
        })
    
    return result

result = troubleshoot_application(
    "gitops-web",
    "gitops-web"
)

print(result)

def get_argocd_application(application, namespace="argocd"):
    try:
        app = custom_objects.get_namespaced_custom_object(
            group="argoproj.io",
            version="v1alpha1",
            namespace=namespace,
            plural="applications",
            name=application
        )

        status = app.get("status", {})
        sync = status.get("sync", {})
        health = status.get("health", {})

        return {
            "application": application,
            "sync_status": sync.get("status"),
            "health_status": health.get("status"),
            "revision": sync.get("revision")
        }

    except Exception as e:
        return {
            "error": str(e)
        }

print(get_argocd_application("gitops-web-app"))

tool_registry = {
    "get_pods": get_pods,
    "get_deployment_status": get_deployment_status,
    "get_pod_logs": get_pod_logs,
    "get_pod_events": get_pod_events,
    "get_argocd_application": get_argocd_application
}

print(tool_registry)

from google.genai import types

tools = types.Tool(
    function_declarations=[
        {
            "name": "get_pods",
            "description": "Get the current status of all pods in a Kubernetes namespace.",
            "parameters": {
                "type": "object",
                "properties": {
                    "namespace": {
                        "type": "string",
                        "description": "The Kubernetes namespace to inspect."
                    }
                },
                "required": ["namespace"]
            }
        },

        {
            "name": "get_deployment_status",
            "description": "Get the replica and availability status of a Kubernetes deployment.",
            "parameters": {
                "type": "object",
                "properties": {
                    "namespace": {
                        "type": "string",
                        "description": "The Kubernetes namespace."
                    },
                    "deployment": {
                        "type": "string",
                        "description": "The deployment name."
                    }
                },
                "required": ["namespace", "deployment"]
            }
        },

        {
            "name": "get_pod_logs",
            "description": "Read logs from a specific Kubernetes pod for troubleshooting.",
            "parameters": {
                "type": "object",
                "properties": {
                    "namespace": {
                        "type": "string",
                        "description": "The Kubernetes namespace."
                    },
                    "pod_name": {
                        "type": "string",
                        "description": "The name of the pod."
                    }
                },
                "required": ["namespace", "pod_name"]
            }
        },

        {
            "name": "get_pod_events",
            "description": "Get Kubernetes events associated with a specific pod for troubleshooting.",
            "parameters": {
                "type": "object",
                "properties": {
                    "namespace": {
                        "type": "string",
                        "description": "The Kubernetes namespace."
                    },
                    "pod_name": {
                        "type": "string",
                        "description": "The name of the pod."
                    }
                },
                "required": ["namespace", "pod_name"]
            }
        },

        {
            "name": "get_argocd_application",
            "description": "Get the Argo CD sync status, health status, and deployed revision of an application.",
            "parameters": {
                "type": "object",
                "properties": {
                    "application": {
                        "type": "string",
                        "description": "The Argo CD application name."
                    },
                    "namespace": {
                        "type": "string",
                        "description": "The namespace where the Argo CD application exists. Usually argocd."
                    }
                },
                "required": ["application"]
            }
        }
    ]
)

