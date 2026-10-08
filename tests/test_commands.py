import unittest

from korix.actions import exec_pod, port_forward_resource, rollout_history, rollout_undo
from korix.commands import build_kubectl_command, is_mutating_command, validate_translated_args


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

    def test_is_mutating_command_detects_rollout_undo(self):
        self.assertTrue(is_mutating_command(["rollout", "undo", "deployment", "api"]))

    def test_validate_translated_args_rejects_shell_control(self):
        with self.assertRaises(ValueError):
            validate_translated_args(["get", "pods", ";", "delete", "pod", "api"])

    def test_action_builders_for_rollout_and_preview_commands(self):
        self.assertEqual(
            rollout_history("deployment", "api").args,
            ["rollout", "history", "deployment", "api"],
        )
        undo = rollout_undo("deployment", "api")
        self.assertTrue(undo.requires_confirmation)
        self.assertEqual(undo.args, ["rollout", "undo", "deployment", "api"])

        port_forward = port_forward_resource("service", "web", "8080:80")
        self.assertTrue(port_forward.preview_only)
        self.assertEqual(port_forward.args, ["port-forward", "service/web", "8080:80"])

        exec_action = exec_pod("api", ["sh"])
        self.assertTrue(exec_action.preview_only)
        self.assertEqual(exec_action.args, ["exec", "-it", "api", "--", "sh"])


if __name__ == "__main__":
    unittest.main()
