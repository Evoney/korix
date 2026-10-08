package actions

import "testing"

func TestRolloutAndPreviewActionBuilders(t *testing.T) {
	history := RolloutHistory("deployment", "api")
	if got, want := history.Args, []string{"rollout", "history", "deployment", "api"}; !equal(got, want) {
		t.Fatalf("history args = %v, want %v", got, want)
	}

	undo := RolloutUndo("deployment", "api")
	if !undo.RequiresConfirmation {
		t.Fatal("rollout undo should require confirmation")
	}

	portForward, err := PortForwardResource("service", "web", "8080:80")
	if err != nil {
		t.Fatal(err)
	}
	if !portForward.PreviewOnly {
		t.Fatal("port-forward should be preview-only")
	}
	if got, want := portForward.Args, []string{"port-forward", "service/web", "8080:80"}; !equal(got, want) {
		t.Fatalf("port-forward args = %v, want %v", got, want)
	}

	execAction, err := ExecPod("api", []string{"sh"})
	if err != nil {
		t.Fatal(err)
	}
	if !execAction.PreviewOnly {
		t.Fatal("exec should be preview-only")
	}
	if got, want := execAction.Args, []string{"exec", "-it", "api", "--", "sh"}; !equal(got, want) {
		t.Fatalf("exec args = %v, want %v", got, want)
	}
}

func TestPortForwardRejectsInvalidMapping(t *testing.T) {
	if _, err := PortForwardResource("service", "web", "not-a-port"); err == nil {
		t.Fatal("expected invalid port-forward mapping to fail")
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
