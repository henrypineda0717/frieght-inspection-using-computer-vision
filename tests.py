import json
import time
from datetime import datetime

# --- AI & PDF Libraries ---
import google.generativeai as genai

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib.enums import TA_CENTER

from reportlab.platypus import (
    SimpleDocTemplate,
    Table,
    TableStyle,
    Paragraph,
    Spacer,
    HRFlowable,
    PageBreak
)

# ==========================================
# 1. GEMINI API CONFIGURATION
# ==========================================
genai.configure(api_key="YOUR_FREE_GEMINI_API_KEY")


# ==========================================
# 2. SAMPLE JSON DATA
# ==========================================

EXTERIOR_JSON = """
{"container_id":"UNKNOWN","container_type":null,"status":"ok","detections":[{"label":"container_front","category":null,"confidence":0.8930565714836121,"bbox":{"x":100,"y":58,"w":239,"h":340},"severity":null,"defect_type":null,"model_source":"General","container_id":"UNKNOWN","iso_type":"0844","corners":[[341.25,389.3500061035156],[341.25,78.6500015258789],[110.5,69.54999542236328],[100.0999984741211,398.4499816894531]]}],"timestamp":"2026-03-03T20:18:29.447262","people_nearby":false,"door_status":null,"lock_boxes":[],"anomalies_present":false,"inspection_stage":"pre","diff":null,"scene_tags":[],"risk_score":0,"risk_explanations":[],"prewash_remarks":[],"resolved_remarks":[],"contamination_index":1,"contamination_label":"Low","contamination_scale":[],"scene_caption":null,"semantic_people_count":null,"anomaly_summary":null,"recommended_actions":[],"inspection_id":null}
"""

INTERIOR_JSON = """
{"container_id":"UNKNOWN","container_type":null,"status":"ok","detections":[{"label":"Rust","confidence":0.61,"model_source":"Damage"},{"label":"Rust","confidence":0.61,"model_source":"Damage"},{"label":"Dent","confidence":0.60,"model_source":"Damage"},{"label":"container_front","confidence":0.99,"model_source":"General"}],"timestamp":"2026-03-03T20:32:05.310199","inspection_stage":"pre","risk_score":2,"contamination_index":1,"contamination_label":"Low"}
"""


# ==========================================
# 3. DATA PROCESSING
# ==========================================

def process_inspection_data(json_data):

    damages = []
    general_parts = []

    for det in json_data.get("detections", []):

        if det.get("confidence", 0) < 0.30:
            continue

        if det.get("model_source") == "Damage":
            damages.append(det)
        else:
            general_parts.append(det)

    json_data["filtered_damages"] = damages
    json_data["structural_parts"] = general_parts
    json_data["is_damaged"] = len(damages) > 0

    return json_data


# ==========================================
# 4. REPORT SERVICE
# ==========================================

class ReportService:

    def __init__(self):

        self.styles = getSampleStyleSheet()
        self._setup_styles()

    def _setup_styles(self):

        self.styles.add(ParagraphStyle(
            name='CustomTitle',
            parent=self.styles['Heading1'],
            fontSize=26,
            alignment=TA_CENTER,
            spaceAfter=40
        ))

        self.styles.add(ParagraphStyle(
            name='SectionHeader',
            parent=self.styles['Heading2'],
            fontSize=14,
            spaceBefore=20,
            spaceAfter=10
        ))

        self.styles.add(ParagraphStyle(
            name='InfoText',
            parent=self.styles['Normal'],
            fontSize=10,
            spaceAfter=6
        ))


# ==========================================
# AI VIDEO ANALYSIS
# ==========================================

    def get_ai_video_review(self, video_path):

        if not video_path:
            return None

        print("Uploading video to Gemini...")

        video_file = genai.upload_file(path=video_path)

        while video_file.state.name == "PROCESSING":
            time.sleep(3)
            video_file = genai.get_file(video_file.name)

        model = genai.GenerativeModel("gemini-1.5-flash")

        prompt = """
        Analyze this container inspection video.
        Provide a professional inspection summary describing:
        - structural condition
        - contamination
        - damages
        - safety risks
        """

        response = model.generate_content([video_file, prompt])

        return response.text


