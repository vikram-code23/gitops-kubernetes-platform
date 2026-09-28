from kubernetes import client,config
from google import genai
from google.genai import types

config.load_kube_config(
    context = "kind-gitops-cluster"
)

v1 = client.CoreV1Api()
apps_v1 = client.AppsV1Api()
custom_objects = client.CustomObjectsApi()
networking_v1 = client.NetworkingV1Api()

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
        
def get_service_status(namespace, service):
    service_data = v1.read_namespaced_service(
        name=service,
        namespace=namespace
    )

    return {
        "service": service_data.metadata.name,
        "namespace": service_data.metadata.namespace,
        "type": service_data.spec.type,
        "cluster_ip": service_data.spec.cluster_ip,
        "ports": [
            {
                "port": port.port,
                "target_port": str(port.target_port),
                "protocol": port.protocol
            }
            for port in service_data.spec.ports
        ]
    }

def get_service_endpoints(namespace, service):
    endpoints = v1.read_namespaced_endpoints(
        name=service,
        namespace=namespace
    )

    addresses = []

    for subset in endpoints.subsets or []:

        for address in subset.addresses or []:
            addresses.append({
                "ip": address.ip,
                "pod": (
                    address.target_ref.name
                    if address.target_ref
                    else None
                )
            })

    return {
        "service": service,
        "namespace": namespace,
        "ready_endpoints": len(addresses),
        "endpoints": addresses
    }

def get_ingress_status(namespace, ingress):
    ingress_data = networking_v1.list_namespaced_ingress(
        namespace=namespace
    )

    for item in ingress_data.items:

        if item.metadata.name == ingress:

            rules = []

            for rule in item.spec.rules or []:

                host = rule.host

                paths = []

                if rule.http:
                    for path in rule.http.paths:

                        paths.append({
                            "path": path.path,
                            "service": (
                                path.backend.service.name
                                if path.backend.service
                                else None
                            ),
                            "port": (
                                path.backend.service.port.number
                                if path.backend.service
                                and path.backend.service.port
                                else None
                            )
                        })

                rules.append({
                    "host": host,
                    "paths": paths
                })

            return {
                "ingress": ingress,
                "namespace": namespace,
                "rules": rules
            }

    return {
        "error": f"Ingress {ingress} not found"
    }

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

def troubleshoot_application(
    application,
    application_namespace="argocd",
    workload_namespace="gitops-web",
    deployment="gitops-web",
    service="gitops-web-service",
    ingress="gitops-web-ingress"
):
    argo_status = get_argocd_application(
        application,
        application_namespace
    )

    deployment_status = get_deployment_status(
        workload_namespace,
        deployment
    )
    service_status = get_service_status(
    workload_namespace,
    service
    )

    service_endpoints = get_service_endpoints(
        workload_namespace,
        service
    )

    ingress_status = get_ingress_status(
        workload_namespace,
        ingress
    )
    pods = get_pods(
        workload_namespace
    )

    pod_details = []

    for pod in pods:

        pod_name = pod["name"]

        pod_data = {
            "name": pod_name,
            "status": pod["status"],
            "logs": get_pod_logs(
                workload_namespace,
                pod_name
            ),
            "events": get_pod_events(
                workload_namespace,
                pod_name
            )
        }

        pod_details.append(pod_data)

    result = {
        "argocd": argo_status,
        "deployment": deployment_status,
        "pods": pod_details,
        "service" : service_status,
        "service_endpoints" : service_endpoints,
        "ingress" : ingress_status
    }
    
    analysis = analyze_troubleshooting_result(
        result
    )
    
    result["analysis"] = analysis
    
    return result

