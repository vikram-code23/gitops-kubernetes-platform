from agent import analyze_troubleshooting_result

scenario = {
    "argocd": {
        "application": "gitops-web-app",
        "sync_status": "Synced",
        "health_status": "Healthy",
        "revision": "test-revision"
    },

    "deployment": {
        "deployment": "gitops-web",
        "namespace": "gitops-web",
        "desired_replicas": 3,
        "ready_replicas": 2,
        "available_replicas": 2
    },

    "pods": [
        {
            "name": "gitops-web-running-1",
            "status": "Running",
            "logs": {
                "pod": "gitops-web-running-1",
                "namespace": "gitops-web",
                "logs": "nginx started successfully"
            },
            "events": []
        },

        {
            "name": "gitops-web-running-2",
            "status": "Running",
            "logs": {
                "pod": "gitops-web-running-2",
                "namespace": "gitops-web",
                "logs": "nginx started successfully"
            },
            "events": []
        },

        {
            "name": "gitops-web-pending-1",
            "status": "Pending",
            "logs": {
                "pod": "gitops-web-pending-1",
                "namespace": "gitops-web",
                "logs": ""
            },
            "events": [
                {
                    "reason": "FailedScheduling",
                    "message": (
                        "0/1 nodes are available: "
                        "insufficient cpu."
                    ),
                    "type": "Warning"
                }
            ]
        }
    ]
}

analysis = analyze_troubleshooting_result(
    scenario
)


print("=" * 60)
print("       SYNTHETIC DIAGNOSIS TEST")
print("=" * 60)

print("\nOVERALL STATUS")
print("-" * 60)
print(analysis["overall_status"])

print("\nFINDINGS")
print("-" * 60)

for finding in analysis["findings"]:
    print("-", finding)

print("\nAFFECTED RESOURCES")
print("-" * 60)

for resource in analysis["affected_resources"]:
    print("-", resource)

print("\nLIKELY CAUSES")
print("-" * 60)

for cause in analysis["likely_causes"]:
    print("-", cause)

print("\nRECOMMENDED NEXT STEPS")
print("-" * 60)

for step in analysis["recommended_next_steps"]:
    print("-", step)