# ==========================================
# MAIN REPORT GENERATOR
# ==========================================

    def generate_inspection_report(self, raw_json, filename, video_path=None):

        data = process_inspection_data(raw_json)

        if video_path:
            data["anomaly_summary"] = self.get_ai_video_review(video_path)

        doc = SimpleDocTemplate(filename, pagesize=letter)

        elements = []

# ==========================================
# COVER PAGE
# ==========================================

        elements.append(Paragraph(
            "CONTAINER INSPECTION REPORT",
            self.styles['CustomTitle']
        ))

        elements.append(Spacer(1, 0.4 * inch))

        cover_data = [

            ["Container ID", data.get("container_id", "UNKNOWN")],
            ["Inspection Stage", data.get("inspection_stage", "N/A")],
            ["Timestamp", data.get("timestamp", "N/A")],
            ["Contamination Level", data.get("contamination_label", "Low")],
            ["Inspection Result", "DAMAGED" if data["is_damaged"] else "CLEAR"]

        ]

        table = Table(cover_data, colWidths=[3 * inch, 3 * inch])

        table.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (0,-1), colors.lightgrey),
            ('FONTNAME', (0,0), (0,-1), 'Helvetica-Bold'),
            ('GRID', (0,0), (-1,-1), 0.5, colors.grey)
        ]))

        elements.append(table)

        elements.append(Spacer(1, 1 * inch))

        elements.append(Paragraph(
            "Generated by AI Container Inspection System",
            self.styles['InfoText']
        ))

        elements.append(PageBreak())


# ==========================================
# EXECUTIVE SUMMARY
# ==========================================

        elements.append(Paragraph(
            "EXECUTIVE SUMMARY",
            self.styles['SectionHeader']
        ))

        summary_data = [

            ["Total Defects", str(len(data["filtered_damages"]))],
            ["Structural Components", str(len(data["structural_parts"]))],
            ["Contamination Index", f"{data.get('contamination_index',1)}/9"],
            ["Risk Score", str(data.get("risk_score",0))]
        ]

        summary_table = Table(summary_data, colWidths=[3 * inch, 3 * inch])

        summary_table.setStyle(TableStyle([
            ('BACKGROUND',(0,0),(0,-1),colors.lightgrey),
            ('FONTNAME',(0,0),(0,-1),'Helvetica-Bold'),
            ('GRID',(0,0),(-1,-1),0.5,colors.grey)
        ]))

        elements.append(summary_table)

        elements.append(PageBreak())


# ==========================================
# CONTAINER INFORMATION
# ==========================================

        elements.append(Paragraph(
            "CONTAINER INFORMATION",
            self.styles['SectionHeader']
        ))

        info = [

            ["Container ID", data.get("container_id","UNKNOWN")],
            ["Inspection Stage", data.get("inspection_stage","N/A")],
            ["Timestamp", data.get("timestamp","N/A")],
            ["People Nearby", str(data.get("people_nearby",False))]
        ]

        info_table = Table(info, colWidths=[3 * inch, 3 * inch])

        info_table.setStyle(TableStyle([
            ('BACKGROUND',(0,0),(0,-1),colors.lightgrey),
            ('FONTNAME',(0,0),(0,-1),'Helvetica-Bold'),
            ('GRID',(0,0),(-1,-1),0.5,colors.grey)
        ]))

        elements.append(info_table)

        elements.append(Spacer(1,0.2*inch))


# ==========================================
# AI VIDEO ANALYSIS
# ==========================================

        if data.get("anomaly_summary"):

            elements.append(Paragraph(
                "AI VIDEO ANALYSIS",
                self.styles['SectionHeader']
            ))

            elements.append(Paragraph(
                data["anomaly_summary"],
                self.styles['InfoText']
            ))

        elements.append(PageBreak())


