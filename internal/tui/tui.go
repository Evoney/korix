package tui

import (
	"fmt"
	"strconv"
	"strings"

	"github.com/gdamore/tcell/v2"
	"github.com/rivo/tview"

	"github.com/evoneymendonca/korix/internal/actions"
	"github.com/evoneymendonca/korix/internal/constants"
	"github.com/evoneymendonca/korix/internal/dashboard"
	"github.com/evoneymendonca/korix/internal/kubecommand"
	"github.com/evoneymendonca/korix/internal/kubectl"
	"github.com/evoneymendonca/korix/internal/llm"
	"github.com/evoneymendonca/korix/internal/translation"
)

var sectionOrder = []string{
	"Overview",
	"Pods",
	"Deployments",
	"Services",
	"Ingresses",
	"StatefulSets",
	"DaemonSets",
	"Jobs",
	"CronJobs",
	"Nodes",
	"Events",
	"Namespaces",
	"LLM",
	"History",
	"Actions",
}

type state struct {
	app           *tview.Application
	sections      *tview.List
	items         *tview.List
	detail        *tview.TextView
	status        *tview.TextView
	kubectl       kubectl.Client
	dashboard     dashboard.Service
	snapshot      dashboard.Snapshot
	contexts      []string
	context       string
	namespace     string
	allNamespaces bool
	llmConfig     llm.Config
	translator    *translation.Translator
	llmError      string
	history       []string
}

func Run() error {
	client := kubectl.New()
	config, err := llm.LoadConfigFromEnv()
	if err != nil {
		config = llm.Config{Provider: "cli", BinPath: "llm", TimeoutSeconds: 60}
	}
	s := &state{
		app:       tview.NewApplication(),
		sections:  tview.NewList().ShowSecondaryText(false),
		items:     tview.NewList().ShowSecondaryText(false),
		detail:    tview.NewTextView().SetDynamicColors(true).SetWrap(true),
		status:    tview.NewTextView().SetDynamicColors(true),
		kubectl:   client,
		dashboard: dashboard.NewService(client),
		namespace: constants.DefaultNamespace,
		llmConfig: config,
	}
	s.initialize()
	s.configureLayout()
	return s.app.Run()
}

func (s *state) initialize() {
	if err := s.kubectl.EnsureInstalled(); err != nil {
		s.setStatus("[red]" + err.Error())
		return
	}
	contexts, err := s.kubectl.Contexts()
	if err != nil {
		s.setStatus("[red]" + err.Error())
		return
	}
	s.contexts = contexts
	s.context = s.kubectl.CurrentContext()
	if s.context == "" {
		s.context = contexts[0]
	}
	s.configureTranslator()
	s.refresh()
}

func (s *state) configureLayout() {
	s.sections.SetBorder(true).SetTitle("Sections")
	s.items.SetBorder(true).SetTitle("Items")
	s.detail.SetBorder(true).SetTitle("Inspector")
	s.status.SetBorder(true).SetTitle("Status")

	for _, section := range sectionOrder {
		section := section
		s.sections.AddItem(section, "", 0, func() {
			s.renderItems()
		})
	}
	s.sections.SetChangedFunc(func(index int, mainText, secondaryText string, shortcut rune) {
		s.renderItems()
	})
	s.items.SetChangedFunc(func(index int, mainText, secondaryText string, shortcut rune) {
		s.renderDetail()
	})

	body := tview.NewFlex().
		AddItem(s.sections, 24, 0, true).
		AddItem(tview.NewFlex().
			SetDirection(tview.FlexRow).
			AddItem(s.items, 0, 2, false).
			AddItem(s.detail, 0, 1, false), 0, 1, false)

	root := tview.NewFlex().
		SetDirection(tview.FlexRow).
		AddItem(body, 0, 1, true).
		AddItem(s.status, 3, 0, false)

	s.app.SetRoot(root, true)
	s.app.SetInputCapture(s.handleKey)
	s.renderItems()
}

