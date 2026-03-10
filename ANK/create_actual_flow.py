import os
import django
import json

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ANK.settings')
django.setup()

from MessageTemplates.models import FlowBlueprint, MessageTemplate, WhatsAppPhoneNumber, WhatsAppBusinessAccount

def create_actual_travel_flow():
    graph = {
        "nodes": [
            {
                "id": "node_trigger",
                "type": "trigger",
                "position": {"x": 0, "y": 300},
                "data": {
                    "triggerType": "manual",
                    "startWithTemplate": True,
                    "initialTemplateName": "dummy_rsvp_template",
                    "label": "RSVP Activation"
                }
            },
            {
                "id": "node_rsvp_choice",
                "type": "template",
                "position": {"x": 350, "y": 300},
                "data": {
                    "templateName": "dummy_rsvp_template",
                    "buttons": [
                        {"label": "Yes", "value": "yes"},
                        {"label": "No", "value": "no"}
                    ]
                }
            },
            {
                "id": "node_ask_mode",
                "type": "input",
                "position": {"x": 750, "y": 150},
                "data": {
                    "prompt": "Excellent! How will you be traveling to the event? ✈️🚆🚗",
                    "validation": "choice",
                    "buttons": [
                        {"label": "Air", "value": "Air"},
                        {"label": "Train", "value": "Train"},
                        {"label": "Car", "value": "Car"}
                    ]
                }
            },
            {
                "id": "node_ask_date",
                "type": "input",
                "position": {"x": 1150, "y": 150},
                "data": {
                    "prompt": "📅 What is your Arrival Date? (DD-MM-YYYY)",
                    "validation": "date"
                }
            },
            {
                "id": "node_ask_airline",
                "type": "input",
                "position": {"x": 1550, "y": 50},
                "data": {
                    "prompt": "Which Airline are you flying with? ✈️",
                    "validation": "text"
                }
            },
            {
                "id": "node_ask_train",
                "type": "input",
                "position": {"x": 1550, "y": 250},
                "data": {
                    "prompt": "Which Train are you taking? 🚆",
                    "validation": "text"
                }
            },
            {
                "id": "node_db_sync",
                "type": "orm_update",
                "position": {"x": 2000, "y": 150},
                "data": {
                    "model": "TravelDetail",
                    "mappings": [
                        {"field": "travel_type", "source_node": "node_ask_mode"},
                        {"field": "arrival_date", "source_node": "node_ask_date"},
                        {"field": "airline", "source_node": "node_ask_airline"}
                    ]
                }
            },
            {
                "id": "node_final_thanks",
                "type": "message",
                "position": {"x": 2400, "y": 150},
                "data": {
                    "text": "✅ Thank you! We've saved your travel details. We look forward to seeing you!"
                }
            }
        ],
        "edges": [
            {"id": "e1", "source": "node_trigger", "target": "node_rsvp_choice"},
            {"id": "e2", "source": "node_rsvp_choice", "target": "node_ask_mode", "sourceHandle": "yes"},
            {"id": "e3", "source": "node_ask_mode", "target": "node_ask_date"},
            {"id": "e4", "source": "node_ask_date", "target": "node_ask_airline"},
            {"id": "e5", "source": "node_ask_airline", "target": "node_db_sync"},
            {"id": "e6", "source": "node_db_sync", "target": "node_final_thanks"}
        ]
    }

    bp, created = FlowBlueprint.objects.update_or_create(
        name="Real Travel Capture Flow",
        defaults={
            "trigger_keyword": "travel",
            "graph_json": graph,
            "is_active": True
        }
    )
    print(f"Flow '{bp.name}' updated with ID: {bp.id}")

if __name__ == "__main__":
    create_actual_travel_flow()