def analyze_troubleshooting_result(result):

    findings = []
    overall_status = "HEALTHY"

    affected_resources = []
    likely_causes = []
    recommended_next_steps = []

    argo = result["argocd"]
    deployment = result["deployment"]
    service = result["service"]
    service_endpoints = result["service_endpoints"]
    ingress = result["ingress"]
    # --------------------------------------------------
    # 1. Argo CD checks
    # --------------------------------------------------

    if argo["sync_status"] != "Synced":

        overall_status = "WARNING"

        findings.append(
            f"Argo CD application is "
            f"{argo['sync_status']}."
        )

        if argo["application"] not in affected_resources:
            affected_resources.append(
                argo["application"]
            )

        likely_causes.append(
            "The Kubernetes resources may differ "
            "from the desired Git state."
        )

        recommended_next_steps.append(
            "Inspect the Argo CD application diff "
            "and synchronization status."
        )

    if argo["health_status"] != "Healthy":

        overall_status = "WARNING"

        findings.append(
            f"Argo CD health status is "
            f"{argo['health_status']}."
        )

        affected_resources.append(
            argo["application"]
        )

        likely_causes.append(
            "One or more Kubernetes resources "
            "managed by the Argo CD application "
            "may not be healthy."
        )

        recommended_next_steps.append(
            "Inspect the application's Kubernetes "
            "resources and Argo CD health details."
        )


    # --------------------------------------------------
    # 2. Deployment checks
    # --------------------------------------------------

    if deployment["ready_replicas"] < deployment["desired_replicas"]:

        overall_status = "WARNING"

        findings.append(
            f"Deployment {deployment['deployment']} has only "
            f"{deployment['ready_replicas']}/"
            f"{deployment['desired_replicas']} "
            f"ready replicas."
        )

        if deployment["deployment"] not in affected_resources:
            affected_resources.append(
                deployment["deployment"]
            )

        likely_causes.append(
            "One or more application pods are "
            "not becoming ready."
        )

        recommended_next_steps.append(
            "Inspect pod status, logs, and "
            "Kubernetes warning events."
        )


    # --------------------------------------------------
    # 3. Pod checks
    # --------------------------------------------------

    for pod in result["pods"]:

        pod_name = pod["name"]
        pod_status = pod["status"]

        if pod_status != "Running":

            overall_status = "WARNING"

            findings.append(
                f"Pod {pod_name} is in "
                f"{pod_status} state."
            )
            if pod_name not in affected_resources:
                affected_resources.append(
                    pod_name
                )

            likely_causes.append(
                f"Pod {pod_name} is not "
                "running normally."
            )

            recommended_next_steps.append(
                f"Inspect logs and events "
                f"for pod {pod_name}."
            )


        # --------------------------------------------------
        # 4. Kubernetes event checks
        # --------------------------------------------------

        warning_reasons = [
            "Failed",
            "FailedMount",
            "FailedAttachVolume",
            "FailedScheduling",
            "BackOff",
            "Unhealthy",
            "Killing",
            "Evicted",
            "OOMKilling",
            "FailedCreatePodSandBox"
        ]

        for event in pod["events"]:

            if event["reason"] in warning_reasons:

                overall_status = "WARNING"

                findings.append(
                    f"Pod {pod_name}: "
                    f"{event['reason']} - "
                    f"{event['message']}"
                )

                affected_resources.append(
                    pod_name
                )


                # Specific diagnosis for scheduling
                if event["reason"] == "FailedScheduling":

                    likely_causes.append(
                        f"Pod {pod_name} could not be "
                        "scheduled because Kubernetes "
                        "could not find a suitable node."
                    )

                    recommended_next_steps.append(
                        f"Inspect scheduling events and "
                        f"node resource availability for "
                        f"pod {pod_name}."
                    )


                # Specific diagnosis for volume mounting
                elif event["reason"] == "FailedMount":

                    likely_causes.append(
                        f"Pod {pod_name} may have "
                        "a volume mounting problem."
                    )

                    recommended_next_steps.append(
                        f"Inspect volume configuration "
                        f"and mount-related events for "
                        f"pod {pod_name}."
                    )


                # Specific diagnosis for BackOff
                elif event["reason"] == "BackOff":

                    likely_causes.append(
                        f"Pod {pod_name} is repeatedly "
                        "failing to start."
                    )

                    recommended_next_steps.append(
                        f"Inspect container logs and "
                        f"previous container logs for "
                        f"pod {pod_name}."
                    )


                # General event diagnosis
                else:

                    likely_causes.append(
                        f"Kubernetes reported a "
                        f"{event['reason']} event for "
                        f"pod {pod_name}."
                    )

                    recommended_next_steps.append(
                        f"Review Kubernetes events and "
                        f"logs for pod {pod_name}."
                    )
         
            
        # --------------------------------------------------
        # 7. Application log checks
        # --------------------------------------------------

        logs = pod["logs"]["logs"]

        error_keywords = [
            "error",
            "exception",
            "fatal",
            "failed",
            "crash",
            "panic"
        ]

        logs_lower = logs.lower()

        for keyword in error_keywords:

            if keyword in logs_lower:

                overall_status = "WARNING"

                findings.append(
                    f"Possible '{keyword}' detected "
                    f"in logs of pod {pod_name}."
                )

                affected_resources.append(
                    pod_name
                )

                likely_causes.append(
                    f"Application logs from pod "
                    f"{pod_name} contain "
                    "error-related messages."
                )

                recommended_next_steps.append(
                    f"Review the relevant application "
                    f"logs from pod {pod_name} to "
                    "identify the failing component."
                )

                break

    # 5. Service checks
    if service.get("error"):
        overall_status = "WARNING"
        findings.append(
            f"Service check failed: {service['error']}"
        )
        likely_causes.append(
            "The application Service could not be read."
        )
        recommended_next_steps.append(
            "Inspect the Kubernetes Service configuration."
        )
    if service_endpoints.get("ready_endpoints", 0) == 0:
        overall_status = "WARNING"
        findings.append(
            f"Service {service['service']} has no ready endpoints."
        )
        if service["service"] not in affected_resources:
            affected_resources.append(
                service["service"]
            )

        likely_causes.append(
            f"Service {service['service']} has no healthy "
            "backend endpoints."
        )

        recommended_next_steps.append(
            f"Inspect pod readiness and Service selectors "
            f"for {service['service']}."
            )
        
        
    # 6. Ingress checks
    if ingress.get("error"):
        overall_status = "WARNING"

        findings.append(
            f"Ingress check failed: {ingress['error']}"
        )

        likely_causes.append(
            "The application Ingress resource could not be read."
        )

        recommended_next_steps.append(
            "Inspect the Kubernetes Ingress configuration."
        )


    for rule in ingress.get("rules", []):
        for path in rule.get("paths", []):
            backend_service = path.get("service")

            if backend_service != service["service"]:
                overall_status = "WARNING"

                findings.append(
                    f"Ingress {ingress['ingress']} routes path "
                    f"{path['path']} to unexpected Service "
                    f"{backend_service}."
                )

                if ingress["ingress"] not in affected_resources:
                    affected_resources.append(
                        ingress["ingress"]
                    )

                likely_causes.append(
                    f"Ingress {ingress['ingress']} may be pointing "
                    f"to the wrong backend Service."
                )

                recommended_next_steps.append(
                    f"Inspect the Ingress backend configuration "
                    f"for {ingress['ingress']}."
                )

    # --------------------------------------------------
    # 8. Clean duplicate diagnosis results
    # --------------------------------------------------

    affected_resources = list(
        dict.fromkeys(affected_resources)
    )

    likely_causes = list(
        dict.fromkeys(likely_causes)
    )

    recommended_next_steps = list(
        dict.fromkeys(recommended_next_steps)
    )


    # --------------------------------------------------
    # 9. Return structured diagnosis
    # --------------------------------------------------

    return {
        "overall_status": overall_status,
        "findings": findings,
        "affected_resources": affected_resources,
        "likely_causes": likely_causes,
        "recommended_next_steps": recommended_next_steps
    }


