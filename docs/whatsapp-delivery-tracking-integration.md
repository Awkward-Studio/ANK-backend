# WhatsApp Message Delivery Tracking - Frontend Integration Guide

This document describes how to integrate your Next.js frontend with the Django backend's WhatsApp message delivery tracking system.

## Overview

The system tracks delivery status (sent → delivered → read / failed) for all WhatsApp messages. It supports two types of messages:

1. **Event-based messages**: RSVP templates, travel updates, etc. (linked to EventRegistration)
2. **Standalone messages**: Bulk-send templates, marketing messages (no event context)

---

## Authentication

All endpoints require the webhook token in the header:

```typescript
const headers = {
  'Content-Type': 'application/json',
  'X-Webhook-Token': process.env.DJANGO_RSVP_SECRET
};
```

---

## Endpoints

### 1. Track Message Send

Call this endpoint **immediately after** sending a WhatsApp template message via Meta API.

**Endpoint:** `POST /api/webhooks/track-send/`

#### For Event-based Messages (RSVP, Travel, etc.)

```typescript
interface TrackSendEventRequest {
  wa_id: string;                    // Recipient phone (e.g., "919876543210")
  event_id: string;                 // Event UUID
  event_registration_id?: string;   // Registration UUID (recommended)
  template_wamid: string;           // Message ID from Meta API response
  template_name?: string;           // Template name (e.g., "rsvp_invite_v2")
  flow_type?: string;               // "rsvp" | "travel" | "custom"
  message_type?: string;            // "rsvp" | "travel" | "template"
  guest_id?: string;                // Guest UUID
  guest_name?: string;              // Guest name for display
}

// Example
const response = await fetch(`${DJANGO_URL}/api/webhooks/track-send/`, {
  method: 'POST',
  headers,
  body: JSON.stringify({
    wa_id: '919876543210',
    event_id: 'uuid-of-event',
    event_registration_id: 'uuid-of-registration',
    template_wamid: 'wamid.HBgLMTk4NzY1NDMyMTAVAgAS...',
    template_name: 'rsvp_invite_v2',
    flow_type: 'rsvp',
    message_type: 'rsvp',
    guest_id: 'uuid-of-guest',
    guest_name: 'John Doe'
  })
});

// Response
{
  "ok": true,
  "map_id": "uuid-of-wa-send-map"
}
```

#### For Standalone Messages (Bulk-send, Marketing, etc.)

```typescript
interface TrackSendStandaloneRequest {
  wa_id: string;                    // Recipient phone
  template_wamid: string;           // Message ID from Meta API response (REQUIRED)
  template_name?: string;           // Template name
  flow_type?: string;               // Optional identifier (defaults to "standalone")
  message_type?: string;            // Optional (defaults to "template")
  guest_name?: string;              // Recipient name for display
}

// Example - NO event_id or event_registration_id
const response = await fetch(`${DJANGO_URL}/api/webhooks/track-send/`, {
  method: 'POST',
  headers,
  body: JSON.stringify({
    wa_id: '919876543210',
    template_wamid: 'wamid.HBgLMTk4NzY1NDMyMTAVAgAS...',
    template_name: 'bulk_announcement_v1',
    guest_name: 'John Doe'
  })
});

// Response
{
  "ok": true,
  "standalone": true,
  "wamid": "wamid.HBgLMTk4NzY1NDMyMTAVAgAS..."
}
```

---

### 2. Forward Status Updates from Meta Webhook

When your Next.js app receives status updates from Meta's webhook, forward them to Django.

**Endpoint:** `POST /api/webhooks/message-status/`

```typescript
interface MessageStatusRequest {
  wamid: string;                    // Message ID
  recipient_id: string;             // Phone number
  status: 'sent' | 'delivered' | 'read' | 'failed';
  timestamp: string;                // ISO timestamp
  errors?: Array<{                  // Only for failed status
    code: number;
    title: string;
  }>;
}

// Example: Processing Meta webhook in your Next.js API route
export async function POST(request: Request) {
  const body = await request.json();
  
  // Extract status updates from Meta webhook payload
  const entry = body.entry?.[0];
  const changes = entry?.changes?.[0];
  const statuses = changes?.value?.statuses || [];
  
  for (const status of statuses) {
    await fetch(`${DJANGO_URL}/api/webhooks/message-status/`, {
      method: 'POST',
      headers,
      body: JSON.stringify({
        wamid: status.id,
        recipient_id: status.recipient_id,
        status: status.status,  // "sent", "delivered", "read", "failed"
        timestamp: new Date(parseInt(status.timestamp) * 1000).toISOString(),
        errors: status.errors   // Only present for failed messages
      })
    });
  }
  
  return Response.json({ ok: true });
}

// Response
{
  "ok": true,
  "status": "delivered"  // Current status after update
}
```

---

### 3. Look Up Message Statuses (Batch)

Query the current status of multiple messages at once.

**Endpoint:** `POST /api/webhooks/message-status-lookup/`

