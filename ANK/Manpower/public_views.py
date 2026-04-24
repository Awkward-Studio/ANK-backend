import uuid
import io
import os
import logging
from django.utils import timezone
from django.core.files.base import ContentFile
from django.http import HttpResponse
from django.conf import settings
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from fpdf import FPDF
from .models import MoU, InvoiceWorkflow
from utils.swagger import (
    document_api_view,
    doc_retrieve,
    doc_create,
)

logger = logging.getLogger(__name__)

def num2words_indian(number):
    """
    Convert a number to Indian system words (Lakhs, Crores)
    """
    units = ['', 'One', 'Two', 'Three', 'Four', 'Five', 'Six', 'Seven', 'Eight', 'Nine']
    teens = ['Ten', 'Eleven', 'Twelve', 'Thirteen', 'Fourteen', 'Fifteen', 'Sixteen', 'Seventeen', 'Eighteen', 'Nineteen']
    tens = ['', 'Ten', 'Twenty', 'Thirty', 'Forty', 'Fifty', 'Sixty', 'Seventy', 'Eighty', 'Ninety']

    def format_hundreds(n):
        res = ""
        if n >= 100:
            res += units[n // 100] + " Hundred "
            n %= 100
        if n >= 10 and n <= 19:
            res += teens[n - 10]
        elif n >= 20 or n == 10:
            res += tens[n // 10] + " " + units[n % 10]
        else:
            res += units[n]
        return res.strip()

    if number == 0: return "Zero"

    number = int(number)
    parts = []

    if number >= 10000000:
        parts.append(format_hundreds(number // 10000000) + " Crore")
        number %= 10000000
    if number >= 100000:
        parts.append(format_hundreds(number // 100000) + " Lakh")
        number %= 100000
    if number >= 1000:
        parts.append(format_hundreds(number // 1000) + " Thousand")
        number %= 1000
    if number > 0:
        parts.append(format_hundreds(number))

    return " ".join(parts).strip() + " Only"


class INVOICE_PDF(FPDF):
    def header(self):
        # Logo
        logo_path = os.path.join(settings.BASE_DIR, "static", "ank_logo_orange.png")
        if os.path.exists(logo_path):
            self.image(logo_path, x=self.l_margin, y=10, w=40)

        self.set_font("helvetica", "B", 10)
        self.set_text_color(150)
        self.set_x(self.l_margin)
        self.cell(w=self.epw, h=10, txt="TAX INVOICE", align="R")
        self.ln(15)

    def footer(self):
        self.set_y(-15)
        self.set_font("helvetica", "I", 8)
        self.set_text_color(150)
        self.set_x(self.l_margin)
        self.cell(w=self.epw, h=10, txt=f"Page {self.page_no()}", align="C")


def generate_invoice_pdf(invoice):
    pdf = INVOICE_PDF(orientation="P", unit="mm", format="A4")
    pdf.set_margins(20, 20, 20)
    pdf.add_page()
    epw = pdf.epw

    f = invoice.freelancer
    adj = invoice.adjustment
    cost = invoice.adjustment.allocation.cost_sheet

    # 1. Parties Section
    pdf.set_font("helvetica", "B", 10)
    y_parties = pdf.get_y()

    # LEFT: Freelancer (Provider)
    pdf.set_x(pdf.l_margin)
    pdf.multi_cell(w=epw/2 - 5, h=5, txt=clean_text(f"NAME: {f.name}\nADDRESS: {f.address or 'N/A'}\nMOBILE: {f.contact_phone or 'N/A'}\nE-MAIL: {f.email or 'N/A'}\n{f.id_type}.NO: {f.id_number or 'N/A'}"))

    # RIGHT: Company (Receiver)
    pdf.set_xy(pdf.l_margin + epw/2 + 5, y_parties)
    pdf.multi_cell(w=epw/2 - 5, h=5, txt=clean_text("ANK ENTERTAINMENT LLP\n802, Sun Paradise Business Plaza,\nSenapati Bapat Marg, Opp. Kamla Mills,\nRailway Colony, Lower Parel, Mumbai - 400013"), align="R")
    pdf.ln(10)

    # 2. Metadata Section
    pdf.set_font("helvetica", "B", 9)
    pdf.cell(w=epw*0.5, h=6, txt=clean_text(f"INV.NO .: {invoice.invoice_number}"))
    pdf.cell(w=epw*0.5, h=6, txt=clean_text(f"DATE: {invoice.created_at.strftime('%d-%m-%Y')}"), align="R", ln=1)

    pdf.set_font("helvetica", "", 9)
    pdf.cell(w=epw, h=6, txt=clean_text(f"NAME OF DEPARTMENT: {invoice.event_department.department.name.upper()}"), ln=1)

    periods_str = ", ".join([f"{p['start']} to {p['end']}" for p in adj.engagement_periods]) if adj.engagement_periods else "N/A"
    pdf.cell(w=epw, h=6, txt=clean_text(f"PERIOD OF SERVICE ( DATES ): {periods_str}"), ln=1)
    pdf.cell(w=epw, h=6, txt=clean_text(f"NO.OF WORKING DAYS: {adj.total_engagement_days}"), ln=1)

    rate = adj.override_negotiated_rate if adj.override_negotiated_rate else cost.negotiated_rate
    pdf.cell(w=epw, h=6, txt=clean_text(f"Rs.{float(rate):,.2f}/- per day"), ln=1)
    pdf.ln(4)

    # 3. Main Service Table
    pdf.set_font("helvetica", "B", 9)
    pdf.set_fill_color(245, 245, 245)
    pdf.cell(w=epw*0.5, h=8, txt="NATURE OF SERVICE", border=1, fill=True)
    pdf.cell(w=epw*0.15, h=8, txt="DAYS", border=1, fill=True, align="C")
    pdf.cell(w=epw*0.15, h=8, txt="RATE", border=1, fill=True, align="C")
    pdf.cell(w=epw*0.2, h=8, txt="TOTAL", border=1, fill=True, align="R")
    pdf.ln()

    pdf.set_font("helvetica", "", 9)
    # Line 1: Professional Fees
    pdf.cell(w=epw*0.5, h=8, txt=clean_text(f"{invoice.event.name} @ {invoice.event.venue or 'Venue TBD'}"), border=1)
    pdf.cell(w=epw*0.15, h=8, txt=str(adj.total_engagement_days), border=1, align="C")
    pdf.cell(w=epw*0.15, h=8, txt=f"{float(rate):,.2f}", border=1, align="C")
    fees_total = float(adj.total_engagement_days * rate)
    pdf.cell(w=epw*0.2, h=8, txt=f"{fees_total:,.2f}", border=1, align="R")
    pdf.ln()

    # Sub Total (Professional Fees only)
    pdf.set_font("helvetica", "B", 9)
    pdf.cell(w=epw*0.8, h=8, txt="SUB TOTAL", border=1, align="R")
    pdf.cell(w=epw*0.2, h=8, txt=f"{fees_total:,.2f}", border=1, align="R")
    pdf.ln()

    # Travelling
    pdf.set_font("helvetica", "", 9)
    total_travel = float(cost.travel_costs) + float(adj.travel_adjustments)
    pdf.cell(w=epw*0.8, h=8, txt="TRAVELLING - Reimbursments & Adjustments (Supporting must)", border=1)
    pdf.cell(w=epw*0.2, h=8, txt=f"{total_travel:,.2f}", border=1, align="R")
    pdf.ln()

    # F & B
    pdf.cell(w=epw*0.8, h=8, txt="F & B - Meal Logistics & Per Diem (Supporting must)", border=1)
    pdf.cell(w=epw*0.2, h=8, txt=f"{float(adj.actual_meal_allowance):,.2f}", border=1, align="R")
    pdf.ln()

    # Misc
    if float(adj.other_adjustments) != 0:
        pdf.cell(w=epw*0.8, h=8, txt="MISCELLANEOUS / PENALTIES", border=1)
        pdf.cell(w=epw*0.2, h=8, txt=f"{float(adj.other_adjustments):,.2f}", border=1, align="R")
        pdf.ln()

    # Grand Total
    pdf.set_font("helvetica", "B", 10)
    pdf.cell(w=epw*0.8, h=10, txt="GRAND TOTAL", border=1, align="R")
    pdf.cell(w=epw*0.2, h=10, txt=f"{float(invoice.payable_amount):,.2f}", border=1, align="R")
    pdf.ln(8)

    # Amount in words
    pdf.ln(2)
    pdf.set_font("helvetica", "B", 9)
    words = num2words_indian(invoice.payable_amount)
    pdf.set_x(pdf.l_margin)
    pdf.multi_cell(w=epw, h=6, txt=clean_text(f"AMOUNT IN WORDS: {words}"), align="L")
    pdf.ln(10)

    # 4. Bank Details & Signature
    y_bank = pdf.get_y()
    pdf.set_font("helvetica", "", 9)
    bank_text = (f"A/C. NAME: {f.bank_account_name or 'N/A'}\n"
                 f"NAME OF BANK: {f.bank_name or 'N/A'}\n"
                 f"A/C. NO.: {f.bank_account_number or 'N/A'}\n"
                 f"BRANCH: {f.bank_branch or 'N/A'}\n"
                 f"IFSC CODE: {f.bank_ifsc or 'N/A'}")
    pdf.multi_cell(w=epw/2, h=5, txt=clean_text(bank_text))

    pdf.set_xy(pdf.l_margin + epw/2, y_bank)
    pdf.set_font("helvetica", "B", 9)
    pdf.multi_cell(w=epw/2, h=5, txt=clean_text("SIGNATURE OF FREELANCER\n\nMANDATORY"), align="R")
    pdf.ln(15)

    # 5. Approvals Footer
    pdf.set_font("helvetica", "B", 8)
    pdf.cell(w=epw/3, h=6, txt="Hired By", border="T", align="C")
    pdf.cell(w=epw/3, h=6, txt="Sanctioned By", border="T", align="C")
    pdf.cell(w=epw/3, h=6, txt="Approve By", border="T", align="C", ln=1)

    pdf.ln(10)
    pdf.cell(w=epw/2, h=6, txt="A/C. MANAGER", border="T", align="C")
    pdf.cell(w=epw/2, h=6, txt="SR.A/C MANAGER", border="T", align="C", ln=1)

    return bytes(pdf.output())



@api_view(["GET"])
@permission_classes([AllowAny])
def public_invoice_pdf_download(request, token):
    try:
        invoice = InvoiceWorkflow.objects.select_related(
            "freelancer", 
            "event", 
            "adjustment__allocation__cost_sheet"
        ).get(secure_token=token)
    except (InvoiceWorkflow.DoesNotExist, ValueError):
        return HttpResponse("Invalid or expired token", status=404)
    
    try:
        pdf_content = generate_invoice_pdf(invoice)
        filename = f"Invoice_{invoice.invoice_number}.pdf"
        response = HttpResponse(pdf_content, content_type="application/pdf")
        response["Content-Disposition"] = f'attachment; filename="{filename}"'
        return response
    except Exception as e:
        logger.exception("Error generating invoice PDF")
        return HttpResponse(f"Error generating PDF: {str(e)}", status=500)


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
    
    # Get dates with fallback
    start_date = mou.allocation.start_date
    end_date = mou.allocation.end_date
    if (not start_date or not end_date) and mou.allocation.requirement:
        req = mou.allocation.requirement
        start_date = start_date or getattr(req, 'start_date', None)
        end_date = end_date or getattr(req, 'end_date', None)
    
    date_range_str = "TBD"
    if start_date and end_date:
        date_range_str = f"{start_date.strftime('%d %b %Y')} to {end_date.strftime('%d %b %Y')}"
    
    duration = str(mou.allocation.cost_sheet.days_planned)

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
        ("1. Purpose, Scope & Applicability", f"1.1 This MOU outlines the understanding between the Company and the Freelancer for services to be rendered for the event '{mou.allocation.event_department.event.name}' during the period of {date_range_str} (Total Duration: {duration} days).\n1.2 Each confirmed event engagement shall be deemed an individual assignment under the framework of this MOU.\n1.3 This MOU establishes the professional expectations, confidentiality obligations, and conduct standards applicable to all assignments mutually decided and accepted during the period of engagement.\n1.4 The Company reserves the right to discontinue the engagement if the Freelancer fails to adhere to the terms of this MOU, breaches confidentiality, or conducts themselves in a manner inconsistent with the Company's values."),
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
    pdf.multi_cell(w=epw/2 - 5, h=5, txt=clean_text("For ANK ENTERTAINMENT LLP\nName: Divya Jain - Manager\nDesignation: Assistant Manager - HR\nSignature: [Digitally Signed]\nDate: " + mou.created_at.strftime("%d/%m/%Y")))
    
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
        mou = MoU.objects.select_related("allocation__freelancer", "allocation__event_department__event", "allocation__event_department__department", "allocation__cost_sheet", "allocation__requirement").get(secure_token=token)
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
        mou = MoU.objects.select_related("allocation__freelancer", "allocation__event_department__event", "allocation__event_department__department", "allocation__cost_sheet", "allocation__requirement").get(secure_token=token)
    except (MoU.DoesNotExist, ValueError):
        return Response({"error": "Invalid or expired token"}, status=status.HTTP_404_NOT_FOUND)
    if mou.expires_at and mou.expires_at < timezone.now():
        return Response({"error": "MoU link has expired"}, status=status.HTTP_410_GONE)
    expected_code = (mou.access_code or "").strip()
    provided_code = str(request.query_params.get("code") or request.data.get("access_code", "")).strip()
    if expected_code and provided_code != expected_code:
        return Response({"error": "Access code required or invalid"}, status=status.HTTP_403_FORBIDDEN)
    if request.method == "GET":
        # Fallback to requirement dates if allocation dates are missing
        start_date = mou.allocation.start_date
        end_date = mou.allocation.end_date
        
        if (not start_date or not end_date) and mou.allocation.requirement:
            req = mou.allocation.requirement
            if not start_date:
                start_date = getattr(req, 'start_date', None)
            if not end_date:
                end_date = getattr(req, 'end_date', None)

        data = {
            "id": mou.id, 
            "status": mou.status, 
            "template_data": mou.template_data,
            "freelancer_name": mou.allocation.freelancer.name, 
            "skill_category": mou.allocation.freelancer.skill_category,
            "event_name": mou.allocation.event_department.event.name, 
            "department_name": mou.allocation.event_department.department.name,
            "start_date": start_date, 
            "end_date": end_date,
            "cost_sheet": {
                "days_planned": mou.allocation.cost_sheet.days_planned,
            },
            "expires_at": mou.expires_at, 
            "requires_access_code": bool(expected_code),
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
                # Automatically confirm the allocation
                mou.allocation.status = "confirmed"
                mou.allocation.save()
            else:
                mou.status = "rejected"
            mou.save()
            return Response({"status": mou.status, "signed_pdf_url": f"/api/manpower/public/mou/{token}/pdf/" if mou.status == "accepted" else None})
        except Exception as e:
            logger.exception("Error processing MoU response")
            return Response({"error": f"Internal server error: {str(e)}"}, status=500)
