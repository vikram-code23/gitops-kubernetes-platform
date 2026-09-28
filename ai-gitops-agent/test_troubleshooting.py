from agent import troubleshoot_application

def analyze_troubleshooting_result(result):

    findings = []
    overall_status = "HEALTHY"

    argo = result["argocd"]
    deployment = result["deployment"]

    # Argo CD checks
    if argo["sync_status"] != "Synced":
        overall_status = "WARNING"
        findings.append(
            f"Argo CD application is {argo['sync_status']}."
        )

    if argo["health_status"] != "Healthy":
        overall_status = "WARNING"
        findings.append(
            f"Argo CD health status is {argo['health_status']}."
        )

    # Deployment checks
    if deployment["ready_replicas"] < deployment["desired_replicas"]:
        overall_status = "WARNING"
        findings.append(
            f"Only {deployment['ready_replicas']} of "
            f"{deployment['desired_replicas']} replicas are ready."
        )

    # Pod checks
    for pod in result["pods"]:

        pod_name = pod["name"]
        pod_status = pod["status"]

        if pod_status != "Running":
            overall_status = "WARNING"

            findings.append(
                f"Pod {pod_name} is in {pod_status} state."
            )

        # Event checks
        if pod["events"]:

            overall_status = "WARNING"

            for event in pod["events"]:
                findings.append(
                    f"Pod {pod_name}: "
                    f"{event['reason']} - "
                    f"{event['message']}"
                )

        # Log checks
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

                break

    return {
        "overall_status": overall_status,
        "findings": findings
    }


def format_troubleshooting_report(result):

    print("=" * 55)
    print("       KUBERNETES TROUBLESHOOTING REPORT")
    print("=" * 55)

    # Argo CD
    argo = result["argocd"]

    print("\nARGO CD")
    print("-" * 55)
    print(f"Application      : {argo['application']}")
    print(f"Sync Status      : {argo['sync_status']}")
    print(f"Health Status    : {argo['health_status']}")
    print(f"Revision         : {argo['revision'][:12]}...")

    # Deployment
    deployment = result["deployment"]

    print("\nDEPLOYMENT")
    print("-" * 55)
    print(f"Deployment       : {deployment['deployment']}")
    print(f"Desired Replicas : {deployment['desired_replicas']}")
    print(f"Ready Replicas   : {deployment['ready_replicas']}")
    print(f"Available        : {deployment['available_replicas']}")

    # Pods
    print("\nPODS")
    print("-" * 55)

    for index, pod in enumerate(result["pods"], start=1):

        print(f"{index}. {pod['name']}")
        print(f"   Status         : {pod['status']}")

        events = pod["events"]

        if events:
            print(f"   Events         : {len(events)} event(s)")
        else:
            print("   Events         : None")

        logs = pod["logs"]["logs"]

        if logs:
            print("   Logs           : Available")
        else:
            print("   Logs           : Empty")

        print()

    print("=" * 55)


result = troubleshoot_application(
    application="gitops-web-app"
)

analysis = result["analysis"]

format_troubleshooting_report(result)

print("\nANALYSIS")
print("-" * 55)
print(f"Overall Status : {analysis['overall_status']}")

if analysis["findings"]:

    print("\nFindings:")

    for finding in analysis["findings"]:
        print(f"- {finding}")

else:

    print("\nFindings       : No issues detected.")
    print("=" * 55)