func (s *state) handleKey(event *tcell.EventKey) *tcell.EventKey {
	switch event.Rune() {
	case 'q', 'Q':
		s.app.Stop()
		return nil
	case 'g', 'G':
		s.refresh()
		return nil
	case 'd':
		s.describeSelected()
		return nil
	case 'l':
		s.logsSelected(false)
		return nil
	case 'p':
		s.logsSelected(true)
		return nil
	case 'x':
		s.deleteSelectedPod()
		return nil
	case 'r':
		s.restartSelectedWorkload()
		return nil
	case 's':
		s.scaleSelectedDeployment()
		return nil
	case 'o':
		s.rolloutSelected(actions.RolloutStatus)
		return nil
	case 'h':
		s.rolloutSelected(actions.RolloutHistory)
		return nil
	case 'u':
		if s.currentSection() == "Nodes" {
			s.uncordonSelectedNode()
		} else {
			s.rolloutSelected(actions.RolloutUndo)
		}
		return nil
	case 'c':
		s.cordonSelectedNode()
		return nil
	case 'f':
		s.portForwardSelected()
		return nil
	case 'e':
		s.execSelectedPod()
		return nil
	case ':':
		s.promptNaturalLanguage()
		return nil
	}
	return event
}

func (s *state) refresh() {
	if s.context == "" {
		return
	}
	s.snapshot = s.dashboard.Refresh(s.context, s.namespace, s.allNamespaces)
	s.renderItems()
	s.setStatus(fmt.Sprintf(
		"refreshed context=%s namespace=%s errors=%d",
		s.context,
		s.namespaceLabel(),
		len(s.snapshot.Errors),
	))
}

func (s *state) configureTranslator() {
	provider, err := llm.BuildProvider(s.llmConfig)
	if err != nil {
		s.llmError = err.Error()
		s.translator = nil
		return
	}
	s.llmError = ""
	s.translator = &translation.Translator{Provider: provider}
}

func (s *state) renderItems() {
	section := s.currentSection()
	s.items.Clear()
	for _, label := range s.labelsForSection(section) {
		s.items.AddItem(label, "", 0, nil)
	}
	s.items.SetTitle(fmt.Sprintf("%s (%d)", section, s.items.GetItemCount()))
	s.renderDetail()
}

func (s *state) renderDetail() {
	s.detail.SetText(s.detailForSelection())
}

func (s *state) labelsForSection(section string) []string {
	labels := []string{}
	switch section {
	case "Overview":
		for _, metric := range s.snapshot.Overview {
			labels = append(labels, fmt.Sprintf("%-20s %3d [%s]", metric.Label, metric.Value, metric.Status))
		}
	case "Pods":
		for _, pod := range s.snapshot.Pods {
			labels = append(labels, fmt.Sprintf("%s | %s | ready %s | restarts %d", scopedName(pod.Namespace, pod.Name, s.allNamespaces), pod.Status, pod.Ready, pod.Restarts))
		}
	case "Deployments":
		for _, deployment := range s.snapshot.Deployments {
			labels = append(labels, fmt.Sprintf("%s | ready %s | %s", scopedName(deployment.Namespace, deployment.Name, s.allNamespaces), deployment.Ready, deployment.Issue))
		}
	case "Services":
		for _, service := range s.snapshot.Services {
			labels = append(labels, fmt.Sprintf("%s | %s | %s | %s", scopedName(service.Namespace, service.Name, s.allNamespaces), service.Type, service.ExternalIP, service.Ports))
		}
	case "Ingresses":
		for _, ingress := range s.snapshot.Ingresses {
			labels = append(labels, fmt.Sprintf("%s | %s | %s | %s", scopedName(ingress.Namespace, ingress.Name, s.allNamespaces), ingress.Hosts, ingress.Address, ingress.Issue))
		}
	case "StatefulSets":
		for _, workload := range s.snapshot.StatefulSets {
			labels = append(labels, workloadLabel(workload, s.allNamespaces))
		}
	case "DaemonSets":
		for _, workload := range s.snapshot.DaemonSets {
			labels = append(labels, workloadLabel(workload, s.allNamespaces))
		}
	case "Jobs":
		for _, job := range s.snapshot.Jobs {
			labels = append(labels, fmt.Sprintf("%s | complete %s | failed %d | %s", scopedName(job.Namespace, job.Name, s.allNamespaces), job.Completions, job.Failed, job.Issue))
		}
	case "CronJobs":
		for _, cronjob := range s.snapshot.CronJobs {
			labels = append(labels, fmt.Sprintf("%s | %s | active %d | %s", scopedName(cronjob.Namespace, cronjob.Name, s.allNamespaces), cronjob.Schedule, cronjob.Active, cronjob.Issue))
		}
	case "Nodes":
		for _, node := range s.snapshot.Nodes {
			labels = append(labels, fmt.Sprintf("%s | %s | %s | %s", node.Name, node.Status, node.Roles, node.Issue))
		}
	case "Events":
		for _, event := range s.snapshot.Events {
			labels = append(labels, fmt.Sprintf("%s | %s | %s", event.Type, event.Reason, scopedName(event.Namespace, event.Object, s.allNamespaces)))
		}
	case "Namespaces":
		labels = append(labels, "* all namespaces", "- no default namespace")
		labels = append(labels, s.snapshot.Namespaces...)
	case "LLM":
		status := "ready"
		if s.translator == nil {
			status = "unavailable: " + s.llmError
		}
		labels = append(labels, "Provider "+s.llmConfig.Provider, "Model "+dash(s.llmConfig.Model), "Status "+status)
	case "History":
		if len(s.history) == 0 {
			labels = append(labels, "No commands yet")
		} else {
			labels = append(labels, s.history...)
		}
	default:
		labels = append(labels,
			"g refresh data",
			": natural-language command preview",
			"Pods: d describe, l logs, p previous logs, e exec preview, f port-forward preview, x delete pod",
			"Deployments: d describe, r restart, s scale, o status, h history, u undo",
			"Services: d describe, f port-forward preview",
			"StatefulSets/DaemonSets: d describe, r restart, o status, h history, u undo",
			"Nodes: d describe, c cordon, u uncordon",
			"q quit",
		)
	}
	if len(labels) == 0 {
		if message, ok := s.snapshot.Errors[strings.ToLower(section)]; ok {
			return []string{message}
		}
		return []string{"No data for " + section}
	}
	return labels
}

