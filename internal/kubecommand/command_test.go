package kubecommand

import "testing"

func TestBuildKubectlCommandInjectsContextAndNamespace(t *testing.T) {
	got := BuildKubectlCommand([]string{"get", "pods"}, "prod", "payments", false)
	want := []string{"kubectl", "--context", "prod", "--namespace", "payments", "get", "pods"}
	if !equal(got, want) {
		t.Fatalf("command = %v, want %v", got, want)
	}
}

func TestBuildKubectlCommandRespectsExistingNamespaceFlags(t *testing.T) {
	got := BuildKubectlCommand([]string{"get", "pods", "-n", "observability"}, "prod", "payments", false)
	want := []string{"kubectl", "--context", "prod", "get", "pods", "-n", "observability"}
	if !equal(got, want) {
		t.Fatalf("command = %v, want %v", got, want)
	}
}

func TestBuildKubectlCommandAddsAllNamespaces(t *testing.T) {
	got := BuildKubectlCommand([]string{"get", "pods"}, "prod", "payments", true)
	want := []string{"kubectl", "--context", "prod", "-A", "get", "pods"}
	if !equal(got, want) {
		t.Fatalf("command = %v, want %v", got, want)
	}
}

func TestIsMutatingCommandDetectsRolloutUndo(t *testing.T) {
	if !IsMutatingCommand([]string{"rollout", "undo", "deployment", "api"}) {
		t.Fatal("rollout undo should be mutating")
	}
	if IsMutatingCommand([]string{"get", "pods"}) {
		t.Fatal("get pods should not be mutating")
	}
}

func TestValidateTranslatedArgsRejectsShellControl(t *testing.T) {
	if err := ValidateTranslatedArgs([]string{"get", "pods", ";", "delete", "pod", "api"}); err == nil {
		t.Fatal("expected shell control validation error")
	}
}

func equal(a, b []string) bool {
	if len(a) != len(b) {
		return false
	}
	for index := range a {
		if a[index] != b[index] {
			return false
		}
	}
	return true
}
