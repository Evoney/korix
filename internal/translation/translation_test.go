package translation

import "testing"

func TestExtractKubectlLine(t *testing.T) {
	got := ExtractKubectlLine("Here you go:\n`kubectl get pods -A`\n")
	if got != "kubectl get pods -A" {
		t.Fatalf("line = %q", got)
	}
}

func TestSplitCommandLineHandlesQuotes(t *testing.T) {
	got, err := splitCommandLine(`kubectl get pods -n "observability stack"`)
	if err != nil {
		t.Fatal(err)
	}
	want := []string{"kubectl", "get", "pods", "-n", "observability stack"}
	if !equal(got, want) {
		t.Fatalf("args = %v, want %v", got, want)
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
