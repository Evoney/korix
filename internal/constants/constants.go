package constants

const DefaultNamespace = "default"

var ContextFlags = map[string]struct{}{
	"--context": {},
}

var NamespaceFlags = map[string]struct{}{
	"-n":          {},
	"--namespace": {},
}

var AllNamespaceFlags = map[string]struct{}{
	"-A":               {},
	"--all-namespaces": {},
}

var BuiltinCommands = map[string]struct{}{
	"annotate":      {},
	"api-resources": {},
	"api-versions":  {},
	"apply":         {},
	"attach":        {},
	"auth":          {},
	"autoscale":     {},
	"cluster-info":  {},
	"completion":    {},
	"config":        {},
	"cordon":        {},
	"cp":            {},
	"create":        {},
	"debug":         {},
	"delete":        {},
	"describe":      {},
	"diff":          {},
	"drain":         {},
	"edit":          {},
	"exec":          {},
	"explain":       {},
	"expose":        {},
	"get":           {},
	"kustomize":     {},
	"label":         {},
	"logs":          {},
	"patch":         {},
	"plugin":        {},
	"port-forward":  {},
	"proxy":         {},
	"replace":       {},
	"rollout":       {},
	"run":           {},
	"scale":         {},
	"set":           {},
	"taint":         {},
	"top":           {},
	"uncordon":      {},
	"version":       {},
	"wait":          {},
}
