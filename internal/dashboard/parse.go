package dashboard

import (
	"fmt"
	"sort"
	"strings"
	"time"
)

type listPayload struct {
	Items []resource `json:"items"`
}

type resource struct {
	Metadata metadata `json:"metadata"`
	Spec     spec     `json:"spec"`
	Status   status   `json:"status"`
	Note     string   `json:"note"`
	Message  string   `json:"message"`
	Reason   string   `json:"reason"`
	Type     string   `json:"type"`
}

type metadata struct {
	Name              string            `json:"name"`
	Namespace         string            `json:"namespace"`
	CreationTimestamp string            `json:"creationTimestamp"`
	DeletionTimestamp string            `json:"deletionTimestamp"`
	Labels            map[string]string `json:"labels"`
}

type spec struct {
	NodeName         string        `json:"nodeName"`
	Replicas         *int          `json:"replicas"`
	Type             string        `json:"type"`
	ClusterIP        string        `json:"clusterIP"`
	ExternalIPs      []string      `json:"externalIPs"`
	Ports            []servicePort `json:"ports"`
	IngressClassName string        `json:"ingressClassName"`
	Rules            []ingressRule `json:"rules"`
	Completions      *int          `json:"completions"`
	Schedule         string        `json:"schedule"`
	Suspend          bool          `json:"suspend"`
}

type status struct {
	Phase                  string            `json:"phase"`
	Message                string            `json:"message"`
	ContainerStatuses      []containerStatus `json:"containerStatuses"`
	ReadyReplicas          int               `json:"readyReplicas"`
	AvailableReplicas      int               `json:"availableReplicas"`
	DesiredNumberScheduled int               `json:"desiredNumberScheduled"`
	NumberReady            int               `json:"numberReady"`
	NumberAvailable        int               `json:"numberAvailable"`
	Succeeded              int               `json:"succeeded"`
	Failed                 int               `json:"failed"`
	Conditions             []condition       `json:"conditions"`
	LoadBalancer           loadBalancer      `json:"loadBalancer"`
	StartTime              string            `json:"startTime"`
	CompletionTime         string            `json:"completionTime"`
	Active                 []namedRef        `json:"active"`
	LastScheduleTime       string            `json:"lastScheduleTime"`
	Regarding              objectRef         `json:"regarding"`
	InvolvedObject         objectRef         `json:"involvedObject"`
	EventTime              string            `json:"eventTime"`
	LastTimestamp          string            `json:"lastTimestamp"`
	FirstTimestamp         string            `json:"firstTimestamp"`
}

type containerStatus struct {
	Ready        bool           `json:"ready"`
	RestartCount int            `json:"restartCount"`
	State        containerState `json:"state"`
}

type containerState struct {
	Waiting    stateReason `json:"waiting"`
	Terminated stateReason `json:"terminated"`
}

type stateReason struct {
	Reason  string `json:"reason"`
	Message string `json:"message"`
}

type condition struct {
	Type    string `json:"type"`
	Status  string `json:"status"`
	Reason  string `json:"reason"`
	Message string `json:"message"`
}

type servicePort struct {
	Port       int    `json:"port"`
	TargetPort any    `json:"targetPort"`
	NodePort   int    `json:"nodePort"`
	Protocol   string `json:"protocol"`
}

type loadBalancer struct {
	Ingress []loadBalancerIngress `json:"ingress"`
}

type loadBalancerIngress struct {
	IP       string `json:"ip"`
	Hostname string `json:"hostname"`
}

type ingressRule struct {
	Host string `json:"host"`
}

type objectRef struct {
	Kind      string `json:"kind"`
	Name      string `json:"name"`
	Namespace string `json:"namespace"`
}

type namedRef struct {
	Name string `json:"name"`
}

