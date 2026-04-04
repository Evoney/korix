import curses
import os
import textwrap
from collections.abc import Sequence

from .actions import (
    ActionSpec,
    cordon_node,
    delete_pod,
    describe_resource,
    from_translated_command,
    logs_pod,
    rollout_restart_deployment,
    scale_deployment,
    uncordon_node,
)
from .codex_client import CodexClient
from .commands import build_kubectl_command, build_scoped_command, render_command
from .config import load_codex_config
from .constants import DEFAULT_NAMESPACE
from .dashboard import (
    DashboardService,
    DashboardSnapshot,
    DeploymentRow,
    EventRow,
    NodeRow,
    OverviewMetric,
    PodRow,
)
from .errors import CodexError, KubectlError, TranslationError
from .kubectl import KubectlClient
from .translation import Translator

SECTION_ORDER = ["Overview", "Pods", "Deployments", "Nodes", "Events", "Namespaces", "Actions"]

THEME_DEFAULT = {
    "screen_bg": (252, 235),
    "panel": (252, 237),
    "panel_muted": (246, 237),
    "header": (254, 238),
    "footer": (250, 238),
    "accent": (117, 237),
    "accent_soft": (111, 235),
    "focus": (235, 117),
    "ok": (114, 237),
    "warn": (221, 237),
    "critical": (210, 237),
}

THEME_BASIC = {
    "screen_bg": (curses.COLOR_WHITE, curses.COLOR_BLACK),
    "panel": (curses.COLOR_WHITE, curses.COLOR_BLACK),
    "panel_muted": (curses.COLOR_CYAN, curses.COLOR_BLACK),
    "header": (curses.COLOR_WHITE, curses.COLOR_BLUE),
    "footer": (curses.COLOR_WHITE, curses.COLOR_BLACK),
    "accent": (curses.COLOR_CYAN, curses.COLOR_BLACK),
    "accent_soft": (curses.COLOR_BLUE, curses.COLOR_BLACK),
    "focus": (curses.COLOR_BLACK, curses.COLOR_CYAN),
    "ok": (curses.COLOR_GREEN, curses.COLOR_BLACK),
    "warn": (curses.COLOR_YELLOW, curses.COLOR_BLACK),
    "critical": (curses.COLOR_RED, curses.COLOR_BLACK),
}


