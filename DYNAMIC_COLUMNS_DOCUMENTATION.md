# Dynamic Custom Fields for Event Registrations - Frontend Integration Guide

## Overview

The ANK backend now supports **dynamic custom fields** for Event Registrations. This allows you to create custom columns/fields per event that can be different for each event, enabling flexible data collection without changing the database schema.

### Key Features
- ✅ Create unlimited custom fields for EventRegistration
- ✅ Supports 4 field types: `text`, `number`, `date`, `boolean`
- ✅ Bulk update custom field values
- ✅ Retrieve all registrations with custom fields for table display
- ✅ Field-level CRUD operations
- ✅ Automatic validation based on field type

---

## Architecture Overview

### Models Relationship

```
CustomFieldDefinition (defines the field structure)
    ├── name: "dietary_preference"
    ├── label: "Dietary Preference"
    ├── field_type: "text"
    ├── help_text: "Guest's dietary requirements"
    └── content_type: EventRegistration
         ↓
CustomFieldValue (stores actual values)
    ├── definition: → CustomFieldDefinition
    ├── content_object: → EventRegistration (via GenericForeignKey)
    └── value: "Vegetarian"
```

### How It Works

1. **Define Custom Fields**: Create field definitions that describe what data you want to collect
2. **Attach to Registrations**: Each EventRegistration can have multiple custom field values
3. **Query & Display**: Retrieve registrations with their custom fields in a single API call

---

## API Endpoints Reference

### Base URL
```
https://your-api-domain.com/api/
```

All endpoints require authentication: `Authorization: Bearer <token>`

---

## 1. Custom Field Definitions Management

### 1.1 List All Custom Field Definitions

**GET** `/api/custom-fields/definitions/`

Get all custom field definitions, optionally filtered by model.

**Query Parameters:**
- `model` (optional): Filter by model name
  - Values: `eventregistration`, `event`, `session`

**Request Example:**
```bash
GET /api/custom-fields/definitions/?model=eventregistration
```

**Response:**
```json
[
  {
    "id": "123e4567-e89b-12d3-a456-426614174000",
    "name": "dietary_preference",
    "label": "Dietary Preference",
    "field_type": "text",
    "help_text": "Guest's dietary requirements",
    "model_name": "eventregistration"
  },
  {
    "id": "223e4567-e89b-12d3-a456-426614174001",
    "name": "age_group",
    "label": "Age Group",
    "field_type": "text",
    "help_text": "Guest's age group",
    "model_name": "eventregistration"
  }
]
```

---

### 1.2 Create a Custom Field Definition

**POST** `/api/custom-fields/definitions/`

Create a new custom field definition.

**Request Body:**
```json
{
  "name": "dietary_preference",
  "label": "Dietary Preference",
  "field_type": "text",
  "help_text": "Guest's dietary requirements (optional)",
  "content_type_model": "eventregistration"
}
```

**Field Types:**
- `text`: Free text input
- `number`: Numeric values
- `date`: ISO date format (YYYY-MM-DD)
- `boolean`: true/false values

**Response (201 Created):**
```json
{
  "id": "123e4567-e89b-12d3-a456-426614174000",
  "name": "dietary_preference",
  "label": "Dietary Preference",
  "field_type": "text",
  "help_text": "Guest's dietary requirements (optional)",
  "model_name": "eventregistration"
}
```

**Frontend Implementation Example (React/TypeScript):**
```typescript
interface CreateFieldDefinition {
  name: string;
  label: string;
  field_type: 'text' | 'number' | 'date' | 'boolean';
  help_text?: string;
  content_type_model: 'eventregistration' | 'event' | 'session';
}

async function createCustomField(data: CreateFieldDefinition) {
  const response = await fetch('/api/custom-fields/definitions/', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${token}`
    },
    body: JSON.stringify(data)
  });
  
  if (!response.ok) {
    throw new Error('Failed to create field');
  }
  
  return await response.json();
}

