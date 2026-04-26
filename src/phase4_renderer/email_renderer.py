from src.phase0_foundations.models import PulseReport
from datetime import datetime

# ── Groww brand palette (two-color) ──────────────────────────────────────────
_BLUE  = "#6C63FF"   # circle / primary
_TEAL  = "#00D09C"   # wave / accent

# Soft tint backgrounds derived from the two brand colors
_BLUE_TINT = "#F0EEFF"
_TEAL_TINT = "#E6FAF5"

# Alternating card accents — strictly the two brand colors
_CARD_ACCENTS = [_BLUE, _TEAL, _BLUE]
_CARD_TINTS   = [_BLUE_TINT, _TEAL_TINT, _BLUE_TINT]
_CARD_NUMS    = ["01", "02", "03"]


class EmailRenderer:
    """
    Converts a PulseReport into a visually rich HTML email teaser.
    Strict two-color palette: #6C63FF (Groww blue) and #00D09C (Groww teal).
    """

    def render(self, report: PulseReport, doc_link: str = "#") -> str:
        top_themes = report.themes[:3]

        theme_cards = self._build_theme_cards(top_themes)
        quote_cards = self._build_quote_cards(top_themes)
        action_rows = self._build_action_rows(top_themes)

        start_date = "2026-04-10"
        end_date   = datetime.now().strftime("%Y-%m-%d")
        run_id     = "84116cdf-24c2-4a18-936e-eff1865c3cb3"
        week_label = report.iso_week
        week_num   = week_label.split("-W")[-1] if "-W" in week_label else week_label

        return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{report.product} — Weekly Review Pulse — {week_label}</title>
</head>
<body style="margin:0;padding:0;background-color:#F0EEFF;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;">

  <table width="100%" cellpadding="0" cellspacing="0" border="0"
         style="background-color:#F0EEFF;padding:32px 16px;">
    <tr><td align="center">
      <table width="620" cellpadding="0" cellspacing="0" border="0"
             style="max-width:620px;width:100%;">

        <!-- ══ HEADER ══ -->
        <tr>
          <td style="background:{_BLUE};border-radius:14px 14px 0 0;padding:36px 40px 30px;">

            <!-- pill badge -->
            <div style="display:inline-block;background:{_TEAL};color:#ffffff;
                        font-size:10px;font-weight:700;letter-spacing:1.6px;
                        text-transform:uppercase;padding:5px 14px;border-radius:20px;
                        margin-bottom:18px;">
              Weekly Pulse &nbsp;&bull;&nbsp; Week {week_num}
            </div>

            <h1 style="margin:0 0 8px;font-size:30px;font-weight:800;
                        color:#ffffff;letter-spacing:-0.5px;line-height:1.1;">
              {report.product} — Weekly Review Pulse
            </h1>

            <p style="margin:0;font-size:13px;color:rgba(255,255,255,0.75);letter-spacing:0.3px;">
              {start_date} &nbsp;&rarr;&nbsp; {end_date}
              &nbsp;&middot;&nbsp; {report.iso_week}
            </p>

          </td>
        </tr>

        <!-- ══ STATS STRIP ══ -->
        <tr>
          <td style="background:{_TEAL};padding:13px 40px;">
            <table width="100%" cellpadding="0" cellspacing="0" border="0">
              <tr>
                <td style="color:#ffffff;font-size:13px;font-weight:700;">
                  &#128202;&nbsp; {report.review_count:,} reviews analysed
                </td>
                <td align="right"
                    style="color:rgba(255,255,255,0.85);font-size:13px;font-weight:500;">
                  {len(top_themes)} themes &nbsp;&#128270;
                </td>
              </tr>
            </table>
          </td>
        </tr>

        <!-- ══ MAIN CARD ══ -->
        <tr>
          <td style="background:#ffffff;padding:36px 40px;
                     border-radius:0 0 14px 14px;
                     box-shadow:0 8px 30px rgba(108,99,255,0.10);">

            <!-- ── Top Themes ── -->
            <p style="margin:0 0 14px;font-size:10px;font-weight:700;
                      letter-spacing:2px;text-transform:uppercase;color:{_BLUE};">
              Top themes this week
            </p>
{theme_cards}
            <!-- divider -->
            <div style="border-top:2px solid {_BLUE_TINT};margin:26px 0;"></div>

            <!-- ── Voice of the Customer ── -->
            <p style="margin:0 0 14px;font-size:10px;font-weight:700;
                      letter-spacing:2px;text-transform:uppercase;color:{_TEAL};">
              What users are saying
            </p>
{quote_cards}
            <!-- divider -->
            <div style="border-top:2px solid {_TEAL_TINT};margin:26px 0;"></div>

            <!-- ── Recommended Actions ── -->
            <p style="margin:0 0 14px;font-size:10px;font-weight:700;
                      letter-spacing:2px;text-transform:uppercase;color:{_BLUE};">
              Recommended actions
            </p>
{action_rows}
            <!-- divider -->
            <div style="border-top:2px solid {_BLUE_TINT};margin:30px 0 26px;"></div>

            <!-- ── CTA ── -->
            <div style="text-align:center;">
              <a href="{doc_link}"
                 style="display:inline-block;background:{_BLUE};color:#ffffff;
                        font-size:15px;font-weight:700;text-decoration:none;
                        padding:15px 40px;border-radius:10px;
                        box-shadow:0 5px 18px rgba(108,99,255,0.35);
                        letter-spacing:0.3px;">
                Read full report &nbsp;&rarr;
              </a>
              <p style="margin:12px 0 0;font-size:12px;color:#9ca3af;">
                Full analysis, all themes and data breakdowns in the linked doc.
              </p>
            </div>

          </td>
        </tr>

        <!-- ══ FOOTER ══ -->
        <tr>
          <td style="padding:18px 40px 8px;text-align:center;">
            <p style="margin:0;font-size:11px;color:#a0a8b4;line-height:1.6;">
              run_id&nbsp;{run_id}&nbsp;&middot;&nbsp;Generated by Pulse Agent&nbsp;&middot;&nbsp;
              <a href="#" style="color:{_TEAL};text-decoration:none;">Unsubscribe</a>
            </p>
          </td>
        </tr>

      </table>
    </td></tr>
  </table>

