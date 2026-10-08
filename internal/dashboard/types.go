package dashboard

type OverviewMetric struct {
	Label  string
	Value  int
	Status string
}

type PodRow struct {
	Namespace string
	Name      string
	Status    string
	Ready     string
	Restarts  int
	Node      string
	Age       string
	Issue     string
}

type DeploymentRow struct {
	Namespace string
	Name      string
	Ready     string
	Available int
	Age       string
	Issue     string
}

type ServiceRow struct {
	Namespace  string
	Name       string
	Type       string
	ClusterIP  string
	ExternalIP string
	Ports      string
	Age        string
	Issue      string
}

type IngressRow struct {
	Namespace string
	Name      string
	ClassName string
	Hosts     string
	Address   string
	Age       string
	Issue     string
}

type WorkloadRow struct {
	Namespace string
	Name      string
	Kind      string
	Ready     string
	Desired   int
	Age       string
	Issue     string
}

type JobRow struct {
	Namespace   string
	Name        string
	Completions string
	Succeeded   int
	Failed      int
	Duration    string
	Age         string
	Issue       string
}

type CronJobRow struct {
	Namespace    string
	Name         string
	Schedule     string
	Suspend      bool
	Active       int
	LastSchedule string
	Age          string
	Issue        string
}

type NodeRow struct {
	Name   string
	Status string
	Roles  string
	Age    string
	Issue  string
}

type EventRow struct {
	Namespace string
	Type      string
	Reason    string
	Object    string
	Age       string
	Message   string
}

type Snapshot struct {
	Overview     []OverviewMetric
	Pods         []PodRow
	Deployments  []DeploymentRow
	Services     []ServiceRow
	Ingresses    []IngressRow
	StatefulSets []WorkloadRow
	DaemonSets   []WorkloadRow
	Jobs         []JobRow
	CronJobs     []CronJobRow
	Nodes        []NodeRow
	Events       []EventRow
	Namespaces   []string
	Errors       map[string]string
}
