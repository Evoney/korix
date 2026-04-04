import unittest

from korix.dashboard import build_overview, parse_nodes, parse_pods, summarize_pod_status


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


if __name__ == "__main__":
    unittest.main()