</body>
</html>"""

    # ── helpers ───────────────────────────────────────────────────────────────

    def _build_theme_cards(self, themes) -> str:
        cards = ""
        for i, theme in enumerate(themes):
            accent = _CARD_ACCENTS[i % len(_CARD_ACCENTS)]
            bg     = _CARD_TINTS[i % len(_CARD_TINTS)]
            num    = _CARD_NUMS[i % len(_CARD_NUMS)]
            cards += f"""            <table width="100%" cellpadding="0" cellspacing="0" border="0"
                   style="background:{bg};border-radius:10px;margin-bottom:10px;
                          border-left:4px solid {accent};">
              <tr>
                <td style="padding:14px 18px;">
                  <div style="font-size:10px;font-weight:700;color:{accent};
                              letter-spacing:1.2px;margin-bottom:5px;">
                    THEME {num}
                  </div>
                  <div style="font-size:15px;font-weight:700;color:#1a1a2e;margin-bottom:5px;">
                    {theme.name}
                  </div>
                  <div style="font-size:13px;color:#4b5563;line-height:1.6;">
                    {theme.description}
                  </div>
                </td>
              </tr>
            </table>
"""
        return cards

    def _build_quote_cards(self, themes) -> str:
        blocks = ""
        for i, theme in enumerate(themes):
            accent = _CARD_ACCENTS[i % len(_CARD_ACCENTS)]
            
            # Deduplicate quotes
            seen = set()
            unique_quotes = []
            for q in theme.quotes:
                q_clean = q.strip().strip('"').strip("'")
                q_lower = q_clean.lower()
                if q_lower not in seen:
                    seen.add(q_lower)
                    unique_quotes.append(q_clean)
                    
            quote  = unique_quotes[0] if unique_quotes else ""
            
            blocks += f"""            <table width="100%" cellpadding="0" cellspacing="0" border="0"
                   style="margin-bottom:12px;">
              <tr>
                <td style="width:4px;background:{accent};border-radius:3px;">&nbsp;</td>
                <td style="padding:10px 16px;">
                  <div style="font-size:26px;color:{accent};line-height:0.9;
                              margin-bottom:4px;font-family:Georgia,serif;">
                    &ldquo;
                  </div>
                  <div style="font-size:13.5px;color:#374151;font-style:italic;line-height:1.65;">
                    {quote}
                  </div>
                  <div style="font-size:11px;color:#9ca3af;margin-top:7px;
                              font-weight:600;letter-spacing:0.3px;">
                    &mdash;&nbsp;{theme.name}
                  </div>
                </td>
              </tr>
            </table>
"""
        return blocks

    def _build_action_rows(self, themes) -> str:
        rows = ""
        for i, theme in enumerate(themes):
            accent = _CARD_ACCENTS[i % len(_CARD_ACCENTS)]
            action = theme.action_ideas[0] if theme.action_ideas else ""
            rows += f"""            <table width="100%" cellpadding="0" cellspacing="0" border="0"
                   style="margin-bottom:11px;">
              <tr>
                <td style="width:26px;vertical-align:top;padding-top:1px;">
                  <div style="width:24px;height:24px;background:{accent};border-radius:50%;
                              text-align:center;line-height:24px;font-size:11px;
                              font-weight:800;color:#ffffff;">
                    {i + 1}
                  </div>
                </td>
                <td style="padding-left:12px;font-size:13px;color:#374151;line-height:1.6;">
                  <strong style="color:#1a1a2e;">{theme.name}:</strong>&nbsp;{action}
                </td>
              </tr>
            </table>
"""
        return rows
