import os
import django
import json

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ANK.settings')
django.setup()

from MessageTemplates.models import FlowBlueprint, MessageTemplate, WhatsAppPhoneNumber, WhatsAppBusinessAccount

def create_demo_flow():
    # 1. Ensure dummy WABA
    waba, _ = WhatsAppBusinessAccount.objects.get_or_create(
        waba_id="dummy_waba_id",
        defaults={"name": "Demo Business", "is_active": True}
    )
    
    # 2. Ensure dummy Phone
    phone, _ = WhatsAppPhoneNumber.objects.get_or_create(
        phone_number_id="dummy_phone_id",
        defaults={
            "business_account": waba,
            "display_phone_number": "+1234567890",
            "verified_name": "Demo Workspace",
            "is_active": True,
            "is_default": True
        }
    )

    # 3. Create dummy template (using correct fields for our MessageTemplate model)
    t1, _ = MessageTemplate.objects.get_or_create(
        name="dummy_rsvp_template",
        defaults={
            "message": "Hi, will you be attending the event? (Click Yes/No)",
            "desc": "A sample RSVP template for demonstration",
            "is_rsvp_message": True
        }
    )

    # 4. Graph JSON
    graph = {
        "nodes": [
            {
                "id": "node_trigger",
                "type": "trigger",
                "position": {"x": 50, "y": 250},
                "data": {
                    "triggerType": "manual",
                    "startWithTemplate": True,
                    "initialTemplateName": "dummy_rsvp_template",
                    "label": "Activation"
                }
            },
            {
                "id": "node_template",
                "type": "template",
                "position": {"x": 450, "y": 250},
                "data": {
                    "templateName": "dummy_rsvp_template",
                    "buttons": [
                        {"label": "Yes", "value": "yes"},
                        {"label": "No", "value": "no"}
                    ],
                    "label": "RSVP Branching"
                }
            },
            {
                "id": "node_ask_date",
                "type": "input",
                "position": {"x": 850, "y": 100},
                "data": {
                    "prompt": "Excellent! What date will you be arriving? (DD-MM-YYYY)",
                    "validation": "date",
                    "label": "Capture Date"
                }
            },
            {
                "id": "node_sorry",
                "type": "message",
                "position": {"x": 850, "y": 450},
                "data": {
                    "text": "We are sorry to hear that you cannot make it. We will miss you!",
                    "label": "Exit Path"
                }
            },
            {
                "id": "node_db_sync",
                "type": "orm_update",
                "position": {"x": 1250, "y": 100},
                "data": {
                    "model": "TravelDetail",
                    "mappings": [
                        {"field": "arrival_date", "source_node": "node_ask_date"}
                    ],
                    "label": "Save to TravelRecord"
                }
            },
            {
                "id": "node_final_thanks",
                "type": "message",
                "position": {"x": 1650, "y": 100},
                "data": {
                    "text": "Thank you {{guest.name}}! Your arrival on {{node_ask_date}} has been recorded.",
                    "label": "Completion"
                }
            }
        ],
        "edges": [
            {"id": "e1", "source": "node_trigger", "target": "node_template"},
            {"id": "e2", "source": "node_template", "target": "node_ask_date", "sourceHandle": "yes"},
            {"id": "e3", "source": "node_template", "target": "node_sorry", "sourceHandle": "no"},
            {"id": "e4", "source": "node_ask_date", "target": "node_db_sync"},
            {"id": "e5", "source": "node_db_sync", "target": "node_final_thanks"}
        ]
    }

    bp, created = FlowBlueprint.objects.update_or_create(
        name="Full Travel & RSVP Flow Demo",
        defaults={
            "trigger_keyword": "demo",
            "graph_json": graph,
            "is_active": True
        }
    )
    print(f"Demo Flow created with ID: {bp.id}")

if __name__ == "__main__":
    create_demo_flow()