func ParsePods(payload listPayload) []PodRow {
	rows := make([]PodRow, 0, len(payload.Items))
	for _, item := range payload.Items {
		restarts := 0
		ready := 0
		for _, container := range item.Status.ContainerStatuses {
			restarts += container.RestartCount
			if container.Ready {
				ready++
			}
		}
		podStatus, issue := summarizePodStatus(item)
		rows = append(rows, PodRow{
			Namespace: namespaceOrDefault(item.Metadata.Namespace),
			Name:      item.Metadata.Name,
			Status:    podStatus,
			Ready:     fmt.Sprintf("%d/%d", ready, len(item.Status.ContainerStatuses)),
			Restarts:  restarts,
			Node:      dashIfEmpty(item.Spec.NodeName),
			Age:       FormatAge(item.Metadata.CreationTimestamp),
			Issue:     issue,
		})
	}
	sort.Slice(rows, func(i, j int) bool {
		return podSortKey(rows[i]) < podSortKey(rows[j])
	})
	return rows
}

func ParseDeployments(payload listPayload) []DeploymentRow {
	rows := make([]DeploymentRow, 0, len(payload.Items))
	for _, item := range payload.Items {
		desired := derefInt(item.Spec.Replicas)
		ready := item.Status.ReadyReplicas
		issue := "Healthy"
		if ready < desired {
			issue = "Ready replicas below desired"
		} else if item.Status.AvailableReplicas < desired {
			issue = "Available replicas below desired"
		}
		rows = append(rows, DeploymentRow{
			Namespace: namespaceOrDefault(item.Metadata.Namespace),
			Name:      item.Metadata.Name,
			Ready:     fmt.Sprintf("%d/%d", ready, desired),
			Available: item.Status.AvailableReplicas,
			Age:       FormatAge(item.Metadata.CreationTimestamp),
			Issue:     issue,
		})
	}
	sort.Slice(rows, func(i, j int) bool {
		return healthySort(rows[i].Issue, rows[j].Issue, rows[i].Namespace, rows[j].Namespace, rows[i].Name, rows[j].Name)
	})
	return rows
}

func ParseServices(payload listPayload) []ServiceRow {
	rows := make([]ServiceRow, 0, len(payload.Items))
	for _, item := range payload.Items {
		serviceType := item.Spec.Type
		if serviceType == "" {
			serviceType = "ClusterIP"
		}
		externalIP := serviceExternalIP(item.Spec, item.Status)
		issue := "Healthy"
		if serviceType == "LoadBalancer" && externalIP == "<pending>" {
			issue = "LoadBalancer external IP pending"
		}
		rows = append(rows, ServiceRow{
			Namespace:  namespaceOrDefault(item.Metadata.Namespace),
			Name:       item.Metadata.Name,
			Type:       serviceType,
			ClusterIP:  dashIfEmpty(item.Spec.ClusterIP),
			ExternalIP: externalIP,
			Ports:      formatServicePorts(item.Spec.Ports),
			Age:        FormatAge(item.Metadata.CreationTimestamp),
			Issue:      issue,
		})
	}
	sort.Slice(rows, func(i, j int) bool {
		return healthySort(rows[i].Issue, rows[j].Issue, rows[i].Namespace, rows[j].Namespace, rows[i].Name, rows[j].Name)
	})
	return rows
}

func ParseIngresses(payload listPayload) []IngressRow {
	rows := make([]IngressRow, 0, len(payload.Items))
	for _, item := range payload.Items {
		hosts := ingressHosts(item.Spec)
		address := ingressAddress(item.Status)
		issue := "Healthy"
		if hosts == "-" {
			issue = "No host rules"
		} else if address == "-" {
			issue = "No ingress address"
		}
		rows = append(rows, IngressRow{
			Namespace: namespaceOrDefault(item.Metadata.Namespace),
			Name:      item.Metadata.Name,
			ClassName: dashIfEmpty(item.Spec.IngressClassName),
			Hosts:     hosts,
			Address:   address,
			Age:       FormatAge(item.Metadata.CreationTimestamp),
			Issue:     issue,
		})
	}
	sort.Slice(rows, func(i, j int) bool {
		return healthySort(rows[i].Issue, rows[j].Issue, rows[i].Namespace, rows[j].Namespace, rows[i].Name, rows[j].Name)
	})
	return rows
}

