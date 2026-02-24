import uuid
import io
import logging
from django.utils import timezone
from django.core.files.base import ContentFile
from django.http import HttpResponse
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from fpdf import FPDF
from .models import MoU
from utils.swagger import (
    document_api_view,
    doc_retrieve,
    doc_create,
)

logger = logging.getLogger(__name__)

class MOU_PDF(FPDF):
    def header(self):
        self.set_font("helvetica", "B", 10)
        self.set_text_color(150)
        self.set_x(self.l_margin)
        self.cell(w=self.epw, h=10, txt="ANK ENTERTAINMENT LLP - CONFIDENTIAL", align="R")
        self.ln(10)

    def footer(self):
        self.set_y(-15)
        self.set_font("helvetica", "I", 8)
        self.set_text_color(150)
        self.set_x(self.l_margin)
        self.cell(w=self.epw, h=10, txt=f"Page {self.page_no()}", align="C")


def clean_text(text):
    if not text:
        return ""
    replacements = {
        "\u2013": "-", "\u2014": "--", "\u2018": "'", "\u2019": "'",
        "\u201c": '"', "\u201d": '"', "\u2022": "*", "\u2026": "...",
        "\u00a0": " ",
    }
    for unicode_char, replacement in replacements.items():
        text = text.replace(unicode_char, replacement)
    return str(text).encode("latin-1", "replace").decode("latin-1")


