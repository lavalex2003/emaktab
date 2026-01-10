"""Sensors for eMaktab integration (v2 diary)."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
    
_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities,
) -> None:
    """Set up eMaktab sensors from a config entry."""
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator = data["coordinator"]

    async_add_entities(
        [
            EmaktabDaySensor(coordinator, entry),
            EmaktabAverageMarkSensor(coordinator, entry),
        ],
        update_before_add=True,
    )

def _select_relevant_day(days: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Select ONLY today's day. No fallback to future days."""
    if not days:
        return None

    # today = datetime.now(timezone.utc).date()
    
    # ВРЕМЕННО: фиксированная дата для тестирования (учебный день)
    today = datetime(2025, 11, 13, tzinfo=timezone.utc).date()

    for day in days:
        try:
            day_date = datetime.fromtimestamp(
                int(day["date"]),
                tz=timezone.utc,
            ).date()
        except Exception:
            continue

        if day_date == today:
            return day

    # Сегодня данных нет — это допустимое состояние
    return None

def _normalize_lessons(day: dict[str, Any]) -> list[dict[str, Any]]:
    """Normalize eMaktab lessons to internal standard."""
    normalized: list[dict[str, Any]] = []

    for lesson in day.get("lessons", []):
        if lesson.get("isEmpty"):
            continue

        # Первая оценка (если есть)
        mark_obj = None
        work_marks = lesson.get("workMarks") or []
        if work_marks:
            first_work = work_marks[0]
            marks = first_work.get("marks") or []
            if marks:
                mark_obj = {
                    "value": marks[0].get("value"),
                    "reason": first_work.get("workName"),
                }

        normalized.append(
            {
                "lesson": lesson.get("number"),
                "subject": lesson.get("subject", {}).get("name"),
                "topic": lesson.get("theme"),
                "homework": (lesson.get("homework") or {}).get("text"),
                "mark": mark_obj,
            }
        )

    return normalized

class EmaktabBaseSensor(CoordinatorEntity, SensorEntity):
    """Base class for eMaktab sensors."""

    _attr_has_entity_name = True

    def __init__(self, coordinator):
        super().__init__(coordinator)
        self._attr_attribution = "Data provided by eMaktab.uz"

    @property
    def _day(self) -> dict[str, Any] | None:
        data = self.coordinator.data or {}
        return _select_relevant_day(data.get("days", []))

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        data = self.coordinator.data or {}
        attrs = {
            "last_update": data.get("last_update"),
            "error": data.get("error"),
        }

        if not self._day:
            attrs["status"] = "vacation"

        return attrs

class EmaktabLessonsTodaySensor(EmaktabBaseSensor):
    _attr_name = "Lessons Today"
    _attr_unique_id = "emaktab_lessons_today"

    @property
    def state(self) -> int:
        day = self._day
        if not day:
            return 0

        lessons = [
            l for l in day.get("lessons", [])
            if not l.get("isEmpty")
        ]
        return len(lessons)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        attrs = super().extra_state_attributes
        day = self._day or {}
        attrs["lessons"] = day.get("lessons", [])
        return attrs

class EmaktabHomeworkTodaySensor(EmaktabBaseSensor):
    _attr_name = "Homework Today"
    _attr_unique_id = "emaktab_homework_today"

    @property
    def state(self) -> int:
        day = self._day
        if not day:
            return 0

        count = 0
        for lesson in day.get("lessons", []):
            hw = lesson.get("homework")
            if hw and hw.get("text"):
                count += 1
        return count

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        attrs = super().extra_state_attributes
        items = []

        day = self._day or {}
        for lesson in day.get("lessons", []):
            hw = lesson.get("homework")
            if hw and hw.get("text"):
                items.append(
                    {
                        "lesson": lesson.get("number"),
                        "subject": lesson.get("subject", {}).get("name"),
                        "text": hw.get("text"),
                    }
                )

        attrs["homework"] = items
        return attrs