func ParseStatefulSets(payload listPayload) []WorkloadRow {
	return parseReplicaWorkload(payload, "statefulset")
}

func ParseDaemonSets(payload listPayload) []WorkloadRow {
	rows := make([]WorkloadRow, 0, len(payload.Items))
	for _, item := range payload.Items {
		desired := item.Status.DesiredNumberScheduled
		ready := item.Status.NumberReady
		available := item.Status.NumberAvailable
		if available == 0 {
			available = ready
		}
		issue := "Healthy"
		if ready < desired {
			issue = "Ready pods below desired"
		} else if available < desired {
			issue = "Available pods below desired"
		}
		rows = append(rows, WorkloadRow{
			Namespace: namespaceOrDefault(item.Metadata.Namespace),
			Name:      item.Metadata.Name,
			Kind:      "daemonset",
			Ready:     fmt.Sprintf("%d/%d", ready, desired),
			Desired:   desired,
			Age:       FormatAge(item.Metadata.CreationTimestamp),
			Issue:     issue,
		})
	}
	sortWorkloads(rows)
	return rows
}

func ParseJobs(payload listPayload) []JobRow {
	rows := make([]JobRow, 0, len(payload.Items))
	for _, item := range payload.Items {
		desired := derefIntDefault(item.Spec.Completions, 1)
		issue := summarizeJobIssue(item.Status, desired)
		rows = append(rows, JobRow{
			Namespace:   namespaceOrDefault(item.Metadata.Namespace),
			Name:        item.Metadata.Name,
			Completions: fmt.Sprintf("%d/%d", item.Status.Succeeded, desired),
			Succeeded:   item.Status.Succeeded,
			Failed:      item.Status.Failed,
			Duration:    jobDuration(item.Status),
			Age:         FormatAge(item.Metadata.CreationTimestamp),
			Issue:       issue,
		})
	}
	sort.Slice(rows, func(i, j int) bool {
		if (rows[i].Issue == "Complete") != (rows[j].Issue == "Complete") {
			return rows[i].Issue != "Complete"
		}
		if rows[i].Namespace != rows[j].Namespace {
			return rows[i].Namespace < rows[j].Namespace
		}
		return rows[i].Name < rows[j].Name
	})
	return rows
}

func ParseCronJobs(payload listPayload) []CronJobRow {
	rows := make([]CronJobRow, 0, len(payload.Items))
	for _, item := range payload.Items {
		issue := "Healthy"
		if item.Spec.Suspend {
			issue = "Suspended"
		}
		rows = append(rows, CronJobRow{
			Namespace:    namespaceOrDefault(item.Metadata.Namespace),
			Name:         item.Metadata.Name,
			Schedule:     dashIfEmpty(item.Spec.Schedule),
			Suspend:      item.Spec.Suspend,
			Active:       len(item.Status.Active),
			LastSchedule: FormatAge(item.Status.LastScheduleTime),
			Age:          FormatAge(item.Metadata.CreationTimestamp),
			Issue:        issue,
		})
	}
	sort.Slice(rows, func(i, j int) bool {
		return healthySort(rows[i].Issue, rows[j].Issue, rows[i].Namespace, rows[j].Namespace, rows[i].Name, rows[j].Name)
	})
	return rows
}

func ParseNodes(payload listPayload) []NodeRow {
	rows := make([]NodeRow, 0, len(payload.Items))
	for _, item := range payload.Items {
		nodeStatus, issue := summarizeNode(item)
		rows = append(rows, NodeRow{
			Name:   item.Metadata.Name,
			Status: nodeStatus,
			Roles:  extractNodeRoles(item.Metadata.Labels),
			Age:    FormatAge(item.Metadata.CreationTimestamp),
			Issue:  issue,
		})
	}
	sort.Slice(rows, func(i, j int) bool {
		if (rows[i].Status == "Ready") != (rows[j].Status == "Ready") {
			return rows[i].Status != "Ready"
		}
		return rows[i].Name < rows[j].Name
	})
	return rows
}

