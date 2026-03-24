from __future__ import annotations

BACKGROUND = "#0B0F14"
PANEL_BG = "#111827"
PANEL_ALT = "#0F172A"
TEXT = "#E5E7EB"
MUTED = "#9CA3AF"
ACCENT = "#7C3AED"
WARNING = "#F59E0B"
CYAN = "#06B6D4"
SUCCESS = "#10B981"
ERROR = "#EF4444"
BORDER = "#374151"

CSS = f"""
Screen {{
  background: {BACKGROUND};
  color: {TEXT};
}}

#root-grid {{
  layout: grid;
  grid-size: 2 3;
  grid-columns: 2fr 1fr;
  grid-rows: auto 1fr 14;
  height: 1fr;
}}

#header {{
  column-span: 2;
  height: 3;
  background: {PANEL_ALT};
  border: heavy {ACCENT};
  padding: 0 1;
}}

#chat-panel, #brain-panel, #heartbeat-panel, #logs-panel, #footer-panel {{
  background: {PANEL_BG};
  border: heavy {BORDER};
  padding: 0 1;
}}

#right-stack {{
  layout: grid;
  grid-size: 1 2;
  grid-rows: 1fr 1fr;
}}

.panel-title {{
  color: {ACCENT};
  text-style: bold;
}}

.warning-title {{
  color: {WARNING};
  text-style: bold;
}}

.success {{ color: {SUCCESS}; }}
.warning {{ color: {WARNING}; }}
.cyan {{ color: {CYAN}; }}
.error {{ color: {ERROR}; }}
.muted {{ color: {MUTED}; }}

#logs-tabs {{
  height: 1;
  color: {MUTED};
}}

#approval-popup {{
  dock: top;
  display: none;
  background: {PANEL_ALT};
  border: heavy {WARNING};
  color: {TEXT};
  padding: 1;
}}

#footer-panel {{
  column-span: 2;
  height: 4;
}}

Input {{
  background: {BACKGROUND};
  color: {TEXT};
  border: heavy {ACCENT};
}}
"""
