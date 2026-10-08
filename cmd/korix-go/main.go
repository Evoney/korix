package main

import (
	"flag"
	"fmt"
	"os"

	"github.com/evoneymendonca/korix/internal/tui"
)

func main() {
	flag.Usage = func() {
		fmt.Fprintf(flag.CommandLine.Output(), "Usage: korix-go\n\n")
		fmt.Fprintf(flag.CommandLine.Output(), "Parallel Go port of the Korix terminal control plane.\n")
	}
	flag.Parse()
	if flag.NArg() > 0 {
		fmt.Fprintf(os.Stderr, "korix-go: unexpected argument %q\n", flag.Arg(0))
		os.Exit(2)
	}
	if err := tui.Run(); err != nil {
		fmt.Fprintf(os.Stderr, "korix-go: %v\n", err)
		os.Exit(1)
	}
}