// Usage
const newField = await createCustomField({
  name: 'dietary_preference',
  label: 'Dietary Preference',
  field_type: 'text',
  help_text: 'Guest dietary requirements',
  content_type_model: 'eventregistration'
});
```

---

### 1.3 Get Single Field Definition

**GET** `/api/custom-fields/definitions/{field_id}/`

**Response:**
```json
{
  "id": "123e4567-e89b-12d3-a456-426614174000",
  "name": "dietary_preference",
  "label": "Dietary Preference",
  "field_type": "text",
  "help_text": "Guest's dietary requirements",
  "model_name": "eventregistration"
}
```

---

### 1.4 Update Field Definition

**PUT/PATCH** `/api/custom-fields/definitions/{field_id}/`

**Request Body (PATCH):**
```json
{
  "label": "Dietary Requirements",
  "help_text": "Updated help text"
}
```

---

### 1.5 Delete Field Definition

**DELETE** `/api/custom-fields/definitions/{field_id}/`

⚠️ **Warning**: This will also delete all values associated with this field!

**Response (204 No Content)**

---

## 2. Event Registration Custom Field Values

### 2.1 Get All Custom Fields for a Registration

**GET** `/api/event-registrations/{registration_id}/custom-fields/`

Get all custom field values for a specific registration.

**Response:**
```json
{
  "registration_id": "reg-uuid-123",
  "guest_name": "John Doe",
  "event_id": "event-uuid-456",
  "event_name": "Smith Wedding 2025",
  "rsvp_status": "yes",
  "custom_fields": {
    "dietary_preference": {
      "label": "Dietary Preference",
      "value": "Vegetarian",
      "type": "text",
      "value_id": "value-uuid-789"
    },
    "age_group": {
      "label": "Age Group",
      "value": "Adult",
      "type": "text",
      "value_id": "value-uuid-790"
    }
  }
}
```

**Frontend Implementation Example:**
```typescript
interface CustomFieldValue {
  label: string;
  value: string;
  type: string;
  value_id: string;
}

interface RegistrationWithCustomFields {
  registration_id: string;
  guest_name: string;
  event_id: string;
  event_name: string;
  rsvp_status: string;
  custom_fields: Record<string, CustomFieldValue>;
}