```typescript
interface StatusLookupRequest {
  wamids: string[];  // Array of message IDs
}

interface StatusLookupResponse {
  statuses: {
    [wamid: string]: {
      status: 'sent' | 'delivered' | 'read' | 'failed';
      sent_at: string | null;
      delivered_at: string | null;
      read_at: string | null;
      error_code: string | null;
      error: string | null;
    };
  };
}

// Example
const response = await fetch(`${DJANGO_URL}/api/webhooks/message-status-lookup/`, {
  method: 'POST',
  headers,
  body: JSON.stringify({
    wamids: [
      'wamid.HBgLMTk4NzY1NDMyMTAVAgAS...',
      'wamid.HBgLMTk4NzY1NDMyMTBWBgAS...'
    ]
  })
});

// Response
{
  "statuses": {
    "wamid.HBgLMTk4NzY1NDMyMTAVAgAS...": {
      "status": "delivered",
      "sent_at": "2024-01-15T10:30:00Z",
      "delivered_at": "2024-01-15T10:30:05Z",
      "read_at": null,
      "error_code": null,
      "error": null
    },
    "wamid.HBgLMTk4NzY1NDMyMTBWBgAS...": {
      "status": "read",
      "sent_at": "2024-01-15T10:25:00Z",
      "delivered_at": "2024-01-15T10:25:03Z",
      "read_at": "2024-01-15T10:28:00Z",
      "error_code": null,
      "error": null
    }
  }
}
```

---

### 4. Get Message Logs (List)

Query message logs with various filters.

**Endpoint:** `GET /api/webhooks/message-logs/`

#### Query Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `registration_id` | string | Filter by EventRegistration UUID |
| `event_id` | string | Filter by Event UUID |
| `guest_id` | string | Filter by Guest UUID |
| `recipient_id` | string | Filter by phone number |
| `template_name` | string | Filter by template name |
| `standalone` | "true" | Only return standalone messages (no event context) |

```typescript
interface MessageLog {
  id: string;
  wamid: string;
  recipient_id: string;
  status: 'sent' | 'delivered' | 'read' | 'failed';
  message_type: string;
  template_name: string | null;
  event_id: string | null;
  registration_id: string | null;
  guest_id: string | null;
  guest_name: string | null;
  sent_at: string | null;
  delivered_at: string | null;
  read_at: string | null;
  failed_at: string | null;
  error_code: string | null;
  error_message: string | null;
}

interface MessageLogsResponse {
  logs: MessageLog[];
}

// Example: Get all messages for an event
const response = await fetch(
  `${DJANGO_URL}/api/webhooks/message-logs/?event_id=${eventId}`,
  { headers }
);

// Example: Get standalone messages only
const response = await fetch(
  `${DJANGO_URL}/api/webhooks/message-logs/?standalone=true`,
  { headers }
);

// Example: Get messages for a specific phone number
const response = await fetch(
  `${DJANGO_URL}/api/webhooks/message-logs/?recipient_id=919876543210`,
  { headers }
);

// Example: Get messages for a specific template
const response = await fetch(
  `${DJANGO_URL}/api/webhooks/message-logs/?template_name=bulk_announcement_v1`,
  { headers }
);

// Response (limited to 50 most recent)
{
  "logs": [
    {
      "id": "uuid",
      "wamid": "wamid.HBgLMTk4NzY1NDMyMTAVAgAS...",
      "recipient_id": "919876543210",
      "status": "delivered",
      "message_type": "rsvp",
      "template_name": "rsvp_invite_v2",
      "event_id": "event-uuid",
      "registration_id": "registration-uuid",
      "guest_id": "guest-uuid",
      "guest_name": "John Doe",
      "sent_at": "2024-01-15T10:30:00Z",
      "delivered_at": "2024-01-15T10:30:05Z",
      "read_at": null,
      "failed_at": null,
      "error_code": null,
      "error_message": null
    }
  ]
}
```

---

### 5. Get Latest Message Log for Registration

Get the most recent message log for a specific registration.

**Endpoint:** `GET /api/webhooks/message-logs/latest/`

```typescript
// Example
const response = await fetch(
  `${DJANGO_URL}/api/webhooks/message-logs/latest/?registration_id=${registrationId}`,
  { headers }
);

// Response
{
  "log": {
    "id": "uuid",
    "wamid": "wamid.HBgLMTk4NzY1NDMyMTAVAgAS...",
    "recipient_id": "919876543210",
    "status": "delivered",
    "message_type": "rsvp",
    "template_name": "rsvp_invite_v2",
    "sent_at": "2024-01-15T10:30:00Z",
    "delivered_at": "2024-01-15T10:30:05Z",
    "read_at": null,
    "error_code": null,
    "error_message": null
  }
}

// If no message found
{
  "log": null
}
```

---

## Complete Integration Example

### Sending an RSVP Template with Tracking

