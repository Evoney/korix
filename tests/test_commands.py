import unittest

from korix.commands import build_kubectl_command, is_mutating_command


class CommandsTest(unittest.TestCase):
    def test_build_kubectl_command_injects_context_and_namespace(self):
        self.assertEqual(
            build_kubectl_command(["get", "pods"], "prod", "payments", False),
            ["kubectl", "--context", "prod", "--namespace", "payments", "get", "pods"],
        )

    def test_build_kubectl_command_respects_existing_namespace_flags(self):
        self.assertEqual(
            build_kubectl_command(
                ["get", "pods", "-n", "observability"], "prod", "payments", False
            ),
            ["kubectl", "--context", "prod", "get", "pods", "-n", "observability"],
        )

    def test_build_kubectl_command_adds_all_namespaces(self):
        self.assertEqual(
            build_kubectl_command(["get", "pods"], "prod", "payments", True),
            ["kubectl", "--context", "prod", "-A", "get", "pods"],
        )

    def test_is_mutating_command_detects_rollout_restart(self):
        self.assertTrue(is_mutating_command(["rollout", "restart", "deployment", "api"]))
        self.assertFalse(is_mutating_command(["get", "pods"]))


if __name__ == "__main__":
    unittest.main()
