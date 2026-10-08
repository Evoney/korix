package dashboard

import (
	"github.com/evoneymendonca/korix/internal/kubecommand"
	"github.com/evoneymendonca/korix/internal/kubectl"
)

type Service struct {
	kubectl kubectl.Client
}

func NewService(client kubectl.Client) Service {
	return Service{kubectl: client}
}

func (s Service) Refresh(context, namespace string, allNamespaces bool) Snapshot {
	errors := map[string]string{}
	snapshot := Snapshot{Errors: errors}

	load := func(key string, args []string, namespaced bool, target any) bool {
		cmd := kubecommand.BuildScopedCommand(args, context, namespace, allNamespaces, namespaced)
		if err := s.kubectl.GetJSON(cmd, target, "failed to load "+key); err != nil {
			errors[key] = err.Error()
			return false
		}
		return true
	}

	var pods listPayload
	if load("pods", []string{"get", "pods", "-o", "json"}, true, &pods) {
		snapshot.Pods = ParsePods(pods)
	}
	var deployments listPayload
	if load("deployments", []string{"get", "deployments", "-o", "json"}, true, &deployments) {
		snapshot.Deployments = ParseDeployments(deployments)
	}
	var services listPayload
	if load("services", []string{"get", "services", "-o", "json"}, true, &services) {
		snapshot.Services = ParseServices(services)
	}
	var ingresses listPayload
	if load("ingresses", []string{"get", "ingresses", "-o", "json"}, true, &ingresses) {
		snapshot.Ingresses = ParseIngresses(ingresses)
	}
	var statefulsets listPayload
	if load("statefulsets", []string{"get", "statefulsets", "-o", "json"}, true, &statefulsets) {
		snapshot.StatefulSets = ParseStatefulSets(statefulsets)
	}
	var daemonsets listPayload
	if load("daemonsets", []string{"get", "daemonsets", "-o", "json"}, true, &daemonsets) {
		snapshot.DaemonSets = ParseDaemonSets(daemonsets)
	}
	var jobs listPayload
	if load("jobs", []string{"get", "jobs", "-o", "json"}, true, &jobs) {
		snapshot.Jobs = ParseJobs(jobs)
	}
	var cronjobs listPayload
	if load("cronjobs", []string{"get", "cronjobs", "-o", "json"}, true, &cronjobs) {
		snapshot.CronJobs = ParseCronJobs(cronjobs)
	}
	var nodes listPayload
	if load("nodes", []string{"get", "nodes", "-o", "json"}, false, &nodes) {
		snapshot.Nodes = ParseNodes(nodes)
	}
	var events listPayload
	if load("events", []string{"get", "events", "-o", "json"}, true, &events) {
		snapshot.Events = ParseEvents(events)
	}
	var namespaces listPayload
	if load("namespaces", []string{"get", "namespaces", "-o", "json"}, false, &namespaces) {
		snapshot.Namespaces = ParseNamespaces(namespaces)
	}

	snapshot.Overview = BuildOverview(
		snapshot.Pods,
		snapshot.Deployments,
		snapshot.Nodes,
		snapshot.Events,
	)
	return snapshot
}