```typescript
import { sendWhatsAppTemplate } from '@/lib/whatsapp';

async function sendRSVPInvite(registration: EventRegistration) {
  const { guest, event } = registration;
  
  // 1. Send template via Meta API
  const metaResponse = await sendWhatsAppTemplate({
    to: guest.phone,
    templateName: 'rsvp_invite_v2',
    components: [
      {
        type: 'body',
        parameters: [
          { type: 'text', text: guest.name },
          { type: 'text', text: event.name }
        ]
      }
    ]
  });
  
  const wamid = metaResponse.messages[0].id;
  
  // 2. Track the send in Django
  await fetch(`${DJANGO_URL}/api/webhooks/track-send/`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-Webhook-Token': process.env.DJANGO_RSVP_SECRET!
    },
    body: JSON.stringify({
      wa_id: guest.phone,
      event_id: event.id,
      event_registration_id: registration.id,
      template_wamid: wamid,
      template_name: 'rsvp_invite_v2',
      flow_type: 'rsvp',
      message_type: 'rsvp',
      guest_id: guest.id,
      guest_name: guest.name
    })
  });
  
  return { success: true, wamid };
}
```

### Sending a Bulk/Standalone Message with Tracking

```typescript
async function sendBulkMessage(phone: string, name: string, templateName: string) {
  // 1. Send template via Meta API
  const metaResponse = await sendWhatsAppTemplate({
    to: phone,
    templateName: templateName,
    components: [
      {
        type: 'body',
        parameters: [{ type: 'text', text: name }]
      }
    ]
  });
  
  const wamid = metaResponse.messages[0].id;
  
  // 2. Track the send in Django (standalone - no event_id)
  await fetch(`${DJANGO_URL}/api/webhooks/track-send/`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-Webhook-Token': process.env.DJANGO_RSVP_SECRET!
    },
    body: JSON.stringify({
      wa_id: phone,
      template_wamid: wamid,
      template_name: templateName,
      guest_name: name
    })
  });
  
  return { success: true, wamid };
}
```

### Meta Webhook Handler (Status Updates)

```typescript
// app/api/webhooks/whatsapp/route.ts

export async function POST(request: Request) {
  const body = await request.json();
  
  // Verify webhook (implement your verification logic)
  
  const entry = body.entry?.[0];
  const changes = entry?.changes?.[0];
  const value = changes?.value;
  
  // Handle status updates
  if (value?.statuses) {
    for (const status of value.statuses) {
      try {
        await fetch(`${process.env.DJANGO_URL}/api/webhooks/message-status/`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'X-Webhook-Token': process.env.DJANGO_RSVP_SECRET!
          },
          body: JSON.stringify({
            wamid: status.id,
            recipient_id: status.recipient_id,
            status: status.status,
            timestamp: new Date(parseInt(status.timestamp) * 1000).toISOString(),
            errors: status.errors
          })
        });
      } catch (error) {
        console.error('Failed to forward status update:', error);
      }
    }
  }
  
  // Handle incoming messages (existing logic)
  if (value?.messages) {
    // ... your existing message handling
  }
  
  return Response.json({ ok: true });
}
```

### Displaying Delivery Status in UI

```typescript
// components/DeliveryStatus.tsx

interface DeliveryStatusProps {
  status: 'sent' | 'delivered' | 'read' | 'failed';
  deliveredAt?: string;
  readAt?: string;
  errorMessage?: string;
}

export function DeliveryStatus({ status, deliveredAt, readAt, errorMessage }: DeliveryStatusProps) {
  const statusConfig = {
    sent: { icon: '✓', color: 'text-gray-400', label: 'Sent' },
    delivered: { icon: '✓✓', color: 'text-gray-400', label: 'Delivered' },
    read: { icon: '✓✓', color: 'text-blue-500', label: 'Read' },
    failed: { icon: '✗', color: 'text-red-500', label: 'Failed' }
  };
  
  const config = statusConfig[status];
  
  return (
    <div className={`flex items-center gap-1 ${config.color}`}>
      <span>{config.icon}</span>
      <span className="text-xs">{config.label}</span>
      {status === 'failed' && errorMessage && (
        <span className="text-xs text-red-400">({errorMessage})</span>
      )}
    </div>
  );
}
```

---

## Status Flow

```
┌──────────┐     ┌───────────┐     ┌──────────┐     ┌────────┐
│  SENT    │ ──► │ DELIVERED │ ──► │   READ   │     │ FAILED │
└──────────┘     └───────────┘     └──────────┘     └────────┘
     │                                                   ▲
     └───────────────────────────────────────────────────┘
                    (can fail at any point)
```

- **sent**: Message accepted by WhatsApp servers
- **delivered**: Message delivered to recipient's device
- **read**: Recipient opened/read the message
- **failed**: Message could not be delivered (includes error details)

---

## Error Handling

Common error codes from Meta:

| Code | Description |
|------|-------------|
| 131026 | Message undeliverable (user blocked, number invalid) |
| 131047 | Re-engagement message required (24h window expired) |
| 131051 | Unsupported message type |
| 130472 | User's phone number is not a WhatsApp phone number |

```typescript
// Check for failed messages
const response = await fetch(
  `${DJANGO_URL}/api/webhooks/message-logs/?event_id=${eventId}`,
  { headers }
);
const { logs } = await response.json();

const failedMessages = logs.filter(log => log.status === 'failed');
for (const msg of failedMessages) {
  console.log(`Failed: ${msg.guest_name} - ${msg.error_code}: ${msg.error_message}`);
}
```