def generate_mou_pdf(mou):
    pdf = MOU_PDF(orientation="P", unit="mm", format="A4")
    pdf.set_margins(20, 20, 20)
    pdf.add_page()
    epw = pdf.epw
    
    pdf.set_font("helvetica", "B", 16)
    pdf.set_x(pdf.l_margin)
    pdf.multi_cell(w=epw, h=10, txt=clean_text("MEMORANDUM OF UNDERSTANDING (MOU) & CONFIDENTIALITY AGREEMENT"), align="C")
    pdf.ln(5)
    
    pdf.set_font("helvetica", "B", 11)
    pdf.set_x(pdf.l_margin)
    pdf.multi_cell(w=epw, h=6, txt=clean_text("Between ANK ENTERTAINMENT LLP (A New Knot) and The Freelancer / Consultant"), align="C")
    pdf.ln(10)
    
    pdf.set_font("helvetica", "", 10)
    date_str = mou.created_at.strftime("%d %B %Y")
    pdf.set_x(pdf.l_margin)
    pdf.multi_cell(w=epw, h=6, txt=clean_text(f"This Memorandum of Understanding (\"MOU\") is executed on this {date_str} (\"Effective Date\") by and between:"))
    pdf.ln(4)
    
    pdf.set_font("helvetica", "B", 10)
    pdf.set_x(pdf.l_margin)
    company_text = ("ANK ENTERTAINMENT LLP (A New Knot), a limited liability partnership registered under the LLP Act, "
                    "having its principal office at 802, Sun Paradise Plaza, Opp. Kamla Mills, Senapati Bapat Marg, Lower Parel, Mumbai - 400013, "
                    "and registered address at GA/1, Tarang Society, Mogal Lane, Mahim, Mumbai - 400016, (hereinafter referred to as the \"Company\"),")
    pdf.multi_cell(w=epw, h=6, txt=clean_text(company_text))
    pdf.ln(4)
    
    pdf.set_font("helvetica", "", 10)
    pdf.set_x(pdf.l_margin)
    pdf.multi_cell(w=epw, h=6, txt=clean_text("AND"), align="C")
    pdf.ln(4)
    
    f = mou.allocation.freelancer
    pdf.set_font("helvetica", "B", 10)
    f_info = (f"{f.name},\n"
              f"S/o / D/o {f.parent_name or '____________________'}\n"
              f"Residing at {f.address or '____________________'}\n"
              f"Bearing PAN / Aadhar No. {f.id_number or '____________________'} (hereinafter referred to as the \"Freelancer\").")
    pdf.set_x(pdf.l_margin)
    pdf.multi_cell(w=epw, h=6, txt=clean_text(f_info))
    pdf.ln(6)
    
    pdf.set_font("helvetica", "", 10)
    pdf.set_x(pdf.l_margin)
    pdf.multi_cell(w=epw, h=6, txt=clean_text("The Company and the Freelancer shall collectively be referred to as the \"Parties.\""))
    pdf.ln(8)
    
    sections = [
        ("1. Purpose, Scope & Applicability", "1.1 This MOU outlines the understanding between the Company and the Freelancer for services to be rendered only for those specific events and assignments confirmed by ANK Entertainment LLP through official digital communication channels (email, WhatsApp, or any other approved platform), where the dates, and remuneration have been mutually acknowledged.\n1.2 Each confirmed event engagement shall be deemed an individual assignment under the framework of this MOU.\n1.3 This MOU establishes the professional expectations, confidentiality obligations, and conduct standards applicable to all assignments mutually decided and accepted during the period of engagement.\n1.4 The Company reserves the right to discontinue the engagement if the Freelancer fails to adhere to the terms of this MOU, breaches confidentiality, or conducts themselves in a manner inconsistent with the Company's values."),
        ("2. Payment Terms", "The Freelancer shall be compensated at a pre-agreed rate for each confirmed event. Payment shall be processed within 30 days of invoice submission post-event completion, subject to satisfactory performance. Travel Days will be compensated only if active work is assigned. Non-working travel days will not be billable."),
        ("3. Confidentiality & Non-Disclosure Agreement (NDA)", "3.1 The Freelancer acknowledges that they may have access to confidential information, including event concepts, client data, guest lists, creative plans, and budgets.\n3.2 The Freelancer agrees to maintain complete confidentiality, refrain from unauthorized recording or sharing of event content, and handle client property responsibly."),
        ("4. Professional Conduct During Events", "No unauthorized photography or videography. No sharing of event material on social media. Maintain strict confidentiality. Focus on assigned responsibilities. Maintain professional grooming and body language. Mobile phones must be on silent mode. Consumption of alcohol or tobacco in guest areas is strictly prohibited."),
        ("5. Ownership of Work", "All creative outputs, operational documentation, and intellectual materials produced during the engagement shall remain the exclusive property of ANK ENTERTAINMENT LLP."),
        ("6. General Terms", "Severability: If any clause is deemed invalid, the rest remain in effect.\nWaiver: Failure to enforce any clause is not a waiver of rights.\nJurisdiction: This MOU shall be governed by the laws of India, and the courts of Mumbai shall have exclusive jurisdiction.")
    ]
    
    for title, text in sections:
        pdf.set_font("helvetica", "B", 10)
        pdf.set_x(pdf.l_margin)
        pdf.multi_cell(w=epw, h=6, txt=clean_text(title))
        pdf.set_font("helvetica", "", 10)
        pdf.set_x(pdf.l_margin)
        pdf.multi_cell(w=epw, h=5, txt=clean_text(text))
        pdf.ln(4)
        
    pdf.ln(10)
    pdf.set_font("helvetica", "I", 10)
    pdf.set_x(pdf.l_margin)
    pdf.multi_cell(w=epw, h=5, txt=clean_text("By signing this MOU, the Freelancer confirms having read, understood, and agreed to the terms herein, applicable only to the events and dates officially confirmed by ANK Entertainment LLP via digital communication."))
    pdf.ln(15)
    
    pdf.set_font("helvetica", "B", 10)
    y_before = pdf.get_y()
    
    # Left Column
    pdf.set_x(pdf.l_margin)
    pdf.multi_cell(w=epw/2 - 5, h=5, txt=clean_text("For ANK ENTERTAINMENT LLP\nName: Sahitya Shetty\nDesignation: Assistant Manager - HR\nSignature: [Digitally Signed]\nDate: " + mou.created_at.strftime("%d/%m/%Y")))
    
    # Right Column
    pdf.set_xy(pdf.l_margin + epw/2 + 5, y_before)
    accepted_date = mou.accepted_at.strftime("%d/%m/%Y") if mou.accepted_at else "[Pending]"
    sig_text = "[Digitally Accepted]" if mou.accepted_at else "________________________"
    pdf.multi_cell(w=epw/2 - 5, h=5, txt=clean_text(f"For Freelancer / Consultant\nName: {f.name}\nSignature: {sig_text}\nDate: {accepted_date}"))
    
    return bytes(pdf.output())