class EmaktabMarksTodaySensor(EmaktabBaseSensor):
    _attr_name = "Marks Today"
    _attr_unique_id = "emaktab_marks_today"

    @property
    def state(self) -> int:
        day = self._day
        if not day:
            return 0

        count = 0
        for lesson in day.get("lessons", []):
            for wm in lesson.get("workMarks", []):
                count += len(wm.get("marks", []))
        return count

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        attrs = super().extra_state_attributes
        marks = []

        day = self._day or {}
        for lesson in day.get("lessons", []):
            for wm in lesson.get("workMarks", []):
                for mark in wm.get("marks", []):
                    marks.append(
                        {
                            "lesson": lesson.get("number"),
                            "subject": lesson.get("subject", {}).get("name"),
                            "work": wm.get("workName"),
                            "value": mark.get("value"),
                        }
                    )

        attrs["marks"] = marks
        return attrs

class EmaktabImportantWorksTodaySensor(EmaktabBaseSensor):
    _attr_name = "Important Works Today"
    _attr_unique_id = "emaktab_important_works_today"

    @property
    def state(self) -> int:
        day = self._day
        if not day:
            return 0

        return len(day.get("importantWorks", []))

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        attrs = super().extra_state_attributes
        day = self._day or {}
        attrs["important_works"] = day.get("importantWorks", [])
        return attrs

class EmaktabDaySensor(EmaktabBaseSensor, SensorEntity):
    """Aggregated sensor for a school day."""

    _attr_has_entity_name = True
    _attr_name = "School Day"
    _attr_icon = "mdi:school"

    def __init__(self, coordinator, entry):
        super().__init__(coordinator)
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_day"
        self._attr_name = f"School Day ({entry.title})"

    @property
    def state(self) -> str | None:
        """Return date of the school day (YYYY-MM-DD)."""
        day = self._day
        if not day:
            return None

        try:
            ts = int(day.get("date"))
            return datetime.fromtimestamp(ts, tz=timezone.utc).date().isoformat()
        except Exception:
            return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return normalized school data."""
        attrs: dict[str, Any] = {
            "source": "emaktab",
            "student": self._entry.title,
            "school_id": self._entry.data.get("school_id"),
            "person_id": self._entry.data.get("person_id"),
        }

        day = self._day
        if not day:
            return attrs

        lessons = _normalize_lessons(day)

        attrs["lesson_count"] = len(lessons)
        attrs["lessons"] = lessons

        return attrs
    
class EmaktabAverageMarkSensor(EmaktabBaseSensor, SensorEntity):
    """Sensor calculating average mark for the school day."""

    _attr_has_entity_name = True
    _attr_icon = "mdi:calculator-variant"

    def __init__(self, coordinator, entry) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_average_mark"
        self._attr_name = f"Average Mark ({entry.title})"

    @property
    def state(self) -> float | int:
        day = self._day
        if not day:
            return 0

        marks: list[int] = []

        for lesson in _normalize_lessons(day):
            mark = lesson.get("mark")
            if not mark:
                continue

            try:
                value = int(mark.get("value"))
                marks.append(value)
            except (TypeError, ValueError):
                continue

        if not marks:
            return 0

        avg = sum(marks) / len(marks)
        return round(avg, 1)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        attrs: dict[str, Any] = {
            "source": "emaktab",
            "student": self._entry.title,
        }

        day = self._day
        if not day:
            attrs["marks_count"] = 0
            attrs["marks"] = []
            return attrs

        marks: list[int] = []

        for lesson in _normalize_lessons(day):
            mark = lesson.get("mark")
            if not mark:
                continue

            try:
                marks.append(int(mark.get("value")))
            except (TypeError, ValueError):
                continue

        attrs["marks_count"] = len(marks)
        attrs["marks"] = marks

        try:
            ts = int(day.get("date"))
            attrs["date"] = datetime.fromtimestamp(
                ts, tz=timezone.utc
            ).date().isoformat()
        except Exception:
            pass

        return attrs
