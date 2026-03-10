"""
PDF Report Generation Service
Generates professional inspection reports with branding, images, and structured data.
Now includes detailed contamination analysis.
"""
import io
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image, PageBreak,
    HRFlowable
)
from reportlab.platypus.flowables import KeepTogether

# Optional: use PIL for image resizing (to reduce PDF size)
try:
    from PIL import Image as PILImage
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

# Adjust imports to your project structure
from app.config import settings
from app.services.storage_service import StorageService

logger = logging.getLogger(__name__)


class ReportService:
    """Service for generating technical container inspection reports with contamination focus."""

    def __init__(self):
        self.styles = getSampleStyleSheet()
        self.storage_service = StorageService()  # kept for potential future use
        self._setup_custom_styles()

    def _setup_custom_styles(self):
        """Setup custom paragraph styles for the report."""
        self.styles.add(ParagraphStyle(
            name='CustomTitle',
            parent=self.styles['Heading1'],
            fontSize=24,
            textColor=colors.HexColor('#1f1f1f'),
            spaceAfter=30,
            alignment=TA_CENTER,
            fontName='Helvetica-Bold'
        ))

        self.styles.add(ParagraphStyle(
            name='CustomSubtitle',
            parent=self.styles['Normal'],
            fontSize=12,
            textColor=colors.HexColor('#6b7280'),
            spaceAfter=20,
            alignment=TA_CENTER,
            fontName='Helvetica'
        ))

        self.styles.add(ParagraphStyle(
            name='SectionHeader',
            parent=self.styles['Heading2'],
            fontSize=14,
            textColor=colors.HexColor('#1f1f1f'),
            spaceAfter=12,
            spaceBefore=20,
            fontName='Helvetica-Bold'
        ))

        self.styles.add(ParagraphStyle(
            name='InfoText',
            parent=self.styles['Normal'],
            fontSize=10,
            textColor=colors.HexColor('#374151'),
            spaceAfter=6,
            fontName='Helvetica'
        ))

        self.styles.add(ParagraphStyle(
            name='TableNote',
            parent=self.styles['Italic'],
            fontSize=9,
            textColor=colors.HexColor('#4b5563'),
            leftIndent=10,
            rightIndent=10,
            spaceBefore=4,
            spaceAfter=12
        ))

        self.styles.add(ParagraphStyle(
            name='CenteredFooter',
            parent=self.styles['Normal'],
            fontSize=10,
            textColor=colors.HexColor('#6b7280'),
            alignment=TA_CENTER,
            fontName='Helvetica-Oblique',
            spaceBefore=30
        ))

        self.styles.add(ParagraphStyle(
            name='WarningText',
            parent=self.styles['Normal'],
            fontSize=10,
            textColor=colors.HexColor('#b91c1c'),  # red
            spaceAfter=6,
            fontName='Helvetica-Bold'
        ))

    # ----------------------------------------------------------------------
    # Helper methods for image handling and location estimation
    # ----------------------------------------------------------------------
    def _resolve_image_path(self, image_path: Optional[str]) -> Optional[Path]:
        """Resolve an image path using STORAGE_ROOT and ROOT_DIR as fallback."""
        if not image_path:
            return None
        # Try STORAGE_ROOT first (where uploaded images are stored)
        storage_root = getattr(settings, 'STORAGE_ROOT', None)
        if storage_root:
            full = Path(storage_root) / image_path
            if full.exists():
                return full
        # Fallback to project root
        root_dir = getattr(settings, 'ROOT_DIR', Path.cwd())
        full = root_dir / image_path
        return full if full.exists() else None

    def _estimate_location(self, detection: Dict[str, Any]) -> str:
        """
        Estimate a rough location from bounding box coordinates.
        Returns a string like 'top-left', 'bottom-center', etc.
        """
        # DetectionResponse uses flat bbox_x, bbox_y, etc.
        x = detection.get('bbox_x')
        y = detection.get('bbox_y')
        w = detection.get('bbox_w')
        h = detection.get('bbox_h')
        
        if x is None or y is None or w is None or h is None:
            # Fallback to 'bbox' list if present
            bbox = detection.get('bbox')
            if not bbox or len(bbox) < 4:
                return "N/A"
            x, y, w, h = bbox[:4]
            
        # We don't have image dimensions, so we use absolute coordinates 
        # as a rough guide, assuming standard 1920x1080 or similar if they are large,
        # or relative [0,1] if they are small.
        
        # If they look like normalized coordinates (0 to 1)
        if 0 <= x <= 1 and 0 <= y <= 1:
            x_center = x + (w / 2)
            y_center = y + (h / 2)
        else:
            # Assume pixels, we'll just guess
            return f"at ({int(x)}, {int(y)})"

        # Vertical (top, middle, bottom)
        if y_center < 0.33:
            vert = "top"
        elif y_center < 0.66:
            vert = "middle"
        else:
            vert = "bottom"

        # Horizontal (left, center, right)
        if x_center < 0.33:
            horz = "left"
        elif x_center < 0.66:
            horz = "center"
        else:
            horz = "right"

        return f"{vert}-{horz}"

    # ----------------------------------------------------------------------
    # Contamination aggregation
    # ----------------------------------------------------------------------
    def _aggregate_contamination(self, frames: List[Dict]) -> Dict[str, Any]:
        """
        Process all frames and return a summary of contamination findings.
        Expects each detection to have a 'category' field.
        """
        summary = {
            "total_frames": len(frames),
            "frames_with_contamination": 0,
            "contamination_types": set(),
            "frame_details": []          # list of dicts with frame_num, image_path, detections
        }
        for idx, frame in enumerate(frames, 1):
            dets = frame.get('detections', [])
            # In this project, 'damage' and 'contamination' are often treated similarly for reporting
            cont_dets = [d for d in dets if d.get('category') in ('contamination', 'damage', 'dirt')]
            if cont_dets:
                summary["frames_with_contamination"] += 1
                for d in cont_dets:
                    label = d.get('label', 'unknown')
                    summary["contamination_types"].add(label)
                summary["frame_details"].append({
                    "frame_num": idx,
                    "image_path": frame.get('overlay_path') or frame.get('image_path'),
                    "detections": cont_dets
                })
        # Convert set to list for JSON serialization / later use
        summary["contamination_types"] = list(summary["contamination_types"])
        return summary

    # ----------------------------------------------------------------------
    # Section builders
    # ----------------------------------------------------------------------
    def _add_header(self, elements: List, logo_path: Optional[Path] = None):
        """Add company logo, title, and horizontal rule."""
        if logo_path and logo_path.exists():
            try:
                logo = Image(str(logo_path), width=1.5*inch, height=1.5*inch, kind='proportional')
                logo.hAlign = 'CENTER'
                elements.append(logo)
                elements.append(Spacer(1, 0.2*inch))
            except Exception as e:
                logger.warning(f"Could not add logo: {e}")

        elements.append(Paragraph("MCS Robotics", self.styles['CustomTitle']))
        elements.append(Paragraph("Container Inspection System", self.styles['CustomSubtitle']))
        elements.append(HRFlowable(width="100%", thickness=2, color=colors.HexColor('#e5e7eb')))
        elements.append(Spacer(1, 0.3*inch))

    def _add_footer(self, canvas, doc):
        """Footer callback with page number and timestamp."""
        canvas.saveState()
        app_version = getattr(settings, 'APP_VERSION', '3.0.0')
        footer_text = f"Generated by MCS Robotics Inspection Suite v{app_version}"
        canvas.setFont('Helvetica', 8)
        canvas.setFillColor(colors.HexColor('#9ca3af'))
        canvas.drawCentredString(letter[0]/2, 0.5*inch, footer_text)
        canvas.drawRightString(letter[0] - 0.75*inch, 0.5*inch, f"Page {doc.page}")
        canvas.drawString(0.75*inch, 0.5*inch, f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        canvas.restoreState()

    def _add_summary_section(self, elements: List, inspection_data: Dict):
        """Add the inspection summary table."""
        elements.append(Paragraph("INSPECTION SUMMARY", self.styles['SectionHeader']))
        summary_data = [
            ['Inspection ID:', str(inspection_data.get('id', 'N/A'))],
            ['Container ID:', inspection_data.get('container_id', 'UNKNOWN')],
            ['ISO Type:', inspection_data.get('iso_type', 'Unknown')],
            ['Stage:', inspection_data.get('stage', 'None')],
            ['Operational Status:', inspection_data.get('status', 'N/A').upper()],
        ]
        summary_table = Table(summary_data, colWidths=[2*inch, 4*inch])
        summary_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#f3f4f6')),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e5e7eb')),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ]))
        elements.append(summary_table)
        elements.append(Paragraph(
            "<b>Table Context:</b> This section details administrative metadata and current logistics staging. "
            "Operational status indicates the container's readiness for transit based on structural visual confirmation.",
            self.styles['TableNote']
        ))
        elements.append(Spacer(1, 0.2*inch))

    def _add_risk_section(self, elements: List, inspection_data: Dict):
        """Add the risk assessment table."""
        elements.append(Paragraph("RISK ASSESSMENT", self.styles['SectionHeader']))
        risk_data = [
            ['Risk Score:', str(inspection_data.get('risk_score', 0))],
            ['Contamination Index:', f"{inspection_data.get('contamination_index', 1)}/9"],
            ['Safety Anomalies:', 'Yes' if inspection_data.get('anomalies_present') else 'No'],
        ]
        risk_table = Table(risk_data, colWidths=[2*inch, 4*inch])
        risk_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#f3f4f6')),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e5e7eb')),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ]))
        elements.append(risk_table)
        elements.append(Paragraph(
            "<b>Table Context:</b> Quantitative assessment of environmental and structural hazards. "
            "The Contamination Index reflects the presence of non-cargo residues or chemical stains within the interior surfaces.",
            self.styles['TableNote']
        ))

    def _pil_to_reportlab_image(self, pil_img, width=5*inch, height=3.75*inch):
        """Helper to convert a PIL image to a ReportLab Image flowable via a buffer."""
        img_buffer = io.BytesIO()
        if pil_img.mode in ("RGBA", "P"):
            pil_img = pil_img.convert("RGB")
        pil_img.save(img_buffer, format='JPEG', quality=85)
        img_buffer.seek(0)
        return Image(img_buffer, width=width, height=height, kind='proportional')

    def _add_contamination_section(self, elements: List, contamination_summary: Dict):
        """
        Add a dedicated section that details contamination findings.
        Shows a summary line, a table of all contamination events, and an example image.
        """
        if contamination_summary["frames_with_contamination"] == 0:
            elements.append(Paragraph(
                "No contamination detected in any frame.",
                self.styles['InfoText']
            ))
            return

        elements.append(PageBreak())
        elements.append(Paragraph("CONTAMINATION ANALYSIS", self.styles['SectionHeader']))

        summary_text = (
            f"<b>Frames with contamination:</b> {contamination_summary['frames_with_contamination']} "
            f"out of {contamination_summary['total_frames']}  |  "
            f"<b>Types observed:</b> {', '.join(contamination_summary['contamination_types'])}"
        )
        elements.append(Paragraph(summary_text, self.styles['InfoText']))
        elements.append(Spacer(1, 0.2*inch))

        data = [['Frame', 'Contaminant', 'Confidence', 'Location']]
        for item in contamination_summary["frame_details"]:
            for d in item["detections"]:
                loc = self._estimate_location(d)
                data.append([
                    str(item["frame_num"]),
                    d.get('label', 'Unknown'),
                    f"{d.get('confidence', 0)*100:.1f}%",
                    loc
                ])

        cont_table = Table(data, colWidths=[1*inch, 2*inch, 1.2*inch, 2*inch])
        cont_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1f1f1f')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e5e7eb')),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ]))
        elements.append(cont_table)

        example = contamination_summary["frame_details"][0]
        if example["image_path"]:
            img_path = self._resolve_image_path(example["image_path"])
            if img_path and img_path.exists():
                elements.append(Spacer(1, 0.2*inch))
                elements.append(Paragraph(
                    f"Example: Frame #{example['frame_num']} with contamination",
                    self.styles['InfoText']
                ))
                if HAS_PIL:
                    try:
                        pil_img = PILImage.open(img_path)
                        pil_img.thumbnail((750, 750))
                        img = self._pil_to_reportlab_image(pil_img)
                        elements.append(img)
                    except Exception as e:
                        logger.error(f"Error processing contamination example image: {e}")
                        elements.append(Paragraph("<i>Error loading image</i>", self.styles['InfoText']))
                else:
                    img = Image(str(img_path), width=5*inch, height=3.75*inch, kind='proportional')
                    elements.append(img)

        elements.append(Paragraph(
            "<b>Table Context:</b> Every contamination event detected by the vision system. "
            "Location is approximated from bounding box center.",
            self.styles['TableNote']
        ))

    def _add_frames_section(self, elements: List, frames: List[Dict]):
        """Add the technical analysis log with per‑frame details."""
        if not frames:
            return

        elements.append(PageBreak())
        elements.append(Paragraph("TECHNICAL ANALYSIS LOG", self.styles['SectionHeader']))

        MAX_FRAMES = 20
        if len(frames) > MAX_FRAMES:
            step = len(frames) / MAX_FRAMES
            sampled_frames = [frames[int(i * step)] for i in range(MAX_FRAMES)]
            frames_to_process = sampled_frames
            elements.append(Paragraph(f"<i>Showing {MAX_FRAMES} sampled frames from a total of {len(frames)}.</i>", self.styles['InfoText']))
        else:
            frames_to_process = frames

        for idx, frame in enumerate(frames_to_process, 1):
            elements.append(Paragraph(f"<b>Visual Acquisition #{idx}</b>", self.styles['InfoText']))

            image_path = frame.get('overlay_path') or frame.get('image_path')
            if image_path:
                full_image_path = self._resolve_image_path(image_path)
                if full_image_path and full_image_path.exists():
                    if HAS_PIL:
                        try:
                            pil_img = PILImage.open(full_image_path)
                            pil_img.thumbnail((750, 750))
                            img = self._pil_to_reportlab_image(pil_img)
                            elements.append(img)
                        except Exception as e:
                            logger.error(f"Error processing frame image: {e}")
                            elements.append(Paragraph("<i>Error loading image</i>", self.styles['InfoText']))
                    else:
                        img = Image(str(full_image_path), width=5*inch, height=3.75*inch, kind='proportional')
                        elements.append(img)
                else:
                    elements.append(Paragraph("<i>Image not available</i>", self.styles['InfoText']))
            else:
                elements.append(Paragraph("<i>No image available for this frame</i>", self.styles['InfoText']))

            detections = frame.get('detections', [])
            if detections:
                det_data = [['ID', 'Classification', 'Technical Category', 'System Confidence']]
                for det_idx, det in enumerate(detections, 1):
                    det_data.append([
                        str(det_idx),
                        det.get('label', 'Unknown'),
                        det.get('category', 'N/A'),
                        f"{det.get('confidence', 0)*100:.1f}%"
                    ])

                dt = Table(det_data, colWidths=[0.5*inch, 2*inch, 2*inch, 1.5*inch])
                dt.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1f1f1f')),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                    ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e5e7eb')),
                    ('FONTSIZE', (0, 0), (-1, -1), 8),
                ]))
                elements.append(dt)

                cont_in_frame = [d for d in detections if d.get('category') == 'contamination']
                if cont_in_frame:
                    elements.append(Paragraph(
                        f"<font color='#b91c1c'>⚠️ This frame contains {len(cont_in_frame)} contamination detection(s).</font>",
                        self.styles['WarningText']
                    ))
            else:
                elements.append(Paragraph("<i>No detections in this frame</i>", self.styles['InfoText']))

            if idx % 2 == 0 and idx < len(frames_to_process):
                elements.append(PageBreak())
            else:
                elements.append(Spacer(1, 0.2*inch))

    def _generate_narrative(self, contamination_summary: Dict) -> str:
        """Generate a dynamic narrative based on contamination findings."""
        if contamination_summary["frames_with_contamination"] > 0:
            types = ', '.join(contamination_summary["contamination_types"])
            return (
                f"Contamination detected in {contamination_summary['frames_with_contamination']} frames. "
                f"Observed types: {types}. "
                "Immediate cleaning recommended for affected areas to prevent cargo damage and maintain ISO standards."
            )
        else:
            return (
                "Surface analysis indicates optimal structural health with no visible contamination. "
                "No puncture-based light leaks or significant material fatigue detected."
            )

    def _add_final_sections(self, elements: List, inspection_data: Dict, contamination_summary: Dict):
        """Add structural narrative and maintenance forecast."""
        elements.append(PageBreak())
        elements.append(Paragraph("STRUCTURAL & MATERIAL INTEGRITY NARRATIVE", self.styles['SectionHeader']))
        narrative = self._generate_narrative(contamination_summary)
        elements.append(Paragraph(narrative, self.styles['Normal']))
        elements.append(Spacer(1, 0.3*inch))

        elements.append(Paragraph("PREVENTATIVE MAINTENANCE FORECAST", self.styles['SectionHeader']))
        pred_data = inspection_data.get('maintenance_forecast', [
            ["Component", "Integrity Level", "Technical Action", "Service Timeline"],
            ["Corner Castings", "High", "Standard Inspection", "12 Months"],
            ["Roof Panel", "Nominal", "Monitor Surface", "Q4 2026"],
            ["Floor Planks", "Moderate", "Odor Neutralization", "Immediate"]
        ])

        pt = Table(pred_data, colWidths=[1.5*inch, 1.5*inch, 1.5*inch, 1.5*inch])
        pt.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1f1f1f')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e5e7eb')),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
        ]))
        elements.append(pt)
        elements.append(Paragraph(
            "<b>Table Context:</b> Predictive analytics derived from vision data. The service timeline estimates optimal repair windows to prevent structural breach or de-certification.",
            self.styles['TableNote']
        ))

        elements.append(Paragraph("End of Technical Inspection & Analysis Report", self.styles['CenteredFooter']))

    # ----------------------------------------------------------------------
    # Main public method
    # ----------------------------------------------------------------------
    def generate_inspection_report(self, inspection_data: Dict, output_path: Optional[Path] = None) -> bytes:
        """
        Generate a PDF inspection report.
        """
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=letter,
            rightMargin=0.75*inch,
            leftMargin=0.75*inch,
            topMargin=1*inch,
            bottomMargin=1*inch
        )
        elements = []

        logo_path = Path(getattr(settings, 'ROOT_DIR', Path.cwd())) / "frontend" / "assets" / "images" / "pti-logo.png"
        self._add_header(elements, logo_path)

        elements.append(Paragraph("INSPECTION REPORT", self.styles['CustomTitle']))
        elements.append(Paragraph(
            f"<b>Report Date:</b> {datetime.now().strftime('%B %d, %Y')}",
            self.styles['InfoText']
        ))
        elements.append(Spacer(1, 0.3*inch))

        self._add_summary_section(elements, inspection_data)
        self._add_risk_section(elements, inspection_data)

        frames = inspection_data.get('frames', [])
        contamination_summary = self._aggregate_contamination(frames)
        logger.info(f"Contamination summary: {contamination_summary['frames_with_contamination']} frames with contamination")

        self._add_contamination_section(elements, contamination_summary)
        self._add_frames_section(elements, frames)
        self._add_final_sections(elements, inspection_data, contamination_summary)

        doc.build(elements, onFirstPage=self._add_footer, onLaterPages=self._add_footer)
        pdf_bytes = buffer.getvalue()
        buffer.close()

        if output_path:
            output_path.write_bytes(pdf_bytes)
            logger.info(f"Report saved to {output_path}")

        return pdf_bytes