tool_registry = {
    "get_pods": get_pods,
    "get_deployment_status": get_deployment_status,
    "get_pod_logs": get_pod_logs,
    "get_pod_events": get_pod_events,
    "get_argocd_application": get_argocd_application,
    "get_service_status": get_service_status,
    "get_service_endpoints": get_service_endpoints,
    "get_ingress_status": get_ingress_status,
    "troubleshoot_application": troubleshoot_application
}

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
        },
        {
            "name": "troubleshoot_application",
            "description": (
                "Read-only Kubernetes and Argo CD troubleshooting workflow. "
                "Collects Argo CD application status, deployment replica "
                "status, pod status, logs, and events, then performs basic "
                "evidence-based health analysis. Use this tool when the user "
                "asks to troubleshoot or diagnose their application."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "application": {
                        "type": "string",
                        "description": "Argo CD application name."
                    },
                    "application_namespace": {
                        "type": "string",
                        "description": "Argo CD namespace.",
                        "default": "argocd"
                    },
                    "workload_namespace": {
                        "type": "string",
                        "description": "Kubernetes namespace containing the application workload.",
                        "default": "gitops-web"
                    },
                    "deployment": {
                        "type": "string",
                        "description": "Kubernetes deployment name.",
                        "default": "gitops-web"
                    },
                    "service": {
                        "type": "string",
                        "description": "Kubernetes Service name.",
                        "default": "gitops-web-service"
                    },
                    "ingress": {
                        "type": "string",
                        "description": "Kubernetes Ingress resource name.",
                        "default": "gitops-web-ingress"
                    }
                },
                "required": [
                    "application"
                ]
            }
        },
            {
                "name": "get_service_status",
                "description": (
                    "Get the current configuration and status information "
                    "for a Kubernetes Service."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "namespace": {
                            "type": "string",
                            "description": "The Kubernetes namespace."
                        },
                        "service": {
                            "type": "string",
                            "description": "The Kubernetes Service name."
                        }
                    },
                    "required": [
                        "namespace",
                        "service"
                    ]
                }
            },
            {
                "name": "get_service_endpoints",
                "description": (
                    "Get the ready endpoint addresses associated with "
                    "a Kubernetes Service."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "namespace": {
                            "type": "string",
                            "description": "The Kubernetes namespace."
                        },
                        "service": {
                            "type": "string",
                            "description": "The Kubernetes Service name."
                        }
                    },
                    "required": [
                        "namespace",
                        "service"
                    ]
                }
            },
            {
                "name": "get_ingress_status",
                "description": (
                    "Get the configuration of a Kubernetes Ingress, "
                    "including hosts, paths, backend Services, and ports."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "namespace": {
                            "type": "string",
                            "description": "The Kubernetes namespace."
                        },
                        "ingress": {
                            "type": "string",
                            "description": "The Kubernetes Ingress resource name."
                        }
                    },
                    "required": [
                        "namespace",
                        "ingress"
                    ]
                }
            },
        
    ]
)