# ==========================================
# DAMAGE TABLE
# ==========================================

        elements.append(Paragraph(
            "DETECTED DAMAGES",
            self.styles['SectionHeader']
        ))

        if data["filtered_damages"]:

            rows = [["#", "Damage Type", "Confidence"]]

            for i, det in enumerate(data["filtered_damages"],1):

                conf = f"{det.get('confidence',0)*100:.1f}%"

                rows.append([i, det.get("label","Unknown"), conf])

            table = Table(rows, colWidths=[1*inch,3*inch,2*inch])

            table.setStyle(TableStyle([

                ('BACKGROUND',(0,0),(-1,0),colors.red),
                ('TEXTCOLOR',(0,0),(-1,0),colors.white),
                ('GRID',(0,0),(-1,-1),0.5,colors.grey)

            ]))

            elements.append(table)

        else:

            elements.append(Paragraph(
                "No significant damages detected.",
                self.styles['InfoText']
            ))


# ==========================================
# STRUCTURAL COMPONENTS
# ==========================================

        elements.append(Spacer(1,0.3*inch))

        elements.append(Paragraph(
            "STRUCTURAL COMPONENTS IDENTIFIED",
            self.styles['SectionHeader']
        ))

        rows = [["#", "Component", "Confidence"]]

        for i, det in enumerate(data["structural_parts"],1):

            conf = f"{det.get('confidence',0)*100:.1f}%"

            rows.append([i, det.get("label","Unknown"), conf])

        table = Table(rows, colWidths=[1*inch,3*inch,2*inch])

        table.setStyle(TableStyle([
            ('BACKGROUND',(0,0),(-1,0),colors.blue),
            ('TEXTCOLOR',(0,0),(-1,0),colors.white),
            ('GRID',(0,0),(-1,-1),0.5,colors.grey)
        ]))

        elements.append(table)

        elements.append(PageBreak())


# ==========================================
# CONTAMINATION ANALYSIS
# ==========================================

        elements.append(Paragraph(
            "CONTAMINATION ANALYSIS",
            self.styles['SectionHeader']
        ))

        text = f"""
        Contamination Index: {data.get('contamination_index',1)} / 9<br/>
        Classification: {data.get('contamination_label','Low')}
        """

        elements.append(Paragraph(text,self.styles['InfoText']))


# ==========================================
# RISK ASSESSMENT
# ==========================================

        elements.append(Paragraph(
            "RISK ASSESSMENT",
            self.styles['SectionHeader']
        ))

        risk_text = f"""
        Automated analysis estimated a risk score of
        {data.get('risk_score',0)}.
        """

        elements.append(Paragraph(risk_text,self.styles['InfoText']))


# ==========================================
# RECOMMENDED ACTIONS
# ==========================================

        elements.append(Paragraph(
            "RECOMMENDED ACTIONS",
            self.styles['SectionHeader']
        ))

        if data["is_damaged"]:

            actions = [

                "Inspect rust areas and apply anti-corrosion coating.",
                "Repair dents if structural deformation is confirmed.",
                "Clean contamination residues."

            ]

        else:

            actions = ["Container condition acceptable. No repair needed."]

        for a in actions:
            elements.append(Paragraph(f"• {a}", self.styles['InfoText']))

        doc.build(elements)

        print(f"Report generated: {filename}")


# ==========================================
# RUN SCRIPT
# ==========================================

if __name__ == "__main__":

    service = ReportService()

    print("Generating exterior report...")
    service.generate_inspection_report(
        json.loads(EXTERIOR_JSON),
        "Exterior_Report.pdf"
    )

    print("Generating interior report...")
    service.generate_inspection_report(
        json.loads(INTERIOR_JSON),
        "Interior_Report.pdf"
    )