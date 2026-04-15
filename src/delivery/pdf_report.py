"""
PDF-Report: Konvertiert den HTML-Monatsreport in ein professionell gestyltes PDF.
"""

import logging
import tempfile
from datetime import datetime
from pathlib import Path

from weasyprint import HTML

logger = logging.getLogger(__name__)


def build_report_html(content: str, title: str = None, date: datetime = None) -> str:
    """Bettet den Report-Content in ein gestyltes HTML-Template ein."""
    if date is None:
        date = datetime.now()

    if title is None:
        title = f"Monatsbericht {date.strftime('%B %Y')}"

    month_year = date.strftime("%B %Y")
    date_str = date.strftime("%d.%m.%Y")

    html = f"""<!DOCTYPE html>
<html lang="de">
<head>
<meta charset="UTF-8">
<title>{title}</title>
<style>
    @page {{
        size: A4;
        margin: 20mm 18mm 25mm 18mm;

        @bottom-center {{
            content: "Seite " counter(page) " von " counter(pages);
            font-size: 8pt;
            color: #6b7280;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif;
        }}
    }}

    :root {{
        --bg-primary: #0f172a;
        --bg-secondary: #1e293b;
        --bg-card: #1e293b;
        --border: #334155;
        --text-primary: #f1f5f9;
        --text-secondary: #94a3b8;
        --text-muted: #64748b;
        --accent: #3b82f6;
        --accent-light: #60a5fa;
        --green: #22c55e;
        --green-bg: rgba(34, 197, 94, 0.1);
        --red: #ef4444;
        --red-bg: rgba(239, 68, 68, 0.1);
        --yellow: #eab308;
    }}

    * {{
        margin: 0;
        padding: 0;
        box-sizing: border-box;
    }}

    body {{
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif;
        font-size: 10pt;
        line-height: 1.6;
        color: var(--text-primary);
        background: var(--bg-primary);
    }}

    /* === HEADER === */
    .report-header {{
        background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%);
        border: 1px solid var(--border);
        border-radius: 8px;
        padding: 24px 28px;
        margin-bottom: 24px;
        page-break-inside: avoid;
    }}

    .header-top {{
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 12px;
    }}

    .logo-area {{
        display: flex;
        align-items: center;
        gap: 12px;
    }}

    .logo-placeholder {{
        width: 40px;
        height: 40px;
        background: var(--accent);
        border-radius: 8px;
        display: flex;
        align-items: center;
        justify-content: center;
        color: white;
        font-weight: 700;
        font-size: 16pt;
    }}

    .brand-name {{
        font-family: 'Space Mono', monospace;
        font-size: 14pt;
        font-weight: 700;
        color: var(--text-primary);
        letter-spacing: -0.5px;
    }}

    .brand-sub {{
        font-size: 8pt;
        color: var(--text-secondary);
        text-transform: uppercase;
        letter-spacing: 1px;
    }}

    .header-date {{
        text-align: right;
        font-size: 9pt;
        color: var(--text-secondary);
    }}

    .report-title {{
        font-size: 20pt;
        font-weight: 700;
        color: var(--text-primary);
        letter-spacing: -0.5px;
        margin-top: 8px;
        padding-top: 12px;
        border-top: 1px solid var(--border);
    }}

    .report-subtitle {{
        font-size: 10pt;
        color: var(--accent-light);
        margin-top: 4px;
    }}

    /* === CONTENT === */
    .report-content {{
        background: var(--bg-secondary);
        border: 1px solid var(--border);
        border-radius: 8px;
        padding: 24px 28px;
        margin-bottom: 24px;
    }}

    .report-content h1 {{
        font-size: 16pt;
        font-weight: 700;
        color: var(--accent-light);
        margin: 24px 0 12px 0;
        padding-bottom: 6px;
        border-bottom: 2px solid var(--accent);
        page-break-after: avoid;
    }}

    .report-content h1:first-child {{
        margin-top: 0;
    }}

    .report-content h2 {{
        font-size: 13pt;
        font-weight: 600;
        color: var(--text-primary);
        margin: 20px 0 8px 0;
        page-break-after: avoid;
    }}

    .report-content h3 {{
        font-size: 11pt;
        font-weight: 600;
        color: var(--text-secondary);
        margin: 16px 0 6px 0;
        page-break-after: avoid;
    }}

    .report-content p {{
        margin-bottom: 8px;
        color: var(--text-primary);
    }}

    .report-content ul, .report-content ol {{
        margin: 8px 0 12px 20px;
        color: var(--text-primary);
    }}

    .report-content li {{
        margin-bottom: 4px;
    }}

    .report-content strong, .report-content b {{
        color: var(--text-primary);
        font-weight: 600;
    }}

    .report-content em, .report-content i {{
        color: var(--text-secondary);
    }}

    .report-content code {{
        background: var(--bg-primary);
        padding: 1px 5px;
        border-radius: 3px;
        font-size: 9pt;
        color: var(--accent-light);
    }}

    .report-content pre {{
        background: var(--bg-primary);
        border: 1px solid var(--border);
        border-radius: 6px;
        padding: 12px;
        margin: 10px 0;
        font-size: 8.5pt;
        overflow-x: auto;
        color: var(--text-primary);
    }}

    .report-content blockquote {{
        border-left: 3px solid var(--accent);
        padding: 8px 16px;
        margin: 12px 0;
        background: rgba(59, 130, 246, 0.05);
        color: var(--text-secondary);
        font-style: italic;
    }}

    .report-content hr {{
        border: none;
        border-top: 1px solid var(--border);
        margin: 20px 0;
    }}

    /* === TABELLEN === */
    .report-content table {{
        width: 100%;
        border-collapse: collapse;
        margin: 12px 0;
        font-size: 9pt;
        page-break-inside: avoid;
    }}

    .report-content thead {{
        background: var(--bg-primary);
    }}

    .report-content th {{
        padding: 10px 12px;
        text-align: left;
        font-weight: 600;
        color: var(--text-secondary);
        border-bottom: 2px solid var(--accent);
        text-transform: uppercase;
        font-size: 8pt;
        letter-spacing: 0.5px;
    }}

    .report-content td {{
        padding: 8px 12px;
        border-bottom: 1px solid var(--border);
        color: var(--text-primary);
    }}

    .report-content tr:nth-child(even) {{
        background: rgba(15, 23, 42, 0.3);
    }}

    .report-content tr:hover {{
        background: rgba(59, 130, 246, 0.05);
    }}

    /* === FARBIGE ZAHLEN === */
    .positive, .gain {{
        color: var(--green) !important;
        font-weight: 600;
    }}

    .negative, .loss {{
        color: var(--red) !important;
        font-weight: 600;
    }}

    .neutral {{
        color: var(--yellow) !important;
    }}

    /* === CHART-PLATZHALTER === */
    .chart-placeholder {{
        background: var(--bg-primary);
        border: 2px dashed var(--border);
        border-radius: 8px;
        padding: 40px 20px;
        text-align: center;
        color: var(--text-muted);
        font-size: 10pt;
        margin: 16px 0;
    }}

    .chart-placeholder::before {{
        content: "\\1F4CA";
        display: block;
        font-size: 24pt;
        margin-bottom: 8px;
    }}

    /* === KENNZAHL-KARTEN === */
    .kpi-grid {{
        display: flex;
        gap: 12px;
        margin: 16px 0;
        flex-wrap: wrap;
    }}

    .kpi-card {{
        flex: 1;
        min-width: 120px;
        background: var(--bg-primary);
        border: 1px solid var(--border);
        border-radius: 6px;
        padding: 12px 16px;
        text-align: center;
    }}

    .kpi-label {{
        font-size: 7.5pt;
        color: var(--text-muted);
        text-transform: uppercase;
        letter-spacing: 0.5px;
        margin-bottom: 4px;
    }}

    .kpi-value {{
        font-size: 16pt;
        font-weight: 700;
        color: var(--text-primary);
    }}

    .kpi-change {{
        font-size: 8pt;
        margin-top: 2px;
    }}

    /* === FOOTER === */
    .report-footer {{
        background: var(--bg-secondary);
        border: 1px solid var(--border);
        border-radius: 8px;
        padding: 16px 20px;
        margin-top: 24px;
        page-break-inside: avoid;
    }}

    .disclaimer {{
        font-size: 7pt;
        color: var(--text-muted);
        line-height: 1.5;
    }}

    .disclaimer strong {{
        color: var(--text-secondary);
        display: block;
        margin-bottom: 4px;
        font-size: 7.5pt;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }}

    .footer-meta {{
        display: flex;
        justify-content: space-between;
        margin-top: 8px;
        padding-top: 8px;
        border-top: 1px solid var(--border);
        font-size: 7pt;
        color: var(--text-muted);
    }}
</style>
</head>
<body>

<!-- HEADER -->
<div class="report-header">
    <div class="header-top">
        <div class="logo-area">
            <div class="logo-placeholder">V</div>
            <div>
                <div class="brand-name">Velora</div>
                <div class="brand-sub">AI Wealth Advisor</div>
            </div>
        </div>
        <div class="header-date">
            Erstellt am {date_str}
        </div>
    </div>
    <div class="report-title">{title}</div>
    <div class="report-subtitle">{month_year} &mdash; Automatisch generierte Analyse</div>
</div>

<!-- CONTENT -->
<div class="report-content">
    {content}
</div>

<!-- FOOTER -->
<div class="report-footer">
    <div class="disclaimer">
        <strong>Haftungsausschluss</strong>
        Dieser Bericht wurde automatisch durch KI-gestuetzte Analyse erstellt und dient ausschliesslich
        zu Informationszwecken. Er stellt keine Anlageberatung, Empfehlung oder Aufforderung zum Kauf
        oder Verkauf von Finanzinstrumenten dar. Vergangene Wertentwicklungen sind kein verlaesslicher
        Indikator fuer kuenftige Ergebnisse. Alle Angaben ohne Gewaehr. Investitionsentscheidungen
        sollten auf Grundlage einer eigenen Analyse und ggf. professioneller Beratung getroffen werden.
    </div>
    <div class="footer-meta">
        <span>Velora &mdash; AI Wealth Advisor</span>
        <span>Generiert: {date.strftime('%d.%m.%Y %H:%M')}</span>
    </div>
</div>

</body>
</html>"""
    return html