func ParseEvents(payload listPayload) []EventRow {
	rows := make([]EventRow, 0, len(payload.Items))
	for _, item := range payload.Items {
		regarding := item.Status.Regarding
		if regarding.Name == "" {
			regarding = item.Status.InvolvedObject
		}
		namespace := item.Metadata.Namespace
		if namespace == "" {
			namespace = regarding.Namespace
		}
		object := strings.Trim(regarding.Kind+"/"+regarding.Name, "/")
		timestamp := firstNonEmpty(
			item.Status.EventTime,
			item.Metadata.CreationTimestamp,
			item.Status.LastTimestamp,
			item.Status.FirstTimestamp,
		)
		eventType := item.Type
		if eventType == "" {
			eventType = "Normal"
		}
		rows = append(rows, EventRow{
			Namespace: dashIfEmpty(namespace),
			Type:      eventType,
			Reason:    item.Reason,
			Object:    dashIfEmpty(object),
			Age:       FormatAge(timestamp),
			Message:   firstNonEmpty(item.Note, item.Message),
		})
	}
	sort.Slice(rows, func(i, j int) bool {
		if (rows[i].Type == "Warning") != (rows[j].Type == "Warning") {
			return rows[i].Type == "Warning"
		}
		if rows[i].Age != rows[j].Age {
			return rows[i].Age < rows[j].Age
		}
		return rows[i].Reason < rows[j].Reason
	})
	if len(rows) > 100 {
		return rows[:100]
	}
	return rows
}

func ParseNamespaces(payload listPayload) []string {
	namespaces := make([]string, 0, len(payload.Items))
	for _, item := range payload.Items {
		if item.Metadata.Name != "" {
			namespaces = append(namespaces, item.Metadata.Name)
		}
	}
	sort.Strings(namespaces)
	return namespaces
}

func BuildOverview(
	pods []PodRow,
	deployments []DeploymentRow,
	nodes []NodeRow,
	events []EventRow,
) []OverviewMetric {
	unhealthyPods := 0
	for _, pod := range pods {
		if pod.Issue != "Healthy" {
			unhealthyPods++
		}
	}
	failingDeployments := 0
	for _, deployment := range deployments {
		if deployment.Issue != "Healthy" {
			failingDeployments++
		}
	}
	notReadyNodes := 0
	for _, node := range nodes {
		if node.Status != "Ready" {
			notReadyNodes++
		}
	}
	warningEvents := 0
	for _, event := range events {
		if event.Type == "Warning" {
			warningEvents++
		}
	}
	return []OverviewMetric{
		{Label: "Unhealthy pods", Value: unhealthyPods, Status: severity(unhealthyPods)},
		{Label: "Deployments at risk", Value: failingDeployments, Status: severity(failingDeployments)},
		{Label: "Not ready nodes", Value: notReadyNodes, Status: severity(notReadyNodes)},
		{Label: "Warning events", Value: warningEvents, Status: severity(warningEvents)},
	}
}

func FormatAge(value string) string {
	if value == "" {
		return "-"
	}
	dt, err := time.Parse(time.RFC3339, value)
	if err != nil {
		return "-"
	}
	delta := time.Since(dt)
	if delta < time.Minute {
		return fmt.Sprintf("%ds", int(delta.Seconds()))
	}
	if delta < time.Hour {
		return fmt.Sprintf("%dm", int(delta.Minutes()))
	}
	if delta < 24*time.Hour {
		return fmt.Sprintf("%dh", int(delta.Hours()))
	}
	return fmt.Sprintf("%dd", int(delta.Hours()/24))
}

