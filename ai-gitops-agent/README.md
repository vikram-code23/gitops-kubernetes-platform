# AI-Powered Kubernetes & GitOps Troubleshooting Agent

A read-only AI-powered troubleshooting agent that uses **Gemini, Python, Kubernetes APIs, and Argo CD** to inspect application health, collect real cluster evidence, perform basic diagnosis, and explain troubleshooting findings in natural language.

---

## 1. Project Overview

Kubernetes applications can involve multiple layers such as:

* Argo CD / GitOps synchronization
* Kubernetes Deployments
* Pods
* Application logs
* Kubernetes events
* Services
* Service endpoints
* Ingress resources

When an application has an issue, an engineer may need to inspect several of these resources manually.

This project was created to explore how an **AI agent can assist with this troubleshooting process**.

The agent collects real Kubernetes and Argo CD information through Python tools and provides the collected evidence to Gemini for human-readable analysis.

The agent is intentionally **read-only**. It does not modify the Kubernetes cluster or automatically remediate problems.

---

## 2. Project Goal

The primary goal of this project is:

> **To build a read-only AI troubleshooting agent that can inspect a Kubernetes/GitOps application, collect evidence from multiple infrastructure layers, identify potential problems using deterministic analysis, and explain the findings using an LLM.**

The project demonstrates how AI can be integrated with real infrastructure tools instead of relying only on static text or simulated information.

---

## 3. Why Build an AI Agent?

Traditional troubleshooting often requires an engineer to manually execute multiple commands:

```text
Check Argo CD
      ↓
Check Deployment
      ↓
Check Pods
      ↓
Check Events
      ↓
Check Logs
      ↓
Check Service
      ↓
Check Endpoints
      ↓
Check Ingress
```

This project explores whether the same investigation can be orchestrated through an AI agent.

Instead of expecting the LLM to directly know the Kubernetes state, the agent gives the LLM access to tools.

The LLM decides which tool is required, while Python executes the tool and retrieves real cluster information.

This separation helps keep infrastructure information grounded in actual Kubernetes data.

---

## 4. High-Level Architecture

```text
                         USER
                           |
                           v
                    +-------------+
                    |   Gemini    |
                    |     LLM     |
                    +------+------+
                           |
                     Function Call
                           |
                           v
                +----------------------+
                |    Python Agent      |
                |                      |
                |  Tool Registry       |
                |  Diagnosis Engine    |
                +----------+-----------+
                           |
          +----------------+----------------+
          |                |                |
          v                v                v
    Kubernetes API      Argo CD API    Analysis Logic
          |                |                |
          +----------------+----------------+
                           |
                           v
                    Real Cluster Data
                           |
                           v
                    Evidence Analysis
                           |
                           v
                       Gemini
                           |
                           v
                 Human-readable Answer
```

---

## 5. Kubernetes Traffic Architecture

The application traffic path investigated by the agent is:

```text
Client
  |
  v
Ingress Controller
  |
  v
Ingress Resource
gitops-web-ingress
  |
  v
Service
gitops-web-service
  |
  v
Ready Endpoints
  |
  v
Application Pods
```

The agent distinguishes between the:

* Ingress resource
* Ingress controller
* Kubernetes Service
* Service endpoints
* Application Pods

This prevents treating an Ingress Controller's status as the same thing as application health.

---

## 6. Technology Stack

| Technology               | Purpose                                    |
| ------------------------ | ------------------------------------------ |
| Python                   | Agent implementation and orchestration     |
| Gemini                   | Natural-language reasoning and explanation |
| Google GenAI SDK         | Communication with Gemini                  |
| Kubernetes Python Client | Kubernetes API interaction                 |
| Argo CD                  | GitOps application management              |
| Kubernetes               | Application runtime environment            |
| Kind                     | Local Kubernetes cluster                   |
| Nginx                    | Sample application workload                |
| PowerShell               | Local development environment              |

---

## 7. Main Components

### 7.1 Python AI Agent

The Python application acts as the orchestration layer.

It:

1. Receives the user's question.
2. Sends the request to Gemini.
3. Provides Gemini with available tools.
4. Receives a function call from Gemini.
5. Executes the selected Python function.
6. Retrieves real Kubernetes/Argo CD data.
7. Sends the tool result back to Gemini.
8. Returns the final explanation to the user.

---

### 7.2 Kubernetes Tools

The agent implements tools for inspecting different Kubernetes resources.

#### Pod inspection

Retrieves:

* Pod name
* Namespace
* Pod phase/status

#### Deployment inspection

Retrieves:

* Desired replicas
* Ready replicas
* Available replicas

#### Pod logs

Retrieves application logs from a specific Pod.

#### Pod events

Retrieves Kubernetes events associated with a Pod.