func (s *state) detailForSelection() string {
	section := s.currentSection()
	index := s.items.GetCurrentItem()
	switch section {
	case "Overview":
		if index < len(s.snapshot.Overview) {
			metric := s.snapshot.Overview[index]
			return fmt.Sprintf("%s: %d\nStatus: %s", metric.Label, metric.Value, metric.Status)
		}
	case "Pods":
		if index < len(s.snapshot.Pods) {
			pod := s.snapshot.Pods[index]
			return fmt.Sprintf("Pod: %s/%s\nStatus: %s\nReady: %s\nRestarts: %d\nNode: %s\nAge: %s\nIssue: %s\n\nKeys: d describe | l logs | p previous logs | e exec preview | f port-forward preview | x delete", pod.Namespace, pod.Name, pod.Status, pod.Ready, pod.Restarts, pod.Node, pod.Age, pod.Issue)
		}
	case "Deployments":
		if index < len(s.snapshot.Deployments) {
			row := s.snapshot.Deployments[index]
			return fmt.Sprintf("Deployment: %s/%s\nReady: %s\nAvailable: %d\nAge: %s\nIssue: %s\n\nKeys: d describe | r restart | s scale | o status | h history | u undo", row.Namespace, row.Name, row.Ready, row.Available, row.Age, row.Issue)
		}
	case "Services":
		if index < len(s.snapshot.Services) {
			row := s.snapshot.Services[index]
			return fmt.Sprintf("Service: %s/%s\nType: %s\nCluster IP: %s\nExternal IP: %s\nPorts: %s\nAge: %s\nIssue: %s\n\nKeys: d describe | f port-forward preview", row.Namespace, row.Name, row.Type, row.ClusterIP, row.ExternalIP, row.Ports, row.Age, row.Issue)
		}
	case "Ingresses":
		if index < len(s.snapshot.Ingresses) {
			row := s.snapshot.Ingresses[index]
			return fmt.Sprintf("Ingress: %s/%s\nClass: %s\nHosts: %s\nAddress: %s\nAge: %s\nIssue: %s\n\nKeys: d describe", row.Namespace, row.Name, row.ClassName, row.Hosts, row.Address, row.Age, row.Issue)
		}
	case "StatefulSets":
		return workloadDetail(index, s.snapshot.StatefulSets)
	case "DaemonSets":
		return workloadDetail(index, s.snapshot.DaemonSets)
	case "Jobs":
		if index < len(s.snapshot.Jobs) {
			row := s.snapshot.Jobs[index]
			return fmt.Sprintf("Job: %s/%s\nCompletions: %s\nSucceeded: %d\nFailed: %d\nDuration: %s\nAge: %s\nIssue: %s\n\nKeys: d describe", row.Namespace, row.Name, row.Completions, row.Succeeded, row.Failed, row.Duration, row.Age, row.Issue)
		}
	case "CronJobs":
		if index < len(s.snapshot.CronJobs) {
			row := s.snapshot.CronJobs[index]
			return fmt.Sprintf("CronJob: %s/%s\nSchedule: %s\nSuspended: %t\nActive jobs: %d\nLast schedule: %s\nAge: %s\nIssue: %s\n\nKeys: d describe", row.Namespace, row.Name, row.Schedule, row.Suspend, row.Active, row.LastSchedule, row.Age, row.Issue)
		}
	case "Nodes":
		if index < len(s.snapshot.Nodes) {
			row := s.snapshot.Nodes[index]
			return fmt.Sprintf("Node: %s\nStatus: %s\nRoles: %s\nAge: %s\nIssue: %s\n\nKeys: d describe | c cordon | u uncordon", row.Name, row.Status, row.Roles, row.Age, row.Issue)
		}
	case "Events":
		if index < len(s.snapshot.Events) {
			row := s.snapshot.Events[index]
			return fmt.Sprintf("Event: %s %s\nObject: %s/%s\nAge: %s\n\n%s", row.Type, row.Reason, row.Namespace, row.Object, row.Age, row.Message)
		}
	case "Namespaces":
		return "Press Enter in the Python TUI to switch scope. Scope switching is pending in the Go port."
	case "LLM", "History", "Actions":
		if index < s.items.GetItemCount() {
			text, _ := s.items.GetItemText(index)
			return text
		}
	}
	return "No data for " + section
}