func summarizePodStatus(item resource) (string, string) {
	if item.Metadata.DeletionTimestamp != "" {
		return "Terminating", "Resource is being deleted"
	}
	for _, container := range item.Status.ContainerStatuses {
		if container.State.Waiting.Reason != "" {
			return container.State.Waiting.Reason, firstNonEmpty(container.State.Waiting.Message, container.State.Waiting.Reason)
		}
		if container.State.Terminated.Reason != "" {
			return container.State.Terminated.Reason, firstNonEmpty(container.State.Terminated.Message, container.State.Terminated.Reason)
		}
	}
	phase := firstNonEmpty(item.Status.Phase, "Unknown")
	if phase == "Running" {
		ready := 0
		for _, container := range item.Status.ContainerStatuses {
			if container.Ready {
				ready++
			}
		}
		total := len(item.Status.ContainerStatuses)
		if total > 0 && ready != total {
			return "NotReady", "One or more containers are not ready"
		}
		restarts := 0
		for _, container := range item.Status.ContainerStatuses {
			restarts += container.RestartCount
		}
		if restarts > 0 {
			return "Running", "Containers restarted recently"
		}
		return "Running", "Healthy"
	}
	if phase == "Succeeded" {
		return phase, "Completed"
	}
	return phase, firstNonEmpty(item.Status.Message, phase)
}

func parseReplicaWorkload(payload listPayload, kind string) []WorkloadRow {
	rows := make([]WorkloadRow, 0, len(payload.Items))
	for _, item := range payload.Items {
		desired := derefInt(item.Spec.Replicas)
		ready := item.Status.ReadyReplicas
		issue := "Healthy"
		if ready < desired {
			issue = "Ready replicas below desired"
		}
		rows = append(rows, WorkloadRow{
			Namespace: namespaceOrDefault(item.Metadata.Namespace),
			Name:      item.Metadata.Name,
			Kind:      kind,
			Ready:     fmt.Sprintf("%d/%d", ready, desired),
			Desired:   desired,
			Age:       FormatAge(item.Metadata.CreationTimestamp),
			Issue:     issue,
		})
	}
	sortWorkloads(rows)
	return rows
}

func summarizeNode(item resource) (string, string) {
	readyStatus := "Unknown"
	issues := []string{}
	for _, condition := range item.Status.Conditions {
		switch {
		case condition.Type == "Ready":
			if condition.Status == "True" {
				readyStatus = "Ready"
			} else {
				readyStatus = "NotReady"
				issues = append(issues, firstNonEmpty(condition.Message, "Node is not ready"))
			}
		case condition.Status == "True" &&
			(condition.Type == "DiskPressure" ||
				condition.Type == "MemoryPressure" ||
				condition.Type == "PIDPressure"):
			issues = append(issues, condition.Type)
		}
	}
	if len(issues) == 0 {
		return readyStatus, "Healthy"
	}
	return readyStatus, strings.Join(issues, ", ")
}

func serviceExternalIP(spec spec, status status) string {
	if len(spec.ExternalIPs) > 0 {
		return strings.Join(spec.ExternalIPs, ",")
	}
	addresses := loadBalancerAddresses(status)
	if len(addresses) > 0 {
		return strings.Join(addresses, ",")
	}
	if spec.Type == "LoadBalancer" {
		return "<pending>"
	}
	return "-"
}

func formatServicePorts(ports []servicePort) string {
	if len(ports) == 0 {
		return "-"
	}
	rendered := make([]string, 0, len(ports))
	for _, port := range ports {
		protocol := firstNonEmpty(port.Protocol, "TCP")
		text := fmt.Sprintf("%d", port.Port)
		if port.NodePort != 0 {
			text += fmt.Sprintf(":%d", port.NodePort)
		}
		target := fmt.Sprintf("%v", port.TargetPort)
		if target != "<nil>" && target != "" && target != fmt.Sprintf("%d", port.Port) {
			text += "->" + target
		}
		rendered = append(rendered, text+"/"+protocol)
	}
	return strings.Join(rendered, ",")
}

func ingressHosts(spec spec) string {
	hosts := []string{}
	for _, rule := range spec.Rules {
		if rule.Host != "" {
			hosts = append(hosts, rule.Host)
		}
	}
	if len(hosts) == 0 {
		return "-"
	}
	return strings.Join(hosts, ",")
}

