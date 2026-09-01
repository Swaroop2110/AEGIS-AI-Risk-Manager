"""Agent 4: generate a concise, bank-ready evidence PDF packet."""

from __future__ import annotations

from pathlib import Path
import re
from typing import Any

from config import EVIDENCE_DIR

from .evidence_aggregator import EvidenceBundle
from .win_predictor import DefenseDecision

# Import ReportLab at module level — raise clear error at PDF generation time if missing
try:
    from reportlab.lib.colors import HexColor
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
    _HAS_REPORTLAB = True
except ImportError:
    _HAS_REPORTLAB = False


class EvidencePDFCompiler:
    """Compile a portable evidence packet with no network or LLM dependency."""

    def compile(
        self,
        dispute_id: str,
        reason_code: str,
        bundle: EvidenceBundle,
        strategy: dict[str, Any],
        decision: DefenseDecision,
        causal_explanation: dict[str, Any] | None,
        counterfactual: str | None,
    ) -> Path:
        if not _HAS_REPORTLAB:
            raise RuntimeError("reportlab is required to generate evidence PDFs. Install with: pip install reportlab")

        filename = f"evidence_{self._safe_filename(dispute_id)}.pdf"
        path = EVIDENCE_DIR / filename
        styles = getSampleStyleSheet()
        document = SimpleDocTemplate(
            str(path), pagesize=A4, rightMargin=16 * mm, leftMargin=16 * mm, topMargin=16 * mm, bottomMargin=16 * mm
        )
        story = [
            Paragraph("AEGIS Dispute Evidence Packet", styles["Title"]),
            Paragraph(
                "Autonomous Evidence-Generating Intelligence System &mdash; Razorpay AI Buildathon 2026",
                styles["BodyText"],
            ),
            Spacer(1, 8 * mm),
        ]
        transaction = bundle.sections["transaction"]
        story.extend(self._section(
            "Dispute Summary",
            [
                ("Dispute ID", dispute_id),
                ("Transaction ID", transaction["transaction_id"]),
                ("Merchant", transaction["merchant"]),
                ("Amount", f"{transaction['currency']} {transaction['amount'] / 100:,.2f}"),
                ("Reason Code", reason_code),
                ("Recommended Action", decision.recommended_action.replace("_", " ").title()),
                ("Estimated Win Probability", f"{decision.win_probability:.0%}"),
            ],
        ))
        story.extend(self._section("Authentication Evidence", bundle.sections["authentication"].items()))
        story.extend(self._section("Device & Network Intelligence", bundle.sections["device_network"].items()))
        delivery_items = list(bundle.sections["delivery"].items()) or [("Status", "No delivery record available")]
        story.extend(self._section("Fulfilment & Delivery Proof", delivery_items))
        story.extend(self._section("Customer Behaviour & History", bundle.sections["customer_history"].items()))
        story.extend(self._section(
            "Reason-Code Strategy",
            [
                ("Primary strategy", strategy["primary"]),
                ("Selected evidence", ", ".join(strategy["selected_evidence"]) or "No mapped evidence"),
                ("Missing evidence", ", ".join(strategy["missing_evidence"]) or "None"),
            ],
        ))
        factors = (causal_explanation or {}).get("top_factors", [])
        story.extend(self._section(
            "AI Risk Assessment",
            [
                ("Top risk factors", ", ".join(item.get("factor", "") for item in factors) or "No elevated risk factors"),
                ("Counterfactual", counterfactual or "No counterfactual explanation recorded"),
                ("Expected value", f"INR {decision.cost_benefit['expected_value'] / 100:,.2f}"),
            ],
        ))
        story.append(Spacer(1, 5 * mm))
        story.append(Paragraph(
            "This evidence packet was compiled from authentication-time records preserved by AEGIS. "
            "The merchant should review all information before filing representment.",
            styles["BodyText"],
        ))
        document.build(story)
        return path

    @staticmethod
    def _section(title: str, values) -> list:
        styles = getSampleStyleSheet()
        rows = [
            [
                Paragraph(f"<b>{str(key).replace('_', ' ').title()}</b>", styles["BodyText"]),
                Paragraph(str(value), styles["BodyText"]),
            ]
            for key, value in values
        ]
        if not rows:
            rows = [[Paragraph("<b>—</b>", styles["BodyText"]), Paragraph("No data", styles["BodyText"])]]
        table = Table(rows, colWidths=[48 * mm, 120 * mm])
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), HexColor("#F3F6FC")),
            ("GRID", (0, 0), (-1, -1), 0.25, HexColor("#CBD5E1")),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 6),
            ("RIGHTPADDING", (0, 0), (-1, -1), 6),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ]))
        return [Paragraph(title, styles["Heading2"]), table, Spacer(1, 5 * mm)]

    @staticmethod
    def _safe_filename(value: str) -> str:
        return re.sub(r"[^A-Za-z0-9_-]", "_", value)