def colorize_numbers(html_content: str) -> str:
    """Markiert positive/negative Prozentwerte und Geldbetraege farbig."""
    import re

    # Positive Prozentwerte: +X.X% oder +X%
    html_content = re.sub(
        r'(?<![<\w])(\+\d+[.,]?\d*\s*%)',
        r'<span class="positive">\1</span>',
        html_content,
    )
    # Negative Prozentwerte: -X.X% oder -X%
    html_content = re.sub(
        r'(?<![<\w])(-\d+[.,]?\d*\s*%)',
        r'<span class="negative">\1</span>',
        html_content,
    )
    return html_content


def generate_pdf(
    content: str,
    output_path: str = None,
    title: str = None,
    date: datetime = None,
) -> Path:
    """Generiert ein PDF aus dem HTML-Report-Content.

    Args:
        content: HTML-Content (Monatsreport-Text von Claude).
        output_path: Pfad fuer die PDF-Datei. Wenn None, wird ein temp-Pfad genutzt.
        title: Optionaler Titel. Default: 'Monatsbericht [Monat] [Jahr]'.
        date: Optionales Datum. Default: jetzt.

    Returns:
        Path zur generierten PDF-Datei.
    """
    if date is None:
        date = datetime.now()

    # Zahlen farbig markieren
    content = colorize_numbers(content)

    # HTML bauen
    full_html = build_report_html(content, title=title, date=date)

    # Output-Pfad bestimmen
    if output_path is None:
        output_dir = Path(tempfile.gettempdir()) / "velora"
        output_dir.mkdir(parents=True, exist_ok=True)
        filename = f"monatsbericht_{date.strftime('%Y_%m')}.pdf"
        output_path = output_dir / filename

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # PDF generieren
    logger.info(f"Generiere PDF: {output_path}")
    HTML(string=full_html).write_pdf(str(output_path))
    logger.info(f"PDF erstellt: {output_path} ({output_path.stat().st_size / 1024:.0f} KB)")

    return output_path