func ingressAddress(status status) string {
	addresses := loadBalancerAddresses(status)
	if len(addresses) == 0 {
		return "-"
	}
	return strings.Join(addresses, ",")
}

func loadBalancerAddresses(status status) []string {
	addresses := []string{}
	for _, ingress := range status.LoadBalancer.Ingress {
		value := firstNonEmpty(ingress.IP, ingress.Hostname)
		if value != "" {
			addresses = append(addresses, value)
		}
	}
	return addresses
}

func summarizeJobIssue(status status, desired int) string {
	for _, condition := range status.Conditions {
		if condition.Type == "Failed" && condition.Status == "True" {
			return firstNonEmpty(condition.Reason, condition.Message, "Failed")
		}
		if condition.Type == "Complete" && condition.Status == "True" {
			return "Complete"
		}
	}
	if status.Failed > 0 {
		return fmt.Sprintf("%d failed", status.Failed)
	}
	if status.Succeeded >= desired {
		return "Complete"
	}
	return "Running"
}

func jobDuration(status status) string {
	if status.StartTime == "" {
		return "-"
	}
	start, err := time.Parse(time.RFC3339, status.StartTime)
	if err != nil {
		return "-"
	}
	end := time.Now()
	if status.CompletionTime != "" {
		if parsed, err := time.Parse(time.RFC3339, status.CompletionTime); err == nil {
			end = parsed
		}
	}
	delta := end.Sub(start)
	if delta < time.Minute {
		return fmt.Sprintf("%ds", int(delta.Seconds()))
	}
	if delta < time.Hour {
		return fmt.Sprintf("%dm", int(delta.Minutes()))
	}
	return fmt.Sprintf("%dh", int(delta.Hours()))
}

func extractNodeRoles(labels map[string]string) string {
	roles := []string{}
	for label := range labels {
		if strings.HasPrefix(label, "node-role.kubernetes.io/") {
			role := strings.TrimPrefix(label, "node-role.kubernetes.io/")
			if role == "" {
				role = "worker"
			}
			roles = append(roles, role)
		}
	}
	if len(roles) == 0 {
		return "worker"
	}
	sort.Strings(roles)
	return strings.Join(compactUnique(roles), ",")
}

func severity(count int) string {
	if count > 0 {
		return "warning"
	}
	return "ok"
}

func podSortKey(row PodRow) string {
	unhealthy := "1"
	if row.Issue != "Healthy" {
		unhealthy = "0"
	}
	warning := "1"
	switch row.Status {
	case "CrashLoopBackOff", "ImagePullBackOff", "ErrImagePull", "Failed":
		warning = "0"
	}
	return unhealthy + "|" + warning + "|" + row.Namespace + "|" + row.Name
}

func healthySort(issueA, issueB, namespaceA, namespaceB, nameA, nameB string) bool {
	if (issueA == "Healthy") != (issueB == "Healthy") {
		return issueA != "Healthy"
	}
	if namespaceA != namespaceB {
		return namespaceA < namespaceB
	}
	return nameA < nameB
}

func sortWorkloads(rows []WorkloadRow) {
	sort.Slice(rows, func(i, j int) bool {
		return healthySort(rows[i].Issue, rows[j].Issue, rows[i].Namespace, rows[j].Namespace, rows[i].Name, rows[j].Name)
	})
}

func namespaceOrDefault(value string) string {
	if value == "" {
		return "default"
	}
	return value
}

func dashIfEmpty(value string) string {
	if value == "" {
		return "-"
	}
	return value
}

func firstNonEmpty(values ...string) string {
	for _, value := range values {
		if value != "" {
			return value
		}
	}
	return ""
}

func derefInt(value *int) int {
	if value == nil {
		return 0
	}
	return *value
}

func derefIntDefault(value *int, fallback int) int {
	if value == nil {
		return fallback
	}
	return *value
}

func compactUnique(values []string) []string {
	if len(values) == 0 {
		return values
	}
	out := []string{values[0]}
	for _, value := range values[1:] {
		if value != out[len(out)-1] {
			out = append(out, value)
		}
	}
	return out
}