client_ai = genai.Client()

gemini_config = types.GenerateContentConfig(
    tools=[tools],

    system_instruction="""
You are an AI-powered Kubernetes and GitOps troubleshooting agent.

Your job is to help users understand the current state of their
Kubernetes applications and Argo CD deployments.

Rules:

1. Use the available tools whenever real Kubernetes or Argo CD
   information is required.

2. Treat tool results as the source of truth for cluster state.
   Never invent pod status, deployment status, logs, events,
   Service status, endpoints, Ingress configuration, or Argo CD status.

3. You are READ-ONLY.
   Never perform actions that modify the Kubernetes cluster,
   Argo CD applications, deployments, pods, or infrastructure.

4. When the user asks to troubleshoot an application, prefer the
   troubleshoot_application tool because it collects multiple
   sources of evidence and performs basic health analysis.

5. Use individual tools when the user asks for a specific piece
   of information, such as pod logs, pod status, deployment status,
   Service information, endpoints, or Ingress configuration.

6. Clearly distinguish between:
   - GitOps synchronization problems
   - Kubernetes deployment problems
   - Pod runtime problems
   - Application/logging problems
   - Service and traffic-routing problems

7. If the available evidence is insufficient to determine the
   cause, clearly say that more information is required.

8. Give the user a concise explanation of:
   - Current status
   - Evidence found
   - Possible cause
   - Recommended next investigation step

9. When the user asks about application traffic routing,
   inspect the relevant Kubernetes Ingress, Service,
   and Service endpoints using the available tools.

10. Distinguish between:
    - Ingress resource
    - Ingress controller
    - Kubernetes Service
    - Service endpoints

11. Do not assume that an Ingress controller status represents
    the health of the application's Ingress resource.

12. A Kubernetes Service does not have a simple "Running"
    state like a Pod. Use Service configuration and ready
    endpoints to evaluate backend availability.

13. When diagnosing application health, consider evidence across
    Argo CD, Deployment, Pods, Events, Logs, Service,
    Service endpoints, and Ingress rather than relying on
    a single resource.

14. Do not claim that you fixed an issue because you cannot
    modify the environment.
""",

    automatic_function_calling=types.AutomaticFunctionCallingConfig(
        disable=True
    )
)

def run_agent(user_prompt):

    contents = [
        types.Content(
            role="user",
            parts=[
                types.Part.from_text(
                    text=user_prompt
                )
            ]
        )
    ]

    while True:

        try:

            response = client_ai.models.generate_content(
                model="gemini-3.6-flash",
                contents=contents,
                config=gemini_config
            )

        except Exception as e:

            error_message = str(e)

            if "503" in error_message:

                return (
                    "The AI model is temporarily unavailable "
                    "because of high demand. "
                    "Please try again in a moment."
                )

            if "429" in error_message:

                return (
                    "The AI model request limit has been reached. "
                    "Please wait before trying again."
                )

            return (
                "I couldn't process the request because "
                f"the AI service returned an error: {e}"
            )

        function_calls = []

        for part in response.candidates[0].content.parts:

            if part.function_call:
                function_calls.append(part.function_call)

        if not function_calls:

            return response.text

        contents.append(
            response.candidates[0].content
        )

        for function_call in function_calls:

            function_name = function_call.name

            args = dict(
                function_call.args or {}
            )

            tool_function = tool_registry.get(
                function_name
            )

            if tool_function is None:

                result = {
                    "error": f"Unknown tool: {function_name}"
                }

            else:

                try:

                    result = tool_function(
                        **args
                    )

                except Exception as e:

                    result = {
                        "error": str(e)
                    }

            tool_response = types.Part.from_function_response(
                name=function_name,
                response={
                    "result": result
                }
            )

            contents.append(
                types.Content(
                    role="user",
                    parts=[
                        tool_response
                    ]
                )
            )
 


        
if __name__ == "__main__":

    print("=" * 60)
    print("       AI KUBERNETES & GITOPS TROUBLESHOOTING AGENT")
    print("=" * 60)
    
    print("\nAsk me anything about your Kubernetes application.")
    print("Type 'exit' to stop.\n")

    while True:

        user_prompt = input("You: ")

        if user_prompt.lower() == "exit":
            print("\nAgent: Goodbye!")
            break

        if not user_prompt.strip():
            continue

        result = run_agent(user_prompt)

        print("\nAgent:")
        print(result)
        print()
    