@api_view(["GET"])
@permission_classes([AllowAny])
def public_mou_pdf_download(request, token):
    try:
        mou = MoU.objects.select_related("allocation__freelancer", "allocation__event_department__event", "allocation__event_department__department", "allocation__cost_sheet").get(secure_token=token)
    except (MoU.DoesNotExist, ValueError):
        return HttpResponse("Invalid or expired token", status=404)
    try:
        pdf_content = generate_mou_pdf(mou)
        filename = f"MoU_{mou.allocation.freelancer.name.replace(' ', '_')}.pdf"
        response = HttpResponse(pdf_content, content_type="application/pdf")
        response["Content-Disposition"] = f'attachment; filename="{filename}"'
        return response
    except Exception as e:
        logger.exception("Error generating download PDF")
        return HttpResponse(f"Error generating PDF: {str(e)}", status=500)


@document_api_view({
    "get": doc_retrieve(response=None, description="Fetch MoU details using secure token", tags=["Manpower: Public MoU"]),
    "post": doc_create(request=None, response=None, description="Accept or reject MoU using secure token", tags=["Manpower: Public MoU"])
})
@api_view(["GET", "POST"])
@permission_classes([AllowAny])
def public_mou_interaction(request, token):
    try:
        mou = MoU.objects.select_related("allocation__freelancer", "allocation__event_department__event", "allocation__event_department__department", "allocation__cost_sheet").get(secure_token=token)
    except (MoU.DoesNotExist, ValueError):
        return Response({"error": "Invalid or expired token"}, status=status.HTTP_404_NOT_FOUND)
    if mou.expires_at and mou.expires_at < timezone.now():
        return Response({"error": "MoU link has expired"}, status=status.HTTP_410_GONE)
    expected_code = (mou.access_code or "").strip()
    provided_code = str(request.query_params.get("code") or request.data.get("access_code", "")).strip()
    if expected_code and provided_code != expected_code:
        return Response({"error": "Access code required or invalid"}, status=status.HTTP_403_FORBIDDEN)
    if request.method == "GET":
        data = {
            "id": mou.id, "status": mou.status, "template_data": mou.template_data,
            "freelancer_name": mou.allocation.freelancer.name, "skill_category": mou.allocation.freelancer.skill_category,
            "event_name": mou.allocation.event_department.event.name, "department_name": mou.allocation.event_department.department.name,
            "start_date": mou.allocation.start_date, "end_date": mou.allocation.end_date,
            "cost_sheet": {
                "negotiated_rate": mou.allocation.cost_sheet.negotiated_rate, "days_planned": mou.allocation.cost_sheet.days_planned,
                "daily_allowance": mou.allocation.cost_sheet.daily_allowance, "total_estimated_cost": mou.allocation.cost_sheet.total_estimated_cost,
            },
            "expires_at": mou.expires_at, "requires_access_code": bool(expected_code),
            "signed_pdf_url": f"/api/manpower/public/mou/{token}/pdf/" if mou.status == "accepted" else None,
            "download_url": f"/api/manpower/public/mou/{token}/pdf/",
        }
        return Response(data)
    elif request.method == "POST":
        if mou.status in ["accepted", "rejected"]:
            return Response({"error": "MoU has already been responded to"}, status=status.HTTP_400_BAD_REQUEST)
        action = request.data.get("action")
        if action not in ["accept", "reject"]:
            return Response({"error": "Invalid action. Use 'accept' or 'reject'"}, status=status.HTTP_400_BAD_REQUEST)
        try:
            if action == "accept":
                mou.status = "accepted"
                mou.accepted_at = timezone.now()
            else:
                mou.status = "rejected"
            mou.save()
            return Response({"status": mou.status, "signed_pdf_url": f"/api/manpower/public/mou/{token}/pdf/" if mou.status == "accepted" else None})
        except Exception as e:
            logger.exception("Error processing MoU response")
            return Response({"error": f"Internal server error: {str(e)}"}, status=500)