func (s *state) describeSelected() {
	kind, name, namespaced := s.selectedResource()
	if kind == "" || name == "" {
		return
	}
	s.execute(actions.DescribeResource(kind, name, namespaced), "")
}

func (s *state) logsSelected(previous bool) {
	pod := s.selectedPod()
	if pod.Name == "" {
		return
	}
	s.execute(actions.LogsPod(pod.Name, previous), "")
}

func (s *state) deleteSelectedPod() {
	pod := s.selectedPod()
	if pod.Name == "" {
		return
	}
	s.execute(actions.DeletePod(pod.Name), "")
}

func (s *state) restartSelectedWorkload() {
	kind, name := s.selectedRolloutResource()
	if kind == "" {
		return
	}
	s.execute(actions.RolloutRestart(kind, name), "")
}

func (s *state) rolloutSelected(builder func(string, string) actions.Spec) {
	kind, name := s.selectedRolloutResource()
	if kind == "" {
		return
	}
	s.execute(builder(kind, name), "")
}

func (s *state) scaleSelectedDeployment() {
	row := s.selectedDeployment()
	if row.Name == "" {
		return
	}
	s.prompt("Target replicas", strings.Split(row.Ready, "/")[1], func(value string) {
		replicas, err := strconv.Atoi(value)
		if err != nil {
			s.setStatus("[red]invalid replica count: " + value)
			return
		}
		s.execute(actions.ScaleDeployment(row.Name, replicas), "")
	})
}

func (s *state) cordonSelectedNode() {
	node := s.selectedNode()
	if node.Name != "" {
		s.execute(actions.CordonNode(node.Name), "")
	}
}

func (s *state) uncordonSelectedNode() {
	node := s.selectedNode()
	if node.Name != "" {
		s.execute(actions.UncordonNode(node.Name), "")
	}
}

func (s *state) portForwardSelected() {
	kind, name, _ := s.selectedResource()
	if kind != "pod" && kind != "service" {
		return
	}
	def := "8080:8080"
	if kind == "service" {
		def = "8080:80"
	}
	s.prompt("Local:remote port", def, func(value string) {
		spec, err := actions.PortForwardResource(kind, name, value)
		if err != nil {
			s.setStatus("[red]" + err.Error())
			return
		}
		s.execute(spec, "")
	})
}

func (s *state) execSelectedPod() {
	pod := s.selectedPod()
	if pod.Name == "" {
		return
	}
	s.prompt("Exec command", "sh", func(value string) {
		command := strings.Fields(value)
		spec, err := actions.ExecPod(pod.Name, command)
		if err != nil {
			s.setStatus("[red]" + err.Error())
			return
		}
		s.execute(spec, "")
	})
}

