import os
import django
import json

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ANK.settings')
django.setup()

from MessageTemplates.models import FlowBlueprint, MessageTemplate

def create_master_logistics_flow():
    graph = {
        "nodes": [
            {
                "id": "trigger_1",
                "type": "trigger",
                "position": {"x": 50, "y": 300},
                "data": {
                    "triggerType": "manual",
                    "startWithTemplate": True,
                    "initialTemplateName": "dummy_rsvp_template",
                    "label": "RSVP Launch"
                }
            },
            {
                "id": "rsvp_choice",
                "type": "template",
                "position": {"x": 400, "y": 300},
                "data": {
                    "templateName": "dummy_rsvp_template",
                    "buttons": [
                        {"label": "Attending", "value": "yes"},
                        {"label": "Not Attending", "value": "no"}
                    ]
                }
            },
            {
                "id": "check_pax",
                "type": "logic",
                "position": {"x": 800, "y": 150},
                "data": {
                    "field": "guest.estimated_pax",
                    "operator": ">",
                    "value": "1",
                    "label": "Is Group?"
                }
            },
            {
                "id": "ask_group_pax",
                "type": "input",
                "position": {"x": 1150, "y": 50},
                "data": {
                    "prompt": "We see you have multiple guests. How many people are traveling in this group?",
                    "validation": "number"
                }
            },
            {
                "id": "ask_mode",
                "type": "input",
                "position": {"x": 1500, "y": 150},
                "data": {
                    "prompt": "How will you be traveling? ✈️🚆🚗",
                    "validation": "choice",
                    "buttons": [
                        {"label": "By Air", "value": "Air"},
                        {"label": "By Train", "value": "Train"},
                        {"label": "By Car", "value": "Car"}
                    ]
                }
            },
            {
                "id": "ask_arrival_date",
                "type": "input",
                "position": {"x": 1900, "y": 150},
                "data": {
                    "prompt": "Got it! What is your Arrival Date? (DD-MM-YYYY)",
                    "validation": "date"
                }
            },
            {
                "id": "ask_carrier",
                "type": "input",
                "position": {"x": 2300, "y": 150},
                "data": {
                    "prompt": "Which Airline/Carrier are you using?",
                    "validation": "text"
                }
            },
            {
                "id": "ask_hotel_time",
                "type": "input",
                "position": {"x": 2700, "y": 150},
                "data": {
                    "prompt": "What time do you expect to arrive at the Hotel? (HH:MM)",
                    "validation": "time"
                }
            },
            {
                "id": "sync_logistics",
                "type": "orm_update",
                "position": {"x": 3100, "y": 150},
                "data": {
                    "model": "TravelDetail",
                    "mappings": [
                        {"field": "travel_type", "source_node": "ask_mode"},
                        {"field": "arrival_date", "source_node": "ask_arrival_date"},
                        {"field": "airline", "source_node": "ask_carrier"},
                        {"field": "hotel_arrival_time", "source_node": "ask_hotel_time"}
                    ]
                }
            },
            {
                "id": "final_thanks",
                "type": "message",
                "position": {"x": 3500, "y": 150},
                "data": {
                    "text": "✅ Thank you {{guest.name}}! Your logistics have been captured and saved."
                }
            },
            {
                "id": "bye",
                "type": "message",
                "position": {"x": 800, "y": 450},
                "data": {
                    "text": "Thank you for letting us know. We will miss you at the event!"
                }
            }
        ],
        "edges": [
            {"id": "e1", "source": "trigger_1", "target": "rsvp_choice"},
            {"id": "e2", "source": "rsvp_choice", "target": "check_pax", "sourceHandle": "yes"},
            {"id": "e3", "source": "rsvp_choice", "target": "bye", "sourceHandle": "no"},
            {"id": "e4", "source": "check_pax", "target": "ask_group_pax", "sourceHandle": "true"},
            {"id": "e5", "source": "check_pax", "target": "ask_mode", "sourceHandle": "false"},
            {"id": "e6", "source": "ask_group_pax", "target": "ask_mode"},
            {"id": "e7", "source": "ask_mode", "target": "ask_arrival_date"},
            {"id": "e8", "source": "ask_arrival_date", "target": "ask_carrier"},
            {"id": "e9", "source": "ask_carrier", "target": "ask_hotel_time"},
            {"id": "e10", "source": "ask_hotel_time", "target": "sync_logistics"},
            {"id": "e11", "source": "sync_logistics", "target": "final_thanks"}
        ]
    }

    bp, created = FlowBlueprint.objects.update_or_create(
        name="Master Logistics & Travel Flow",
        defaults={
            "trigger_keyword": "master",
            "graph_json": graph,
            "is_active": True
        }
    )
    print(f"Master Flow updated with ID: {bp.id}")

if __name__ == "__main__":
    create_master_logistics_flow()
