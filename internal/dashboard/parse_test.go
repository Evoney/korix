package dashboard

import "testing"

func TestParseServicesFlagsPendingLoadBalancer(t *testing.T) {
	rows := ParseServices(listPayload{Items: []resource{{
		Metadata: metadata{Name: "web", Namespace: "prod"},
		Spec: spec{
			Type:      "LoadBalancer",
			ClusterIP: "10.0.0.12",
			Ports: []servicePort{{
				Port:       80,
				TargetPort: float64(8080),
				Protocol:   "TCP",
			}},
		},
	}}})
	if rows[0].ExternalIP != "<pending>" {
		t.Fatalf("external ip = %q, want pending", rows[0].ExternalIP)
	}
	if rows[0].Ports != "80->8080/TCP" {
		t.Fatalf("ports = %q", rows[0].Ports)
	}
}

func TestParseIngressesFlagsMissingAddress(t *testing.T) {
	rows := ParseIngresses(listPayload{Items: []resource{{
		Metadata: metadata{Name: "edge", Namespace: "prod"},
		Spec:     spec{Rules: []ingressRule{{Host: "api.example.com"}}},
	}}})
	if rows[0].Hosts != "api.example.com" {
		t.Fatalf("hosts = %q", rows[0].Hosts)
	}
	if rows[0].Issue != "No ingress address" {
		t.Fatalf("issue = %q", rows[0].Issue)
	}
}

func TestParseStatefulSetsAndDaemonSetsSurfaceUnreadyWorkloads(t *testing.T) {
	replicas := 3
	statefulsets := ParseStatefulSets(listPayload{Items: []resource{{
		Metadata: metadata{Name: "db", Namespace: "prod"},
		Spec:     spec{Replicas: &replicas},
		Status:   status{ReadyReplicas: 2},
	}}})
	daemonsets := ParseDaemonSets(listPayload{Items: []resource{{
		Metadata: metadata{Name: "agent", Namespace: "prod"},
		Status:   status{DesiredNumberScheduled: 4, NumberReady: 3},
	}}})
	if statefulsets[0].Ready != "2/3" {
		t.Fatalf("statefulset ready = %q", statefulsets[0].Ready)
	}
	if daemonsets[0].Ready != "3/4" {
		t.Fatalf("daemonset ready = %q", daemonsets[0].Ready)
	}
}

func TestParseJobsAndCronJobsSummarizeStatus(t *testing.T) {
	completions := 1
	jobs := ParseJobs(listPayload{Items: []resource{{
		Metadata: metadata{Name: "migrate", Namespace: "prod"},
		Spec:     spec{Completions: &completions},
		Status:   status{Failed: 1},
	}}})
	cronjobs := ParseCronJobs(listPayload{Items: []resource{{
		Metadata: metadata{Name: "backup", Namespace: "prod"},
		Spec:     spec{Schedule: "*/5 * * * *", Suspend: true},
		Status:   status{Active: []namedRef{{Name: "backup-1"}}},
	}}})
	if jobs[0].Issue != "1 failed" {
		t.Fatalf("job issue = %q", jobs[0].Issue)
	}
	if cronjobs[0].Issue != "Suspended" || cronjobs[0].Active != 1 {
		t.Fatalf("cronjob = %+v", cronjobs[0])
	}
}