func (s *state) promptNaturalLanguage() {
	if s.translator == nil {
		s.setStatus("[red]natural-language translation is unavailable")
		return
	}
	s.prompt("Ask Korix", "", func(value string) {
		spec, err := s.translator.Translate(value)
		if err != nil {
			s.detail.SetText(err.Error())
			s.setStatus("[red]translation failed")
			return
		}
		s.execute(actions.FromTranslatedCommand(spec.Args, kubecommand.IsMutatingCommand(spec.Args)), value)
	})
}

func (s *state) execute(action actions.Spec, source string) {
	var cmd []string
	switch action.Scope {
	case actions.ScopeCluster:
		cmd = kubecommand.BuildScopedCommand(action.Args, s.context, s.namespace, s.allNamespaces, false)
	case actions.ScopeNamespaced:
		cmd = kubecommand.BuildScopedCommand(action.Args, s.context, s.namespace, s.allNamespaces, true)
	default:
		cmd = kubecommand.BuildKubectlCommand(action.Args, s.context, s.namespace, s.allNamespaces)
	}
	commandText := kubecommand.RenderCommand(cmd)
	s.remember(commandText, source)
	if action.PreviewOnly {
		s.detail.SetText("$ " + commandText + "\n\nPreview only. Run this command in a separate terminal if needed.")
		s.setStatus("command preview ready: " + action.Label)
		return
	}
	if action.RequiresConfirmation {
		s.confirm("Run "+commandText+"?", func(ok bool) {
			if ok {
				s.runCommand(cmd, action)
			}
		})
		return
	}
	s.runCommand(cmd, action)
}

func (s *state) runCommand(cmd []string, action actions.Spec) {
	result, err := s.kubectl.Run(cmd)
	chunks := []string{"$ " + kubecommand.RenderCommand(cmd), ""}
	if err != nil {
		chunks = append(chunks, err.Error())
		s.detail.SetText(strings.Join(chunks, "\n"))
		s.setStatus("[red]command failed: " + action.Label)
		return
	}
	if result.Stdout != "" {
		chunks = append(chunks, result.Stdout)
	}
	if result.Stderr != "" {
		chunks = append(chunks, "", result.Stderr)
	}
	if result.ExitCode != 0 {
		chunks = append(chunks, "", fmt.Sprintf("Command exited with status %d.", result.ExitCode))
		s.setStatus("[red]command failed: " + action.Label)
	} else {
		s.setStatus("command completed: " + action.Label)
	}
	s.detail.SetText(strings.Join(chunks, "\n"))
	if result.ExitCode == 0 && action.RequiresConfirmation {
		s.refresh()
	}
}

func (s *state) prompt(label, defaultValue string, done func(string)) {
	input := tview.NewInputField().SetLabel(label + ": ").SetText(defaultValue)
	input.SetDoneFunc(func(key tcell.Key) {
		value := input.GetText()
		s.app.SetRoot(s.root(), true)
		if key == tcell.KeyEnter {
			done(value)
		}
	})
	frame := tview.NewFrame(input).SetBorders(1, 1, 1, 1, 2, 2)
	s.app.SetRoot(frame, true).SetFocus(input)
}

func (s *state) confirm(label string, done func(bool)) {
	modal := tview.NewModal().
		SetText(label).
		AddButtons([]string{"Cancel", "Run"}).
		SetDoneFunc(func(index int, buttonLabel string) {
			s.app.SetRoot(s.root(), true)
			done(buttonLabel == "Run")
		})
	s.app.SetRoot(modal, false).SetFocus(modal)
}

func (s *state) root() tview.Primitive {
	body := tview.NewFlex().
		AddItem(s.sections, 24, 0, true).
		AddItem(tview.NewFlex().
			SetDirection(tview.FlexRow).
			AddItem(s.items, 0, 2, false).
			AddItem(s.detail, 0, 1, false), 0, 1, false)
	return tview.NewFlex().
		SetDirection(tview.FlexRow).
		AddItem(body, 0, 1, true).
		AddItem(s.status, 3, 0, false)
}

func (s *state) currentSection() string {
	index := s.sections.GetCurrentItem()
	if index < 0 || index >= len(sectionOrder) {
		return "Overview"
	}
	return sectionOrder[index]
}