async function getRegistrationCustomFields(
  registrationId: string
): Promise<RegistrationWithCustomFields> {
  const response = await fetch(
    `/api/event-registrations/${registrationId}/custom-fields/`,
    {
      headers: {
        'Authorization': `Bearer ${token}`
      }
    }
  );
  
  return await response.json();
}
```

---

### 2.2 Bulk Update Custom Fields for a Registration

**POST** `/api/event-registrations/{registration_id}/custom-fields/`

Set or update multiple custom field values at once.

**Request Body:**
```json
{
  "custom_fields": {
    "dietary_preference": "Vegetarian",
    "age_group": "Adult",
    "needs_accommodation": "true",
    "arrival_date": "2025-03-15"
  }
}
```

**Response (200 OK):**
```json
{
  "message": "Custom fields updated successfully",
  "updated_fields": [
    {
      "field": "dietary_preference",
      "label": "Dietary Preference",
      "value": "Vegetarian",
      "created": false
    },
    {
      "field": "age_group",
      "label": "Age Group",
      "value": "Adult",
      "created": true
    }
  ]
}
```

**Frontend Implementation Example:**
```typescript
async function updateCustomFields(
  registrationId: string,
  fields: Record<string, string>
) {
  const response = await fetch(
    `/api/event-registrations/${registrationId}/custom-fields/`,
    {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${token}`
      },
      body: JSON.stringify({ custom_fields: fields })
    }
  );
  
  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.message || 'Failed to update fields');
  }
  
  return await response.json();
}

// Usage
await updateCustomFields('reg-uuid-123', {
  dietary_preference: 'Vegetarian',
  age_group: 'Adult',
  arrival_date: '2025-03-15'
});
```

---

### 2.3 Get/Update/Delete Single Custom Field Value

**GET/PUT/DELETE** `/api/event-registrations/{registration_id}/custom-fields/{field_name}/`

**GET Response:**
```json
{
  "id": "value-uuid-789",
  "definition": "def-uuid-123",
  "value": "Vegetarian",
  "field_name": "dietary_preference",
  "field_label": "Dietary Preference",
  "field_type": "text"
}
```

**PUT Request:**
```json
{
  "value": "Vegan"
}
```

**DELETE Response (204 No Content)**

---

## 3. Event-Level: Get All Registrations with Custom Fields

### 3.1 Get All Registrations for an Event (with Custom Fields)

**GET** `/api/events/{event_id}/registrations/custom-fields/`

This is the **most important endpoint** for displaying registration tables with dynamic columns.

**Response:**
```json
{
  "event_id": "event-uuid-456",
  "event_name": "Smith Wedding 2025",
  "total_registrations": 150,
  "field_definitions": [
    {
      "id": "def-uuid-1",
      "name": "dietary_preference",
      "label": "Dietary Preference",
      "field_type": "text",
      "help_text": "Guest dietary requirements"
    },
    {
      "id": "def-uuid-2",
      "name": "age_group",
      "label": "Age Group",
      "field_type": "text",
      "help_text": ""
    }
  ],
  "registrations": [
    {
      "registration_id": "reg-uuid-1",
      "guest_name": "John Doe",
      "event_id": "event-uuid-456",
      "event_name": "Smith Wedding 2025",
      "rsvp_status": "yes",
      "custom_fields": {
        "dietary_preference": {
          "label": "Dietary Preference",
          "value": "Vegetarian",
          "type": "text",
          "value_id": "value-uuid-1"
        },
        "age_group": {
          "label": "Age Group",
          "value": "Adult",
          "type": "text",
          "value_id": "value-uuid-2"
        }
      }
    },
    {
      "registration_id": "reg-uuid-2",
      "guest_name": "Jane Smith",
      "event_id": "event-uuid-456",
      "event_name": "Smith Wedding 2025",
      "rsvp_status": "pending",
      "custom_fields": {
        "dietary_preference": {
          "label": "Dietary Preference",
          "value": "None",
          "type": "text",
          "value_id": "value-uuid-3"
        }
      }
    }
  ]
}
```

**Frontend Implementation Example (React Data Table):**
```typescript
import { useEffect, useState } from 'react';

interface EventRegistrationsData {
  event_id: string;
  event_name: string;
  total_registrations: number;
  field_definitions: FieldDefinition[];
  registrations: RegistrationWithCustomFields[];
}

function RegistrationsTable({ eventId }: { eventId: string }) {
  const [data, setData] = useState<EventRegistrationsData | null>(null);
  
  useEffect(() => {
    async function fetchData() {
      const response = await fetch(
        `/api/events/${eventId}/registrations/custom-fields/`,
        {
          headers: { 'Authorization': `Bearer ${token}` }
        }
      );
      setData(await response.json());
    }
    fetchData();
  }, [eventId]);
  
  if (!data) return <div>Loading...</div>;
  
  // Build dynamic columns
  const columns = [
    { key: 'guest_name', label: 'Guest Name' },
    { key: 'rsvp_status', label: 'RSVP Status' },
    ...data.field_definitions.map(field => ({
      key: field.name,
      label: field.label,
      type: field.field_type
    }))
  ];
  
  return (
    <table>
      <thead>
        <tr>
          {columns.map(col => (
            <th key={col.key}>{col.label}</th>
          ))}
        </tr>
      </thead>
      <tbody>
        {data.registrations.map(reg => (
          <tr key={reg.registration_id}>
            <td>{reg.guest_name}</td>
            <td>{reg.rsvp_status}</td>
            {data.field_definitions.map(field => (
              <td key={field.name}>
                {reg.custom_fields[field.name]?.value || '-'}
              </td>
            ))}
          </tr>
        ))}
      </tbody>
    </table>
  );
}
```

---

## Frontend Implementation Patterns

### Pattern 1: Dynamic Form Builder

Build a form dynamically based on field definitions:

```typescript
function CustomFieldsForm({ 
  registrationId, 
  eventId 
}: { 
  registrationId: string;
  eventId: string;
}) {
  const [fields, setFields] = useState<FieldDefinition[]>([]);
  const [values, setValues] = useState<Record<string, string>>({});
  
  useEffect(() => {
    // Load field definitions
    async function loadFields() {
      const defs = await fetch(
        `/api/custom-fields/definitions/?model=eventregistration`
      ).then(r => r.json());
      setFields(defs);
      
      // Load existing values
      const existing = await fetch(
        `/api/event-registrations/${registrationId}/custom-fields/`
      ).then(r => r.json());
      
      const valueMap: Record<string, string> = {};
      Object.entries(existing.custom_fields).forEach(([key, val]: any) => {
        valueMap[key] = val.value;
      });
      setValues(valueMap);
    }
    loadFields();
  }, [registrationId]);
  
  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    
    await fetch(
      `/api/event-registrations/${registrationId}/custom-fields/`,
      {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify({ custom_fields: values })
      }
    );
    
    alert('Custom fields updated!');
  }
  
  return (
    <form onSubmit={handleSubmit}>
      {fields.map(field => (
        <div key={field.name}>
          <label>{field.label}</label>
          {field.field_type === 'text' && (
            <input
              type="text"
              value={values[field.name] || ''}
              onChange={e => setValues({
                ...values,
                [field.name]: e.target.value
              })}
              placeholder={field.help_text}
            />
          )}
          {field.field_type === 'number' && (
            <input
              type="number"
              value={values[field.name] || ''}
              onChange={e => setValues({
                ...values,
                [field.name]: e.target.value
              })}
            />
          )}
          {field.field_type === 'date' && (
            <input
              type="date"
              value={values[field.name] || ''}
              onChange={e => setValues({
                ...values,
                [field.name]: e.target.value
              })}
            />
          )}
          {field.field_type === 'boolean' && (
            <select
              value={values[field.name] || 'false'}
              onChange={e => setValues({
                ...values,
                [field.name]: e.target.value
              })}
            >
              <option value="true">Yes</option>
              <option value="false">No</option>
            </select>
          )}
        </div>
      ))}
      <button type="submit">Save Custom Fields</button>
    </form>
  );
}
```

---

### Pattern 2: Admin Field Manager

Allow admins to create/manage custom fields:

```typescript
function FieldDefinitionManager() {
  const [fields, setFields] = useState<FieldDefinition[]>([]);
  const [newField, setNewField] = useState({
    name: '',
    label: '',
    field_type: 'text',
    help_text: ''
  });
  
  useEffect(() => {
    loadFields();
  }, []);
  
  async function loadFields() {
    const data = await fetch(
      '/api/custom-fields/definitions/?model=eventregistration',
      {
        headers: { 'Authorization': `Bearer ${token}` }
      }
    ).then(r => r.json());
    setFields(data);
  }
  
  async function createField() {
    await fetch('/api/custom-fields/definitions/', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${token}`
      },
      body: JSON.stringify({
        ...newField,
        content_type_model: 'eventregistration'
      })
    });
    
    loadFields();
    setNewField({ name: '', label: '', field_type: 'text', help_text: '' });
  }
  
  async function deleteField(fieldId: string) {
    if (!confirm('Delete this field and all its values?')) return;
    
    await fetch(`/api/custom-fields/definitions/${fieldId}/`, {
      method: 'DELETE',
      headers: { 'Authorization': `Bearer ${token}` }
    });
    
    loadFields();
  }
  
  return (
    <div>
      <h2>Custom Fields Manager</h2>
      
      <div className="create-field">
        <h3>Create New Field</h3>
        <input
          placeholder="Field name (e.g., dietary_preference)"
          value={newField.name}
          onChange={e => setNewField({ ...newField, name: e.target.value })}
        />
        <input
          placeholder="Field label (e.g., Dietary Preference)"
          value={newField.label}
          onChange={e => setNewField({ ...newField, label: e.target.value })}
        />
        <select
          value={newField.field_type}
          onChange={e => setNewField({ ...newField, field_type: e.target.value })}
        >
          <option value="text">Text</option>
          <option value="number">Number</option>
          <option value="date">Date</option>
          <option value="boolean">Boolean</option>
        </select>
        <input
          placeholder="Help text (optional)"
          value={newField.help_text}
          onChange={e => setNewField({ ...newField, help_text: e.target.value })}
        />
        <button onClick={createField}>Create Field</button>
      </div>
      
      <div className="existing-fields">
        <h3>Existing Fields</h3>
        <ul>
          {fields.map(field => (
            <li key={field.id}>
              <strong>{field.label}</strong> ({field.name}) - {field.field_type}
              <button onClick={() => deleteField(field.id)}>Delete</button>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}
```

---

### Pattern 3: Excel-Like Editable Table

Inline editing with custom columns:

```typescript
function EditableRegistrationsTable({ eventId }: { eventId: string }) {
  const [data, setData] = useState<EventRegistrationsData | null>(null);
  const [editingCell, setEditingCell] = useState<{
    registrationId: string;
    fieldName: string;
  } | null>(null);
  
  async function updateCell(
    registrationId: string,
    fieldName: string,
    newValue: string
  ) {
    await fetch(
      `/api/event-registrations/${registrationId}/custom-fields/`,
      {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify({
          custom_fields: { [fieldName]: newValue }
        })
      }
    );
    
    // Reload data
    loadData();
  }
  
  // Render editable cells...
  // Implementation details omitted for brevity
}
```

---

## Common Use Cases

### Use Case 1: Add "Dietary Preference" Column

```typescript
// 1. Create the field definition
await createCustomField({
  name: 'dietary_preference',
  label: 'Dietary Preference',
  field_type: 'text',
  help_text: 'Vegetarian, Vegan, Halal, etc.',
  content_type_model: 'eventregistration'
});

// 2. Update values for specific registrations
await updateCustomFields('reg-uuid-123', {
  dietary_preference: 'Vegetarian'
});

// 3. Display in table
const eventData = await fetch(
  `/api/events/${eventId}/registrations/custom-fields/`
).then(r => r.json());

// Now you have dietary_preference in custom_fields for each registration
```

---

### Use Case 2: Add Multiple Event-Specific Fields

```typescript
// For a wedding event, create fields:
const weddingFields = [
  {
    name: 'dietary_preference',
    label: 'Dietary Preference',
    field_type: 'text'
  },
  {
    name: 'plus_one_name',
    label: 'Plus One Name',
    field_type: 'text'
  },
  {
    name: 'table_number',
    label: 'Table Number',
    field_type: 'number'
  },
  {
    name: 'needs_accommodation',
    label: 'Needs Accommodation',
    field_type: 'boolean'
  }
];

for (const field of weddingFields) {
  await createCustomField({
    ...field,
    content_type_model: 'eventregistration'
  });
}
```

---

## Error Handling

### Common Errors

**400 Bad Request - Invalid field name:**
```json
{
  "custom_fields": [
    "Invalid field names: unknown_field"
  ]
}
```

**400 Bad Request - Invalid value type:**
```json
{
  "value": "Value must be a number for field \"Table Number\""
}
```

**404 Not Found - Field doesn't exist:**
```json
{
  "error": "Custom field 'unknown_field' not found"
}
```

**Frontend Error Handling Example:**
```typescript
try {
  await updateCustomFields(registrationId, fields);
} catch (error) {
  if (error.response?.status === 400) {
    const data = await error.response.json();
    if (data.custom_fields) {
      alert(`Invalid fields: ${data.custom_fields.join(', ')}`);
    } else if (data.value) {
      alert(`Validation error: ${data.value}`);
    }
  } else if (error.response?.status === 404) {
    alert('Field not found. Please refresh the page.');
  }
}
```

---

## Best Practices

### 1. Field Naming Convention
- Use lowercase with underscores: `dietary_preference`, not `Dietary Preference`
- Be descriptive but concise
- Avoid special characters

### 2. Caching Strategy
```typescript
// Cache field definitions (they don't change often)
const fieldDefinitionsCache = new Map();

async function getFieldDefinitions(model: string = 'eventregistration') {
  if (!fieldDefinitionsCache.has(model)) {
    const data = await fetch(
      `/api/custom-fields/definitions/?model=${model}`
    ).then(r => r.json());
    fieldDefinitionsCache.set(model, data);
  }
  return fieldDefinitionsCache.get(model);
}

// Clear cache when fields are created/updated/deleted
function clearFieldCache() {
  fieldDefinitionsCache.clear();
}
```

### 3. Optimistic UI Updates
```typescript
// Update UI immediately, rollback on error
async function optimisticUpdate(
  registrationId: string,
  fieldName: string,
  newValue: string
) {
  // Update local state immediately
  setLocalValue(newValue);
  
  try {
    await updateCustomFields(registrationId, {
      [fieldName]: newValue
    });
  } catch (error) {
    // Rollback on error
    setLocalValue(previousValue);
    alert('Failed to update. Please try again.');
  }
}
```

### 4. Batch Operations
If updating many registrations at once:
```typescript
async function batchUpdateCustomFields(
  updates: Array<{
    registrationId: string;
    fields: Record<string, string>;
  }>
) {
  const promises = updates.map(({ registrationId, fields }) =>
    updateCustomFields(registrationId, fields)
  );
  
  await Promise.allSettled(promises);
}
```

---

## Migration Guide

If you have existing hardcoded fields that should become dynamic:

### Before:
```typescript
// Hardcoded in component
<input
  name="dietary_preference"
  value={registration.dietary_preference}
/>
```

### After:
```typescript
// Dynamic from API
{data.field_definitions.map(field => (
  <input
    key={field.name}
    name={field.name}
    value={registration.custom_fields[field.name]?.value || ''}
    placeholder={field.help_text}
  />
))}
```

---

## Testing Checklist

- [ ] Create a custom field definition
- [ ] List all field definitions
- [ ] Update a field definition
- [ ] Delete a field definition
- [ ] Set custom field values for a registration
- [ ] Get custom field values for a registration
- [ ] Get all registrations with custom fields for an event
- [ ] Update a single custom field value
- [ ] Delete a custom field value
- [ ] Validate field type constraints (number, date, boolean)
- [ ] Handle missing/null values gracefully
- [ ] Test with 10+ custom fields
- [ ] Test with 100+ registrations

---

## Troubleshooting

### Issue: Custom fields not showing up

**Solution**: Ensure migrations have been run:
```bash
python manage.py migrate
```

### Issue: "ContentType not found" error

**Solution**: Ensure you're using the correct model name:
- Use `eventregistration` (lowercase, no spaces)
- Not `EventRegistration` or `event_registration`

### Issue: Values not saving

**Solution**: Check that field definitions exist before trying to set values:
```typescript
// Get field definitions first
const fields = await fetch('/api/custom-fields/definitions/?model=eventregistration')
  .then(r => r.json());

// Verify field exists
const fieldExists = fields.some(f => f.name === 'dietary_preference');
if (!fieldExists) {
  console.error('Field not defined!');
}
```

---

## Summary

The dynamic custom fields system provides:

1. **Flexibility**: Add new fields without database migrations
2. **Per-Event Customization**: Different events can collect different data
3. **Type Safety**: Built-in validation for number, date, boolean fields
4. **Easy Integration**: RESTful API with comprehensive endpoints
5. **Performance**: Efficient bulk operations and prefetching

**Key Endpoints to Remember:**
- Create fields: `POST /api/custom-fields/definitions/`
- Update values: `POST /api/event-registrations/{id}/custom-fields/`
- Get all data: `GET /api/events/{id}/registrations/custom-fields/`

For questions or issues, contact the backend team or refer to the API schema at `/api/schema/swagger-ui/`.