class KubeAgentTUI:
    def __init__(self):
        self._kubectl = KubectlClient()
        self._dashboard = DashboardService(self._kubectl)
        self._translator: Translator | None = None
        self._contexts: list[str] = []
        self._context = ""
        self._namespace = DEFAULT_NAMESPACE
        self._all_namespaces = False
        self._snapshot = DashboardSnapshot()
        self._section_index = 0
        self._item_index = 0
        self._focus = "items"
        self._detail_text = ""
        self._status_text = "Starting Korix..."
        self._quit = False
        self._fatal_error: str | None = None
        self._stdscr = None
        self._theme_ready = False
        self._theme_pairs: dict[str, int] = {}

    def run(self) -> None:
        curses.wrapper(self._curses_main)

    def _curses_main(self, stdscr) -> None:
        self._stdscr = stdscr
        self._init_theme()
        try:
            curses.curs_set(0)
        except curses.error:
            pass
        stdscr.keypad(True)
        self._initialize()
        while not self._quit:
            self._render()
            key = stdscr.getch()
            self._handle_key(key)

    def _initialize(self) -> None:
        try:
            self._kubectl.ensure_installed()
            self._contexts = self._kubectl.contexts()
            self._context = self._kubectl.current_context() or self._contexts[0]
            try:
                config = load_codex_config(os.environ)
                self._translator = Translator(CodexClient(config))
                self._status_text = "Ready."
            except CodexError as exc:
                self._status_text = f"Ready without natural-language mode: {exc}"
            self.refresh()
        except KubectlError as exc:
            self._fatal_error = str(exc)

    def _init_theme(self) -> None:
        if not curses.has_colors():
            return
        curses.start_color()
        try:
            curses.use_default_colors()
        except curses.error:
            pass
        theme = THEME_DEFAULT if curses.COLORS >= 256 else THEME_BASIC
        pair_id = 1
        for name, (fg, bg) in theme.items():
            curses.init_pair(pair_id, fg, bg)
            self._theme_pairs[name] = pair_id
            pair_id += 1
        self._theme_ready = True
        self._stdscr.bkgd(" ", self._attr("screen_bg"))

    def _attr(self, name: str, extra: int = 0) -> int:
        pair = self._theme_pairs.get(name)
        if not self._theme_ready or pair is None:
            return extra
        return curses.color_pair(pair) | extra

    def refresh(self) -> None:
        if not self._context:
            return
        try:
            self._snapshot = self._dashboard.refresh(
                self._context, self._namespace, self._all_namespaces
            )
            self._clamp_selection()
            self._status_text = (
                f"Refreshed context={self._context} scope={self._namespace_label()} "
                f"errors={len(self._snapshot.errors)}"
            )
            self._detail_text = self._detail_for_selection()
        except KubectlError as exc:
            self._status_text = str(exc)

    def _namespace_label(self) -> str:
        if self._all_namespaces:
            return "*"
        return self._namespace or "-"

    def _current_section(self) -> str:
        return SECTION_ORDER[self._section_index]

    def _records_for_section(self):
        section = self._current_section()
        if section == "Overview":
            return self._snapshot.overview
        if section == "Pods":
            return self._snapshot.pods
        if section == "Deployments":
            return self._snapshot.deployments
        if section == "Nodes":
            return self._snapshot.nodes
        if section == "Events":
            return self._snapshot.events
        if section == "Namespaces":
            records = ["* all namespaces", "- no default namespace"]
            records.extend(self._snapshot.namespaces)
            return records
        return [
            "Enter inspect details",
            "g refresh data",
            "C switch context",
            "n switch namespace scope",
            ": natural-language command preview",
            "Pods: d describe, l logs, p previous logs, x delete pod",
            "Deployments: d describe, r restart, s scale",
            "Nodes: d describe, c cordon, u uncordon",
            "q quit",
        ]

    def _labels_for_section(self) -> list[str]:
        section = self._current_section()
        labels: list[str] = []
        for record in self._records_for_section():
            if section == "Overview":
                metric = record
                labels.append(f"{metric.label:<20} {metric.value:>3} [{metric.status}]")
            elif section == "Pods":
                pod = record
                prefix = f"{pod.namespace}/" if self._all_namespaces else ""
                labels.append(
                    f"{prefix}{pod.name} | {pod.status} | ready {pod.ready} | restarts {pod.restarts}"
                )
            elif section == "Deployments":
                deployment = record
                prefix = f"{deployment.namespace}/" if self._all_namespaces else ""
                labels.append(
                    f"{prefix}{deployment.name} | ready {deployment.ready} | {deployment.issue}"
                )
            elif section == "Nodes":
                node = record
                labels.append(f"{node.name} | {node.status} | {node.roles} | {node.issue}")
            elif section == "Events":
                event = record
                prefix = f"{event.namespace}/" if self._all_namespaces else ""
                labels.append(f"{event.type} | {event.reason} | {prefix}{event.obj}")
            else:
                labels.append(str(record))
        return labels

    def _clamp_selection(self) -> None:
        total = len(self._records_for_section())
        if total == 0:
            self._item_index = 0
        else:
            self._item_index = max(0, min(self._item_index, total - 1))

    def _detail_for_selection(self) -> str:
        records = self._records_for_section()
        section = self._current_section()
        if not records:
            return self._snapshot.errors.get(section.lower(), f"No data for {section}.")

        record = records[self._item_index]
        if section == "Overview":
            metric: OverviewMetric = record
            lines = [f"{metric.label}: {metric.value}", f"Status: {metric.status}"]
            if self._snapshot.errors:
                lines.append("")
                lines.append("Section errors:")
                for name, message in sorted(self._snapshot.errors.items()):
                    lines.append(f"- {name}: {message}")
            return "\n".join(lines)
        if section == "Pods":
            pod: PodRow = record
            return "\n".join(
                [
                    f"Pod: {pod.namespace}/{pod.name}",
                    f"Status: {pod.status}",
                    f"Ready: {pod.ready}",
                    f"Restarts: {pod.restarts}",
                    f"Node: {pod.node}",
                    f"Age: {pod.age}",
                    f"Issue: {pod.issue}",
                    "",
                    "Keys: d describe | l logs | p previous logs | x delete",
                ]
            )
        if section == "Deployments":
            deployment: DeploymentRow = record
            return "\n".join(
                [
                    f"Deployment: {deployment.namespace}/{deployment.name}",
                    f"Ready: {deployment.ready}",
                    f"Available: {deployment.available}",
                    f"Age: {deployment.age}",
                    f"Issue: {deployment.issue}",
                    "",
                    "Keys: d describe | r rollout restart | s scale",
                ]
            )
        if section == "Nodes":
            node: NodeRow = record
            return "\n".join(
                [
                    f"Node: {node.name}",
                    f"Status: {node.status}",
                    f"Roles: {node.roles}",
                    f"Age: {node.age}",
                    f"Issue: {node.issue}",
                    "",
                    "Keys: d describe | c cordon | u uncordon",
                ]
            )
        if section == "Events":
            event: EventRow = record
            return "\n".join(
                [
                    f"Event: {event.type} {event.reason}",
                    f"Object: {event.namespace}/{event.obj}",
                    f"Age: {event.age}",
                    "",
                    event.message or "No event message.",
                ]
            )
        if section == "Namespaces":
            return "Press Enter to switch the active namespace scope."
        return "\n".join(str(record) for record in records)

    def _render(self) -> None:
        stdscr = self._stdscr
        stdscr.erase()
        height, width = stdscr.getmaxyx()
        if self._fatal_error:
            self._fill_rect(0, 0, width, height, "screen_bg")
            self._draw_lines(
                1,
                2,
                width - 4,
                [
                    "Korix failed to start",
                    "",
                    self._fatal_error,
                    "",
                    "Press q to quit.",
                ],
                attr=self._attr("critical", curses.A_BOLD),
            )
            stdscr.refresh()
            return

        self._fill_rect(0, 0, width, height, "screen_bg")
        header_height = 2
        cards_height = 5
        footer_height = 2
        content_top = header_height + cards_height
        sidebar_width = max(20, min(26, width // 5))
        detail_height = max(9, min(15, height // 3))
        list_height = max(5, height - content_top - detail_height - footer_height)
        detail_top = content_top + list_height

        self._draw_header(0, 0, width, header_height)
        self._draw_metric_cards(header_height, 0, width, cards_height)

        self._draw_sidebar(content_top, 0, sidebar_width, list_height)
        self._draw_items(content_top, sidebar_width, width - sidebar_width, list_height)
        self._draw_detail(detail_top, 0, width, height - detail_top - footer_height)

        self._draw_footer(height - footer_height, 0, width, footer_height)
        stdscr.refresh()

    def _draw_header(self, top: int, left: int, width: int, height: int) -> None:
        self._fill_rect(top, left, width, height, "header")
        title = " Korix "
        context = self._truncate(self._context or "-", max(18, width // 3))
        summary = (
            f"context {context}  |  namespace {self._namespace_label()}  |  "
            f"translator {'enabled' if self._translator else 'offline'}"
        )
        self._safe_addnstr(top, left + 1, title, width - 2, self._attr("header", curses.A_BOLD))
        self._safe_addnstr(
            top,
            max(left + len(title) + 2, width - max(40, width // 2)),
            " dark console ",
            max(0, width - 2),
            self._attr("focus", curses.A_BOLD),
        )
        self._safe_addnstr(
            top + 1,
            left + 1,
            summary,
            width - 2,
            self._attr("header"),
        )

    def _draw_metric_cards(self, top: int, left: int, width: int, height: int) -> None:
        metrics = self._snapshot.overview or [OverviewMetric("Overview", 0, "ok")]
        gap = 1
        count = len(metrics)
        total_gap = gap * (count + 1)
        card_width = max(16, (width - total_gap) // max(1, count))
        x = left + gap
        for metric in metrics:
            if x + card_width > width:
                break
            self._draw_box(top, x, card_width, height - 1, metric.label, "panel")
            value_attr = self._status_attr(metric.status, selected=False) | curses.A_BOLD
            self._safe_addnstr(
                top + 2,
                x + 2,
                str(metric.value),
                card_width - 4,
                value_attr,
            )
            self._safe_addnstr(
                top + 2,
                x + min(card_width - 9, 6),
                self._status_badge(metric.status),
                max(0, card_width - 8),
                self._status_attr(metric.status, selected=False),
            )
            x += card_width + gap

    def _draw_sidebar(self, top: int, left: int, width: int, height: int) -> None:
        self._draw_box(top, left, width, height, "Sections", "panel")
        visible_height = max(1, height - 2)
        for offset, name in enumerate(SECTION_ORDER[:visible_height]):
            line = top + 1 + offset
            if line >= top + height:
                break
            selected = self._section_index == offset
            if selected:
                self._fill_rect(line, left + 1, width - 2, 1, "focus")
            mode = self._attr("focus", curses.A_BOLD) if selected else self._attr("panel")
            if selected and self._focus != "sections":
                mode = self._attr("accent")
            prefix = "▸ " if selected else "  "
            self._safe_addnstr(line, left + 1, prefix + name, width - 2, mode)

    def _draw_items(self, top: int, left: int, width: int, height: int) -> None:
        labels = self._labels_for_section()
        title = f"{self._current_section()} ({len(labels)})"
        self._draw_box(top, left, width, height, title, "panel")
        visible = max(1, height - 2)
        start = 0
        if self._item_index >= visible:
            start = self._item_index - visible + 1
        for row in range(visible):
            index = start + row
            line = top + 1 + row
            if line >= top + height or index >= len(labels):
                break
            selected = index == self._item_index
            record = self._records_for_section()[index]
            attr = self._record_attr(record, selected=selected and self._focus == "items")
            if selected:
                fill_style = "focus" if self._focus == "items" else "accent_soft"
                self._fill_rect(line, left + 1, width - 2, 1, fill_style)
            text = self._truncate(labels[index], max(1, width - 4))
            self._safe_addnstr(line, left + 2, text, width - 3, attr)

    def _draw_detail(self, top: int, left: int, width: int, height: int) -> None:
        self._draw_box(top, left, width, height, "Inspector", "panel")
        self._draw_lines(
            top + 1,
            left + 2,
            max(1, width - 4),
            self._detail_text.splitlines(),
            limit=max(1, height - 2),
            attr=self._attr("panel"),
        )

    def _draw_footer(self, top: int, left: int, width: int, height: int) -> None:
        self._fill_rect(top, left, width, height, "footer")
        help_line = "Tab switch focus  |  arrows move  |  Enter inspect  |  g refresh  |  C context  |  n namespace  |  : ask  |  q quit"
        self._safe_addnstr(
            top, left + 1, self._truncate(help_line, width - 2), width - 2, self._attr("footer")
        )
        self._safe_addnstr(
            top + 1,
            left + 1,
            self._truncate(self._status_text, width - 2),
            width - 2,
            self._attr("footer", curses.A_BOLD),
        )

    def _draw_lines(
        self,
        top: int,
        left: int,
        width: int,
        lines: Sequence[str],
        limit: int | None = None,
        attr: int = 0,
    ) -> None:
        current = 0
        max_lines = limit if limit is not None else len(lines)
        for line in lines:
            wrapped = textwrap.wrap(line, width) or [""]
            for chunk in wrapped:
                if current >= max_lines:
                    return
                self._safe_addnstr(top + current, left, chunk, width, attr)
                current += 1

    def _draw_box(
        self, top: int, left: int, width: int, height: int, title: str, style: str
    ) -> None:
        if width < 4 or height < 3:
            return
        self._fill_rect(top, left, width, height, style)
        border_attr = self._attr("panel_muted")
        self._stdscr.hline(top, left + 1, curses.ACS_HLINE, width - 2, border_attr)
        self._stdscr.hline(top + height - 1, left + 1, curses.ACS_HLINE, width - 2, border_attr)
        self._stdscr.vline(top + 1, left, curses.ACS_VLINE, height - 2, border_attr)
        self._stdscr.vline(top + 1, left + width - 1, curses.ACS_VLINE, height - 2, border_attr)
        self._stdscr.addch(top, left, curses.ACS_ULCORNER, border_attr)
        self._stdscr.addch(top, left + width - 1, curses.ACS_URCORNER, border_attr)
        self._stdscr.addch(top + height - 1, left, curses.ACS_LLCORNER, border_attr)
        self._stdscr.addch(top + height - 1, left + width - 1, curses.ACS_LRCORNER, border_attr)
        if title:
            label = f" {title} "
            self._safe_addnstr(
                top,
                left + 2,
                self._truncate(label, width - 4),
                width - 4,
                self._attr("accent", curses.A_BOLD),
            )

    def _fill_rect(self, top: int, left: int, width: int, height: int, style: str) -> None:
        if width <= 0 or height <= 0:
            return
        for row in range(height):
            self._safe_addnstr(top + row, left, " " * max(0, width), width, self._attr(style))

    def _safe_addnstr(self, y: int, x: int, text: str, width: int, attr: int = 0) -> None:
        if width <= 0:
            return
        try:
            self._stdscr.addnstr(y, x, text, width, attr)
        except curses.error:
            pass

    def _truncate(self, text: str, width: int) -> str:
        if width <= 0:
            return ""
        if len(text) <= width:
            return text
        if width <= 3:
            return text[:width]
        return text[: width - 3] + "..."

    def _status_badge(self, status: str) -> str:
        badge = status.upper()
        if len(badge) > 10:
            badge = badge[:10]
        return f"[{badge}]"

    def _status_attr(self, status: str, selected: bool) -> int:
        normalized = status.lower()
        if selected:
            return self._attr("focus", curses.A_BOLD)
        if normalized in {"ok", "healthy", "running", "ready", "completed"}:
            return self._attr("ok")
        if normalized in {"warning", "warn", "notready", "pending"}:
            return self._attr("warn")
        return self._attr("critical")

    def _record_attr(self, record, selected: bool) -> int:
        if selected:
            return self._attr("focus", curses.A_BOLD)
        section = self._current_section()
        if section == "Overview":
            return self._status_attr(record.status, selected=False)
        if section == "Pods":
            status = "healthy" if record.issue == "Healthy" else record.status
            return self._status_attr(status, selected=False)
        if section == "Deployments":
            status = "healthy" if record.issue == "Healthy" else "warning"
            return self._status_attr(status, selected=False)
        if section == "Nodes":
            status = (
                "ready" if record.status == "Ready" and record.issue == "Healthy" else "critical"
            )
            return self._status_attr(status, selected=False)
        if section == "Events":
            status = "warning" if record.type == "Warning" else "ok"
            return self._status_attr(status, selected=False)
        return self._attr("panel")

    def _handle_key(self, key: int) -> None:
        if key in {ord("q"), ord("Q")}:
            self._quit = True
            return
        if self._fatal_error:
            return
        if key == 9:
            self._focus = "sections" if self._focus == "items" else "items"
            return
        if key == curses.KEY_UP:
            self._move_selection(-1)
            return
        if key == curses.KEY_DOWN:
            self._move_selection(1)
            return
        if key == curses.KEY_LEFT:
            self._focus = "sections"
            return
        if key == curses.KEY_RIGHT:
            self._focus = "items"
            return
        if key in {ord("g"), ord("G")}:
            self.refresh()
            return
        if key == ord("C"):
            self._change_context()
            return
        if key == ord("n"):
            self._change_namespace()
            return
        if key == ord(":"):
            self._run_natural_language()
            return
        if key in {10, 13, curses.KEY_ENTER}:
            self._inspect_default()
            return
        if key == ord("d"):
            self._describe_selected()
            return
        if key == ord("l"):
            self._show_logs(previous=False)
            return
        if key == ord("p"):
            self._show_logs(previous=True)
            return
        if key == ord("x"):
            self._delete_selected_pod()
            return
        if key == ord("r"):
            self._restart_selected_deployment()
            return
        if key == ord("s"):
            self._scale_selected_deployment()
            return
        if key == ord("c"):
            self._cordon_selected_node()
            return
        if key == ord("u"):
            self._uncordon_selected_node()
            return

    def _move_selection(self, delta: int) -> None:
        if self._focus == "sections":
            self._section_index = max(0, min(self._section_index + delta, len(SECTION_ORDER) - 1))
            self._item_index = 0
        else:
            total = len(self._records_for_section())
            if total:
                self._item_index = max(0, min(self._item_index + delta, total - 1))
        self._detail_text = self._detail_for_selection()

    def _prompt_input(self, label: str, default: str = "") -> str:
        height, width = self._stdscr.getmaxyx()
        prompt = f"{label}"
        if default:
            prompt += f" [{default}]"
        prompt += ": "
        curses.echo()
        try:
            curses.curs_set(1)
        except curses.error:
            pass
        self._stdscr.move(height - 1, 0)
        self._stdscr.clrtoeol()
        self._stdscr.addnstr(height - 1, 0, prompt, width - 1)
        raw = self._stdscr.getstr(
            height - 1, min(len(prompt), width - 1), max(1, width - len(prompt) - 1)
        )
        curses.noecho()
        try:
            curses.curs_set(0)
        except curses.error:
            pass
        text = raw.decode("utf-8", errors="ignore").strip()
        self._status_text = "Ready."
        return text or default

    def _confirm(self, command_text: str) -> bool:
        answer = self._prompt_input(f"Run '{command_text}'? type yes to confirm", default="no")
        return answer.strip().lower() == "yes"

    def _change_context(self) -> None:
        self._detail_text = "Available contexts:\n" + "\n".join(
            f"{idx}. {name}" for idx, name in enumerate(self._contexts, start=1)
        )
        choice = self._prompt_input("Context number or name", default=self._context)
        context = self._resolve_named_choice(choice, self._contexts)
        if not context:
            self._status_text = f"Unknown context: {choice}"
            return
        self._context = context
        self.refresh()

    def _change_namespace(self) -> None:
        namespace_lines = ["Namespaces:", "* all namespaces", "- no default namespace"]
        namespace_lines.extend(self._snapshot.namespaces)
        self._detail_text = "\n".join(namespace_lines)
        current = "*" if self._all_namespaces else self._namespace
        choice = self._prompt_input("Namespace (* for all, - for none)", default=current)
        if choice == "*":
            self._all_namespaces = True
            self._namespace = DEFAULT_NAMESPACE
        elif choice == "-":
            self._all_namespaces = False
            self._namespace = ""
        else:
            self._all_namespaces = False
            self._namespace = choice
        self.refresh()

    def _resolve_named_choice(self, choice: str, values: Sequence[str]) -> str | None:
        if choice in values:
            return choice
        if choice.isdigit():
            index = int(choice)
            if 1 <= index <= len(values):
                return values[index - 1]
        return None

    def _run_natural_language(self) -> None:
        if not self._translator:
            self._status_text = "Natural-language translation is unavailable."
            return
        request = self._prompt_input("Ask Korix")
        if not request:
            self._status_text = "Command input cancelled."
            return
        try:
            spec = self._translator.translate(request)
        except TranslationError as exc:
            self._detail_text = str(exc)
            self._status_text = "Translation failed."
            return
        self._execute_action(from_translated_command(spec.args))

    def _inspect_default(self) -> None:
        if self._current_section() == "Namespaces":
            self._set_selected_namespace()
            return
        self._detail_text = self._detail_for_selection()

    def _set_selected_namespace(self) -> None:
        records = self._records_for_section()
        if not records:
            return
        selected = records[self._item_index]
        if selected == "* all namespaces":
            self._all_namespaces = True
            self._namespace = DEFAULT_NAMESPACE
        elif selected == "- no default namespace":
            self._all_namespaces = False
            self._namespace = ""
        else:
            self._all_namespaces = False
            self._namespace = selected
        self.refresh()

    def _describe_selected(self) -> None:
        section = self._current_section()
        records = self._records_for_section()
        if not records:
            return
        selected = records[self._item_index]
        if section == "Pods":
            self._execute_action(describe_resource("pod", selected.name))
        elif section == "Deployments":
            self._execute_action(describe_resource("deployment", selected.name))
        elif section == "Nodes":
            self._execute_action(describe_resource("node", selected.name, namespaced=False))

    def _show_logs(self, previous: bool) -> None:
        if self._current_section() != "Pods" or not self._records_for_section():
            return
        pod = self._records_for_section()[self._item_index]
        self._execute_action(logs_pod(pod.name, previous=previous))

    def _delete_selected_pod(self) -> None:
        if self._current_section() != "Pods" or not self._records_for_section():
            return
        pod = self._records_for_section()[self._item_index]
        self._execute_action(delete_pod(pod.name))

    def _restart_selected_deployment(self) -> None:
        if self._current_section() != "Deployments" or not self._records_for_section():
            return
        deployment = self._records_for_section()[self._item_index]
        self._execute_action(rollout_restart_deployment(deployment.name))

    def _scale_selected_deployment(self) -> None:
        if self._current_section() != "Deployments" or not self._records_for_section():
            return
        deployment = self._records_for_section()[self._item_index]
        replicas_text = self._prompt_input(
            "Target replicas", default=deployment.ready.split("/", 1)[-1]
        )
        try:
            replicas = int(replicas_text)
        except ValueError:
            self._status_text = f"Invalid replica count: {replicas_text}"
            return
        self._execute_action(scale_deployment(deployment.name, replicas))

    def _cordon_selected_node(self) -> None:
        if self._current_section() != "Nodes" or not self._records_for_section():
            return
        node = self._records_for_section()[self._item_index]
        self._execute_action(cordon_node(node.name))

    def _uncordon_selected_node(self) -> None:
        if self._current_section() != "Nodes" or not self._records_for_section():
            return
        node = self._records_for_section()[self._item_index]
        self._execute_action(uncordon_node(node.name))

    def _execute_action(self, action: ActionSpec) -> None:
        if action.scope == "cluster":
            cmd = build_scoped_command(
                action.args, self._context, self._namespace, self._all_namespaces, namespaced=False
            )
        elif action.scope == "namespaced":
            cmd = build_scoped_command(
                action.args, self._context, self._namespace, self._all_namespaces, namespaced=True
            )
        else:
            cmd = build_kubectl_command(
                action.args, self._context, self._namespace, self._all_namespaces
            )

        command_text = render_command(cmd)
        if action.requires_confirmation and not self._confirm(command_text):
            self._status_text = "Action cancelled."
            self._detail_text = f"Skipped:\n{command_text}"
            return

        result = self._kubectl.run(cmd, check=False)
        chunks = [f"$ {command_text}", ""]
        if result.stdout:
            chunks.append(result.stdout.rstrip())
        if result.stderr:
            chunks.extend(["", result.stderr.rstrip()])
        if result.returncode != 0:
            chunks.extend(["", f"Command exited with status {result.returncode}."])
            self._status_text = f"Command failed: {action.label}"
        else:
            self._status_text = f"Command completed: {action.label}"
        self._detail_text = "\n".join(chunks)

        if result.returncode == 0 and action.requires_confirmation:
            self.refresh()


def main() -> None:
    KubeAgentTUI().run()
