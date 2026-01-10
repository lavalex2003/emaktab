# eMaktab for Home Assistant

Custom (unofficial) Home Assistant integration for the **eMaktab** electronic diary service.

This integration allows you to access school day information, lessons, and daily average marks directly in Home Assistant.

---

## Disclaimer

This integration is **not affiliated with, endorsed by, or connected to eMaktab or its developers**.  
It is an independent, community-developed project.

---

## Features

- School day data retrieval
- Normalized lessons data:
  - subject
  - topic
  - homework
  - mark
- Daily average mark calculation
- Support for multiple children
- Configuration via Home Assistant UI (Config Flow)
- Designed for automations and voice assistants

---

## Installation

### Via HACS (recommended)

1. Open **HACS** in Home Assistant
2. Go to **Integrations**
3. Click **Add Custom Repository**
4. Add this repository URL and select **Integration**
5. Search for **eMaktab** and install it
6. Restart Home Assistant

---

## Configuration

Configuration is done entirely through the Home Assistant UI.

During setup, the following data is required:

- eMaktab login
- eMaktab password
- `person_id`
- `school_id`

If multiple children are available, you can create multiple configuration entries.

> ℹ️ The required identifiers are provided by the eMaktab service for each student.

---

## Entities

### Sensor: School Day

- State: current school day date
- Attributes include:
  - lessons (normalized data)
  - student information
  - source metadata

---

### Sensor: Average Mark

- State: average mark for the current school day
- Returns `0` if there are no marks or during holidays

---

### Button: Update eMaktab Data

- Forces an immediate update of all configured eMaktab entries

---

## Notes

- This integration relies on the eMaktab web service and may stop working if the service changes
- No official API is used
- Data is retrieved using authenticated web sessions

---

## License

MIT License