func (s *state) selectedResource() (string, string, bool) {
	index := s.items.GetCurrentItem()
	switch s.currentSection() {
	case "Pods":
		if index < len(s.snapshot.Pods) {
			return "pod", s.snapshot.Pods[index].Name, true
		}
	case "Deployments":
		if index < len(s.snapshot.Deployments) {
			return "deployment", s.snapshot.Deployments[index].Name, true
		}
	case "Services":
		if index < len(s.snapshot.Services) {
			return "service", s.snapshot.Services[index].Name, true
		}
	case "Ingresses":
		if index < len(s.snapshot.Ingresses) {
			return "ingress", s.snapshot.Ingresses[index].Name, true
		}
	case "StatefulSets":
		if index < len(s.snapshot.StatefulSets) {
			return "statefulset", s.snapshot.StatefulSets[index].Name, true
		}
	case "DaemonSets":
		if index < len(s.snapshot.DaemonSets) {
			return "daemonset", s.snapshot.DaemonSets[index].Name, true
		}
	case "Jobs":
		if index < len(s.snapshot.Jobs) {
			return "job", s.snapshot.Jobs[index].Name, true
		}
	case "CronJobs":
		if index < len(s.snapshot.CronJobs) {
			return "cronjob", s.snapshot.CronJobs[index].Name, true
		}
	case "Nodes":
		if index < len(s.snapshot.Nodes) {
			return "node", s.snapshot.Nodes[index].Name, false
		}
	}
	return "", "", true
}

func (s *state) selectedRolloutResource() (string, string) {
	index := s.items.GetCurrentItem()
	switch s.currentSection() {
	case "Deployments":
		if index < len(s.snapshot.Deployments) {
			return "deployment", s.snapshot.Deployments[index].Name
		}
	case "StatefulSets":
		if index < len(s.snapshot.StatefulSets) {
			return "statefulset", s.snapshot.StatefulSets[index].Name
		}
	case "DaemonSets":
		if index < len(s.snapshot.DaemonSets) {
			return "daemonset", s.snapshot.DaemonSets[index].Name
		}
	}
	return "", ""
}

func (s *state) selectedPod() dashboard.PodRow {
	index := s.items.GetCurrentItem()
	if s.currentSection() == "Pods" && index < len(s.snapshot.Pods) {
		return s.snapshot.Pods[index]
	}
	return dashboard.PodRow{}
}

func (s *state) selectedDeployment() dashboard.DeploymentRow {
	index := s.items.GetCurrentItem()
	if s.currentSection() == "Deployments" && index < len(s.snapshot.Deployments) {
		return s.snapshot.Deployments[index]
	}
	return dashboard.DeploymentRow{}
}

func (s *state) selectedNode() dashboard.NodeRow {
	index := s.items.GetCurrentItem()
	if s.currentSection() == "Nodes" && index < len(s.snapshot.Nodes) {
		return s.snapshot.Nodes[index]
	}
	return dashboard.NodeRow{}
}

func (s *state) namespaceLabel() string {
	if s.allNamespaces {
		return "*"
	}
	if s.namespace == "" {
		return "-"
	}
	return s.namespace
}

func (s *state) remember(commandText, source string) {
	entry := commandText
	if source != "" {
		entry = source + " -> " + commandText
	}
	s.history = append([]string{entry}, s.history...)
	if len(s.history) > 25 {
		s.history = s.history[:25]
	}
}

func (s *state) setStatus(text string) {
	s.status.SetText(text)
}

func scopedName(namespace, name string, allNamespaces bool) string {
	if allNamespaces {
		return namespace + "/" + name
	}
	return name
}

func workloadLabel(row dashboard.WorkloadRow, allNamespaces bool) string {
	return fmt.Sprintf("%s | ready %s | %s", scopedName(row.Namespace, row.Name, allNamespaces), row.Ready, row.Issue)
}

func workloadDetail(index int, rows []dashboard.WorkloadRow) string {
	if index >= len(rows) {
		return ""
	}
	row := rows[index]
	return fmt.Sprintf("%s: %s/%s\nReady: %s\nDesired: %d\nAge: %s\nIssue: %s\n\nKeys: d describe | r restart | o rollout status | h history | u undo", strings.Title(row.Kind), row.Namespace, row.Name, row.Ready, row.Desired, row.Age, row.Issue)
}

func dash(value string) string {
	if value == "" {
		return "-"
	}
	return value
}
