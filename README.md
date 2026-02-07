[![hacs_badge](https://img.shields.io/badge/HACS-Default-orange.svg)](https://github.com/hacs/integration)
[![GitHub release](https://img.shields.io/github/v/release/lavalex2003/emaktab)](https://github.com/lavalex2003/emaktab/releases)
[![downloads](https://img.shields.io/github/downloads/lavalex2003/emaktab/total)](https://github.com/lavalex2003/emaktab/releases)
![Home Assistant](https://img.shields.io/badge/Home%20Assistant-2024.6%2B-blue)
![CI](https://github.com/lavalex2003/emaktab/actions/workflows/hassfest.yml/badge.svg)


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
3. Search for **eMaktab** and install it
4. Restart Home Assistant

[![Open in HACS](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=lavalex2003&repository=emaktab)

> After installation, the integration will appear automatically in
> **Settings → Devices & Services → Add Integration**

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

## Support

If you encounter issues:

- Open a GitHub issue
- Include logs
- Describe your Home Assistant version

---

## Notes

- This integration relies on the eMaktab web service and may stop working if the service changes
- No official API is used
- Data is retrieved using authenticated web sessions

---

## License

MIT License
