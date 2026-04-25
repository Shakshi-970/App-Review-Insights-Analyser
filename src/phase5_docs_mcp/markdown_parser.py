import re
from typing import List, Dict, Any

# ── Groww brand palette (RGB 0–1) ─────────────────────────────────────────────
_GREEN  = {'red': 0.000, 'green': 0.816, 'blue': 0.612}   # #00d09c
_DKGRN  = {'red': 0.059, 'green': 0.239, 'blue': 0.188}   # #0f3d30  (title)
_NAVY   = {'red': 0.118, 'green': 0.165, 'blue': 0.259}   # #1e2a3a
_BLUE   = {'red': 0.145, 'green': 0.388, 'blue': 0.922}   # #2563eb
_AMBER  = {'red': 0.961, 'green': 0.620, 'blue': 0.043}   # #f59e0b
_GRAY   = {'red': 0.612, 'green': 0.643, 'blue': 0.690}   # #9ca3af  (muted)
_BODY   = {'red': 0.102, 'green': 0.102, 'blue': 0.129}   # #1a1a21

# Accent colours cycle per theme card (green / blue / amber)
_ACCENTS = [_GREEN, _BLUE, _AMBER]


class MarkdownToDocs:
    """
    Converts the Pulse Markdown report to Google Docs batchUpdate requests.
    Produces a compact, Groww-branded single-page layout.
    """

    def __init__(self, start_index: int = 1):
        self.current_index = start_index
        self.requests: List[Dict[str, Any]] = []
        self._theme_counter = 0   # cycles accent per H4 heading

        # Compact margins for a clean single-page fit
        self.requests.append({
            "updateDocumentStyle": {
                "documentStyle": {
                    "marginTop":    {"magnitude": 40, "unit": "PT"},
                    "marginBottom": {"magnitude": 40, "unit": "PT"},
                    "marginLeft":   {"magnitude": 54, "unit": "PT"},
                    "marginRight":  {"magnitude": 54, "unit": "PT"},
                },
                "fields": "marginTop,marginBottom,marginLeft,marginRight"
            }
        })

    # ── public API ─────────────────────────────────────────────────────────────

    def parse(self, markdown: str) -> List[Dict[str, Any]]:
        markdown = re.sub(r'<a\s+name=.*?></a>', '', markdown)   # strip anchors

        for raw_line in markdown.split('\n'):
            line = raw_line.strip()

            if not line:
                self._tiny_blank()
                continue

            if line == "---":
                self._add_divider()
                continue

            m = re.match(r'^(#{1,4})\s+(.*)', line)
            if m:
                self._add_heading(m.group(2).strip(), level=len(m.group(1)))
                continue

            m = re.match(r'^[>•\-\*]\s+(.*)', line)
            if m and line[0] in '-*•':
                self._add_bullet(m.group(1))
                continue

            if line.startswith('> '):
                self._add_quote(line[2:].strip().strip('"'))
                continue

            # italic-wrapped metadata / footer: *text* or *text **bold** text*
            if re.match(r'^\*[^*].*[^*]\*$', line) or re.match(r'^\*\*.*\*\*$', line):
                self._add_italic_line(line.strip('*'))
                continue

            self._add_formatted_line(line + "\n")

        return self.requests

    # ── element renderers ──────────────────────────────────────────────────────

    def _add_heading(self, text: str, level: int):
        content = text + "\n"
        start = self.current_index

        if level == 2:
            font_size, color, named = 16, _DKGRN, "HEADING_2"
            sp_above, sp_below, ls = 0, 5, 110
            self._theme_counter = 0
        elif level == 3:
            font_size, color, named = 11, _GREEN, "HEADING_3"
            sp_above, sp_below, ls = 8, 3, 105
            self._theme_counter = 0   # new section: reset accent cycle
        else:   # level 4 — per-theme sub-heading
            accent = _ACCENTS[self._theme_counter % len(_ACCENTS)]
            self._theme_counter += 1
            font_size, color, named = 9, accent, "HEADING_4"
            sp_above, sp_below, ls = 5, 1, 100

        self._insert(content)
        end = self.current_index

        self.requests += [
            self._text_style(start, end, bold=True, color=color, font_size=font_size),
            {
                "updateParagraphStyle": {
                    "range": {"startIndex": start, "endIndex": end},
                    "paragraphStyle": {
                        "namedStyleType": named,
                        "spaceAbove": {"magnitude": sp_above, "unit": "PT"},
                        "spaceBelow": {"magnitude": sp_below, "unit": "PT"},
                        "lineSpacing": ls,
                    },
                    "fields": "namedStyleType,spaceAbove,spaceBelow,lineSpacing"
                }
            }
        ]

    def _add_bullet(self, text: str):
        start = self.current_index

        # Bullet glyph in brand green
        self._insert("• ")
        bullet_end = self.current_index
        self.requests.append(
            self._text_style(start, bullet_end, bold=True, color=_GREEN, font_size=9)
        )

        # Rest of line (may contain **bold**)
        self._add_formatted_line(text + "\n", font_size=9)

        self.requests.append({
            "updateParagraphStyle": {
                "range": {"startIndex": start, "endIndex": self.current_index},
                "paragraphStyle": {
                    "spaceAbove": {"magnitude": 1, "unit": "PT"},
                    "spaceBelow": {"magnitude": 1, "unit": "PT"},
                    "lineSpacing": 110,
                },
                "fields": "spaceAbove,spaceBelow,lineSpacing"
            }
        })

    def _add_quote(self, text: str):
        content = f'“{text}”\n'   # curly quotes
        start = self.current_index
        self._insert(content)
        end = self.current_index

        self.requests += [
            self._text_style(start, end, bold=False, italic=True,
                             color={'red': 0.33, 'green': 0.33, 'blue': 0.33},
                             font_size=8.5),
            {
                "updateParagraphStyle": {
                    "range": {"startIndex": start, "endIndex": end},
                    "paragraphStyle": {
                        "spaceAbove": {"magnitude": 1, "unit": "PT"},
                        "spaceBelow": {"magnitude": 1, "unit": "PT"},
                        "lineSpacing": 105,
                        "indentStart": {"magnitude": 16, "unit": "PT"},
                        "indentFirstLine": {"magnitude": 0, "unit": "PT"},
                    },
                    "fields": "spaceAbove,spaceBelow,lineSpacing,indentStart,indentFirstLine"
                }
            }
        ]

    def _add_italic_line(self, text: str):
        """Render a *italic* metadata or footer line, handling inner **bold**."""
        start = self.current_index
        for part in re.split(r'(\*\*.*?\*\*)', text):
            if not part:
                continue
            if part.startswith('**') and part.endswith('**'):
                inner = part[2:-2]
                if not inner:
                    continue
                seg_start = self.current_index
                self._insert(inner)
                if self.current_index > seg_start:
                    self.requests.append(
                        self._text_style(seg_start, self.current_index, bold=True,
                                         italic=True, color=_NAVY, font_size=8.5)
                    )
            else:
                seg_start = self.current_index
                self._insert(part)
                if self.current_index > seg_start:
                    self.requests.append(
                        self._text_style(seg_start, self.current_index, bold=False,
                                         italic=True, color=_GRAY, font_size=8.5)
                    )

        self._insert("\n")
        self.requests.append({
            "updateParagraphStyle": {
                "range": {"startIndex": start, "endIndex": self.current_index},
                "paragraphStyle": {
                    "spaceAbove": {"magnitude": 2, "unit": "PT"},
                    "spaceBelow": {"magnitude": 2, "unit": "PT"},
                    "lineSpacing": 100,
                },
                "fields": "spaceAbove,spaceBelow,lineSpacing"
            }
        })

    def _add_divider(self):
        """Thin visual separator using a small coloured em-dash line."""
        rule = "—" * 55 + "\n"
        start = self.current_index
        self._insert(rule)
        end = self.current_index

        pale_green = {'red': 0.878, 'green': 0.957, 'blue': 0.929}
        self.requests += [
            self._text_style(start, end, bold=False, color=pale_green, font_size=4.5),
            {
                "updateParagraphStyle": {
                    "range": {"startIndex": start, "endIndex": end},
                    "paragraphStyle": {
                        "spaceAbove": {"magnitude": 5, "unit": "PT"},
                        "spaceBelow": {"magnitude": 5, "unit": "PT"},
                        "lineSpacing": 100,
                    },
                    "fields": "spaceAbove,spaceBelow,lineSpacing"
                }
            }
        ]
        self._theme_counter = 0   # reset accent after each divider

    def _add_formatted_line(self, text: str, font_size: float = 9):
        """Render a line that may contain **bold** spans."""
        for part in re.split(r'(\*\*.*?\*\*)', text):
            if not part:
                continue
            if part.startswith('**') and part.endswith('**'):
                inner = part[2:-2]
                if not inner:
                    continue
                seg_start = self.current_index
                self._insert(inner)
                if self.current_index > seg_start:
                    self.requests.append(
                        self._text_style(seg_start, self.current_index,
                                         bold=True, color=_NAVY, font_size=font_size)
                    )
            else:
                seg_start = self.current_index
                self._insert(part)
                if self.current_index > seg_start:
                    self.requests.append(
                        self._text_style(seg_start, self.current_index,
                                         bold=False, color=_BODY, font_size=font_size)
                    )

    def _tiny_blank(self):
        """Empty paragraph with minimal height so blank lines stay compact."""
        start = self.current_index
        self._insert("\n")
        self.requests.append({
            "updateParagraphStyle": {
                "range": {"startIndex": start, "endIndex": self.current_index},
                "paragraphStyle": {
                    "spaceAbove": {"magnitude": 0, "unit": "PT"},
                    "spaceBelow": {"magnitude": 0, "unit": "PT"},
                    "lineSpacing": 50,
                },
                "fields": "spaceAbove,spaceBelow,lineSpacing"
            }
        })

    # ── low-level helpers ──────────────────────────────────────────────────────

    def _insert(self, text: str):
        """Append an insertText request and advance the index."""
        if not text:
            return
        self.requests.append({
            "insertText": {
                "location": {"index": self.current_index},
                "text": text
            }
        })
        self.current_index += len(text)

    @staticmethod
    def _text_style(start: int, end: int, bold=False, italic=False,
                    color=None, font_size: float = 9) -> Dict[str, Any]:
        return {
            "updateTextStyle": {
                "range": {"startIndex": start, "endIndex": end},
                "textStyle": {
                    "bold": bold,
                    "italic": italic,
                    "fontSize": {"magnitude": font_size, "unit": "PT"},
                    "foregroundColor": {"color": {"rgbColor": color or _BODY}},
                },
                "fields": "bold,italic,fontSize,foregroundColor"
            }
        }
