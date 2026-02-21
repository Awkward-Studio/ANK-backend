import uuid
import io
from django.utils import timezone
from django.core.files.base import ContentFile
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


def generate_mou_pdf(mou):
    """Generate a simple PDF for the accepted MoU."""
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", "B", 16)
    pdf.cell(0, 10, "Memorandum of Understanding", ln=True, align="C")
    pdf.ln(10)
    
    pdf.set_font("Arial", "", 12)
    pdf.cell(0, 10, f"Agreement ID: {mou.id}", ln=True)
    pdf.cell(0, 10, f"Freelancer: {mou.allocation.freelancer.name}", ln=True)
    pdf.cell(0, 10, f"Event: {mou.allocation.event_department.event.name}", ln=True)
    pdf.cell(0, 10, f"Department: {mou.allocation.event_department.department.name}", ln=True)
    pdf.ln(5)
    
    pdf.set_font("Arial", "B", 12)
    pdf.cell(0, 10, "Terms and Conditions:", ln=True)
    pdf.set_font("Arial", "", 10)
    terms = mou.template_data.get("terms", "Standard terms apply.")
    pdf.multi_cell(0, 10, terms)
    pdf.ln(5)
    
    pdf.set_font("Arial", "B", 12)
    pdf.cell(0, 10, "Commercials:", ln=True)
    pdf.set_font("Arial", "", 12)
    cost_sheet = mou.allocation.cost_sheet
    pdf.cell(0, 10, f"Negotiated Rate: {cost_sheet.negotiated_rate}", ln=True)
    pdf.cell(0, 10, f"Days Planned: {cost_sheet.days_planned}", ln=True)
    pdf.cell(0, 10, f"Total Estimated Cost: {cost_sheet.total_estimated_cost}", ln=True)
    pdf.ln(10)
    
    pdf.cell(0, 10, f"Accepted electronically on: {mou.accepted_at.strftime('%Y-%m-%d %H:%M:%S')}", ln=True)
    pdf.cell(0, 10, f"Freelancer Signature: [Digitally Accepted]", ln=True)
    
    # Save PDF to memory buffer
    pdf_output = pdf.output(dest='S')
    return pdf_output


@document_api_view(
    {
        "get": doc_retrieve(
            response=None,  # Custom response structure
            description="Fetch MoU details using the secure token",
            tags=["Manpower: Public MoU"],
        ),
        "post": doc_create(
            request=None,  # Custom request body {"action": "accept"|"reject"}
            response=None,
            description="Accept or reject an MoU using the secure token",
            tags=["Manpower: Public MoU"],
        )
    }
)
@api_view(["GET", "POST"])
@permission_classes([AllowAny])
def public_mou_interaction(request, token):
    """Fetch details or respond to an MoU using the secure token."""
    try:
        mou = MoU.objects.select_related(
            "allocation__freelancer",
            "allocation__event_department__event",
            "allocation__event_department__department",
            "allocation__cost_sheet"
        ).get(secure_token=token)
    except (MoU.DoesNotExist, ValueError):
        return Response(
            {"error": "Invalid or expired token"}, status=status.HTTP_404_NOT_FOUND
        )

    if request.method == "GET":
        # Return only necessary information for the freelancer
        data = {
            "id": mou.id,
            "status": mou.status,
            "template_data": mou.template_data,
            "freelancer_name": mou.allocation.freelancer.name,
            "event_name": mou.allocation.event_department.event.name,
            "department_name": mou.allocation.event_department.department.name,
            "negotiated_rate": mou.allocation.cost_sheet.negotiated_rate,
            "days_planned": mou.allocation.cost_sheet.days_planned,
            "total_estimated_cost": mou.allocation.cost_sheet.total_estimated_cost,
        }
        return Response(data)

    elif request.method == "POST":
        if mou.status in ["accepted", "rejected"]:
            return Response(
                {"error": "MoU has already been responded to"}, status=status.HTTP_400_BAD_REQUEST
            )

        action = request.data.get("action")
        if action not in ["accept", "reject"]:
            return Response(
                {"error": "Invalid action. Use 'accept' or 'reject'"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if action == "accept":
            mou.status = "accepted"
            mou.accepted_at = timezone.now()
            
            # Generate PDF
            pdf_content = generate_mou_pdf(mou)
            filename = f"MoU_{mou.allocation.freelancer.name.replace(' ', '_')}_{mou.id}.pdf"
            mou.signed_pdf.save(filename, ContentFile(pdf_content), save=False)
            
            # TODO: Notification - Send confirmation and PDF link via Email/WhatsApp to freelancer and admin
        else:
            mou.status = "rejected"

        mou.save()
        return Response({"status": mou.status})