These events can expose issues such as:

* FailedScheduling
* FailedMount
* BackOff
* Unhealthy
* Evicted
* OOM-related events

---

### 7.3 Argo CD Inspection

The agent communicates with the Kubernetes API to inspect the Argo CD Application custom resource.

It retrieves:

* Application name
* Sync status
* Health status
* Deployed revision

This allows the agent to distinguish GitOps synchronization problems from Kubernetes runtime problems.

---

### 7.4 Service Inspection

The Service tool retrieves:

* Service name
* Namespace
* Service type
* Cluster IP
* Ports
* Target ports
* Protocol

A Service does not have a simple `Running` state like a Pod.

Therefore, the agent also checks the Service's ready endpoints.

---

### 7.5 Service Endpoint Inspection

The endpoint tool identifies the backend addresses associated with the Service.

For example:

```text
Service
   |
   +-- Endpoint 1
   +-- Endpoint 2
   +-- Endpoint 3
```

This helps determine whether the Service has healthy backend targets.

---

### 7.6 Ingress Inspection

The Ingress tool retrieves:

* Ingress name
* Namespace
* Host rules
* Paths
* Backend Service
* Backend port

This allows the agent to verify whether an Ingress routes traffic to the expected Service.

---

## 8. Diagnosis Engine

The project does not depend entirely on the LLM to determine infrastructure state.

A Python diagnosis engine performs deterministic checks against the collected evidence.

The engine evaluates:

```text
1. Argo CD
2. Deployment
3. Pods
4. Kubernetes events
5. Application logs
6. Service
7. Service endpoints
8. Ingress
```

The result contains:

```text
Overall status
Findings
Affected resources
Likely causes
Recommended next steps
```

This analysis result is then available to Gemini for natural-language explanation.

---

## 9. Why Use a Diagnosis Engine?

An LLM can explain information well, but infrastructure state should come from actual tools.

Therefore, the project separates:

```text
Infrastructure Evidence
        |
        v
Deterministic Analysis
        |
        v
AI Explanation
```

This design reduces the chance of the LLM inventing Kubernetes state.

The system prompt also instructs Gemini to treat tool results as the source of truth.

---

## 10. Function Calling Flow

The agent uses Gemini function calling.

Example:

```text
User:
"Troubleshoot gitops-web-app"

        |
        v

Gemini decides:
troubleshoot_application()

        |
        v

Python executes the function

        |
        v

Kubernetes + Argo CD APIs

        |
        v

Real cluster evidence

        |
        v

Diagnosis engine

        |
        v

Evidence returned to Gemini

        |
        v

Gemini explains the result
```

Gemini does not directly execute Python functions.

The Python agent receives the function call, executes the appropriate function, and sends the result back to Gemini.

---

## 11. Troubleshooting Scenarios Tested

The project was tested using both synthetic failure scenarios and the real Kubernetes environment.

### Scenario 1 — Deployment / Pod readiness issue

The diagnosis engine was tested against an application where desired replicas and ready replicas did not match.

The agent identified the workload as unhealthy and reported the affected resources.

### Scenario 2 — CrashLoopBackOff

A Pod repeatedly failing to start was simulated.

The agent detected the runtime problem and recommended inspecting the container logs and previous container logs.

### Scenario 3 — Application log error

Error-related messages were introduced into simulated application logs.

The diagnosis engine detected the error keywords and identified the affected Pod.

### Scenario 4 — FailedScheduling

A Kubernetes `FailedScheduling` event was simulated.

The agent identified that Kubernetes could not find a suitable node and recommended checking scheduling events and node resource availability.

### Scenario 5 — Argo CD OutOfSync

An Argo CD application with an `OutOfSync` state was simulated.

The agent identified the GitOps synchronization problem separately from Kubernetes runtime health.

### Scenario 6 — Service with zero ready endpoints

The Service existed, but the Service had:

```text
Ready endpoints: 0
```

The agent correctly produced:

```text
WARNING
```

and identified:

```text
Service gitops-web-service has no ready endpoints.
```

This demonstrated that a healthy Deployment or Argo CD state alone does not guarantee that application traffic can reach healthy backends.

### Scenario 7 — Ingress points to the wrong Service

The Ingress was intentionally configured in the test data to point to an unexpected Service.

The agent detected the mismatch:

```text
Ingress gitops-web-ingress routes path /
to unexpected Service wrong-service.
```

This validated the relationship check between the Ingress and Service.

---

## 12. Real Cluster Validation

The agent was also tested against the actual local Kubernetes environment.

The real application returned:

```text
Argo CD:
Synced / Healthy

Deployment:
3 desired
3 ready
3 available

Pods:
3 Running

Service:
gitops-web-service

Ready endpoints:
3
```
