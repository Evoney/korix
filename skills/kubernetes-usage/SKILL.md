---
name: kubernetes-usage
description: Kubernetes usage and troubleshooting expertise. Use when the user needs kubectl commands, resource inspection (pods, nodes, services, deployments, events), logs/exec access, debugging cluster issues, or guidance on Kubernetes operational tasks.
---

# Kubernetes Usage

## Overview

Provide accurate, safe kubectl commands and troubleshooting guidance for Kubernetes. Ask for the minimum context needed (namespace, kube context/cluster, resource name) and prefer non-destructive inspection steps before suggesting changes.

## Quick Start Commands

- **List pods**: `kubectl get pods`
- **List pods all namespaces**: `kubectl get pods -A`
- **Get events**: `kubectl get events` (add `-A` if needed)
- **Describe a pod**: `kubectl describe pod <name> -n <ns>`
- **Pod logs**: `kubectl logs <pod> -n <ns>` (add `-f` to follow)
- **Exec into a pod**: `kubectl exec -it <pod> -n <ns> -- <cmd>`
- **List namespaces**: `kubectl get namespaces`
- **List contexts**: `kubectl config get-contexts`

## Troubleshooting Workflow

1. **Clarify scope**
   - Ask for namespace, context/cluster, and resource type/name if missing.
   - Ask for Kubernetes version if behavior might differ.
2. **Collect facts (safe commands first)**
   - `kubectl get <resource> -n <ns> -o wide`
   - `kubectl describe <resource>/<name> -n <ns>`
   - `kubectl get events -n <ns> --sort-by=.lastTimestamp`
   - `kubectl logs <pod> -n <ns>` (add `-f` if requested)
3. **Identify the symptom class**
   - Pending: check resources/taints/affinity and node capacity
   - CrashLoopBackOff: review logs, probes, and restart events
   - ImagePullBackOff: verify image name, registry access, secrets
   - Service unreachable: confirm selector, endpoints, ports
4. **Propose fixes carefully**
   - Explain impact, ask for confirmation before destructive actions.

## Safety and Confirmation

Require explicit user confirmation before suggesting or executing destructive commands such as:
`apply`, `create`, `delete`, `replace`, `patch`, `scale`, `rollout restart`, or `drain`.

## Output Style

Prefer concise commands first, then a short explanation. When multiple steps are needed, present them in order and ask for missing context instead of guessing.

## Examples of Triggering Requests

- "list pods"
- "get events from cluster"
- "why is my pod in CrashLoopBackOff"
- "show logs for payment-api in prod namespace"
- "exec into a pod and check /etc/resolv.conf"
