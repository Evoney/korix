import unittest

from korix.dashboard import (
    build_overview,
    parse_cronjobs,
    parse_daemonsets,
    parse_ingresses,
    parse_jobs,
    parse_nodes,
    parse_pods,
    parse_services,
    parse_statefulsets,
    summarize_pod_status,
)


class DashboardTest(unittest.TestCase):
    def test_summarize_pod_status_prefers_waiting_reason(self):
        status, issue = summarize_pod_status(
            {
                "metadata": {"name": "api", "namespace": "prod"},
                "status": {
                    "phase": "Running",
                    "containerStatuses": [
                        {
                            "ready": False,
                            "restartCount": 4,
                            "state": {
                                "waiting": {
                                    "reason": "CrashLoopBackOff",
                                    "message": "Back-off restarting failed container",
                                }
                            },
                        }
                    ],
                },
            }
        )
        self.assertEqual(status, "CrashLoopBackOff")
        self.assertIn("Back-off", issue)

    def test_parse_pods_surfaces_unhealthy_rows_first(self):
        rows = parse_pods(
            {
                "items": [
                    {
                        "metadata": {
                            "name": "healthy",
                            "namespace": "default",
                            "creationTimestamp": "2026-04-02T00:00:00Z",
                        },
                        "spec": {"nodeName": "node-a"},
                        "status": {
                            "phase": "Running",
                            "containerStatuses": [{"ready": True, "restartCount": 0, "state": {}}],
                        },
                    },
                    {
                        "metadata": {
                            "name": "broken",
                            "namespace": "default",
                            "creationTimestamp": "2026-04-02T00:00:00Z",
                        },
                        "spec": {"nodeName": "node-b"},
                        "status": {
                            "phase": "Pending",
                            "containerStatuses": [],
                        },
                    },
                ]
            }
        )
        self.assertEqual(rows[0].name, "broken")
        self.assertEqual(rows[0].issue, "Pending")

    def test_parse_nodes_detects_not_ready_state(self):
        rows = parse_nodes(
            {
                "items": [
                    {
                        "metadata": {
                            "name": "worker-a",
                            "creationTimestamp": "2026-04-02T00:00:00Z",
                            "labels": {"node-role.kubernetes.io/worker": ""},
                        },
                        "status": {
                            "conditions": [
                                {
                                    "type": "Ready",
                                    "status": "False",
                                    "message": "Kubelet stopped posting node status.",
                                }
                            ]
                        },
                    }
                ]
            }
        )
        self.assertEqual(rows[0].status, "NotReady")
        self.assertIn("Kubelet", rows[0].issue)

    def test_build_overview_counts_problem_resources(self):
        pods = parse_pods(
            {
                "items": [
                    {
                        "metadata": {
                            "name": "broken",
                            "namespace": "default",
                            "creationTimestamp": "2026-04-02T00:00:00Z",
                        },
                        "spec": {"nodeName": "node-a"},
                        "status": {"phase": "Pending", "containerStatuses": []},
                    }
                ]
            }
        )
        nodes = parse_nodes(
            {
                "items": [
                    {
                        "metadata": {
                            "name": "worker-a",
                            "creationTimestamp": "2026-04-02T00:00:00Z",
                            "labels": {},
                        },
                        "status": {"conditions": [{"type": "Ready", "status": "True"}]},
                    }
                ]
            }
        )
        overview = build_overview(pods, [], nodes, [])
        self.assertEqual(overview[0].value, 1)
        self.assertEqual(overview[2].value, 0)

    def test_parse_services_flags_pending_load_balancer(self):
        rows = parse_services(
            {
                "items": [
                    {
                        "metadata": {"name": "web", "namespace": "prod"},
                        "spec": {
                            "type": "LoadBalancer",
                            "clusterIP": "10.0.0.12",
                            "ports": [{"port": 80, "targetPort": 8080, "protocol": "TCP"}],
                        },
                        "status": {"loadBalancer": {}},
                    }
                ]
            }
        )
        self.assertEqual(rows[0].external_ip, "<pending>")
        self.assertIn("pending", rows[0].issue.lower())
        self.assertEqual(rows[0].ports, "80->8080/TCP")

    def test_parse_ingresses_flags_missing_address(self):
        rows = parse_ingresses(
            {
                "items": [
                    {
                        "metadata": {"name": "edge", "namespace": "prod"},
                        "spec": {"rules": [{"host": "api.example.com"}]},
                        "status": {"loadBalancer": {}},
                    }
                ]
            }
        )
        self.assertEqual(rows[0].hosts, "api.example.com")
        self.assertEqual(rows[0].issue, "No ingress address")

    def test_parse_statefulsets_and_daemonsets_surface_unready_workloads(self):
        statefulsets = parse_statefulsets(
            {
                "items": [
                    {
                        "metadata": {"name": "db", "namespace": "prod"},
                        "spec": {"replicas": 3},
                        "status": {"readyReplicas": 2},
                    }
                ]
            }
        )
        daemonsets = parse_daemonsets(
            {
                "items": [
                    {
                        "metadata": {"name": "agent", "namespace": "prod"},
                        "status": {"desiredNumberScheduled": 4, "numberReady": 3},
                    }
                ]
            }
        )
        self.assertEqual(statefulsets[0].ready, "2/3")
        self.assertIn("Ready", statefulsets[0].issue)
        self.assertEqual(daemonsets[0].ready, "3/4")
        self.assertIn("below desired", daemonsets[0].issue)

    def test_parse_jobs_and_cronjobs_summarize_status(self):
        jobs = parse_jobs(
            {
                "items": [
                    {
                        "metadata": {"name": "migrate", "namespace": "prod"},
                        "spec": {"completions": 1},
                        "status": {"failed": 1, "succeeded": 0},
                    }
                ]
            }
        )
        cronjobs = parse_cronjobs(
            {
                "items": [
                    {
                        "metadata": {"name": "backup", "namespace": "prod"},
                        "spec": {"schedule": "*/5 * * * *", "suspend": True},
                        "status": {"active": [{"name": "backup-1"}]},
                    }
                ]
            }
        )
        self.assertEqual(jobs[0].issue, "1 failed")
        self.assertEqual(cronjobs[0].schedule, "*/5 * * * *")
        self.assertEqual(cronjobs[0].active, 1)
        self.assertEqual(cronjobs[0].issue, "Suspended")


if __name__ == "__main__":
    unittest.main()
