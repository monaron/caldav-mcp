"""
CalDAV MCP Server — Calendar operations via FastMCP streamable-http.
"""
import os
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import caldav
from fastmcp import FastMCP

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("caldav-mcp")

PORT = int(os.environ.get("PORT", "8769"))

CALDAV_URL = os.environ.get("CALDAV_URL", "")
CALDAV_USERNAME = os.environ.get("CALDAV_USERNAME", "")
CALDAV_PASSWORD = os.environ.get("CALDAV_PASSWORD", "")

mcp = FastMCP("caldav-mcp")


def _get_client() -> caldav.DAVClient:
    if not CALDAV_URL or not CALDAV_USERNAME or not CALDAV_PASSWORD:
        raise RuntimeError("CALDAV_URL, CALDAV_USERNAME, CALDAV_PASSWORD must be set")
    return caldav.DAVClient(url=CALDAV_URL, username=CALDAV_USERNAME, password=CALDAV_PASSWORD)


def _format_dt(dt):
    if dt is None:
        return None
    if hasattr(dt, "isoformat"):
        return dt.isoformat()
    return str(dt)


@mcp.tool()
def list_calendars() -> Dict[str, Any]:
    """List all available calendars with name and URL.

    Returns:
        List of calendars with name, url, and CTAG
    """
    try:
        client = _get_client()
        principal = client.principal()
        calendars = principal.calendars()
        result = []
        for cal in calendars:
            result.append({
                "name": cal.name,
                "url": str(cal.url) if cal.url else None,
                "ctag": cal.get_property(caldav.elements.cdav.CTag()),
            })
        return {"count": len(result), "calendars": result}
    except Exception as e:
        return {"error": str(e)}


@mcp.tool()
def list_events(
    start: str,
    end: str,
    calendar_name: Optional[str] = None,
    calendar_url: Optional[str] = None,
) -> Dict[str, Any]:
    """List events in a time range from a calendar.

    Args:
        start: Start datetime ISO 8601 (e.g. 2026-07-01T00:00:00)
        end: End datetime ISO 8601
        calendar_name: Calendar name filter (e.g. "personal", "work")
        calendar_url: Exact calendar URL (overrides calendar_name if set)

    Returns:
        List of events with uid, summary, start, end, description, location
    """
    try:
        client = _get_client()
        principal = client.principal()

        if calendar_url:
            cal = [c for c in principal.calendars() if str(c.url) == calendar_url]
            cal = cal[0] if cal else None
            if cal is None:
                return {"error": f"Calendar not found: {calendar_url}"}
        elif calendar_name:
            cal = next((c for c in principal.calendars() if c.name.lower() == calendar_name.lower()), None)
            if cal is None:
                return {"error": f"Calendar not found: {calendar_name}"}
        else:
            cal = principal.calendars()[0] if principal.calendars() else None
            if cal is None:
                return {"error": "No calendars available"}

        try:
            events = cal.date_search(start=start, end=end, expand=True)
        except Exception:
            events = cal.search(start=datetime.fromisoformat(start), end=datetime.fromisoformat(end), expand=True)

        result = []
        for ev in events:
            try:
                vevent = ev.instance.vevent
                result.append({
                    "uid": str(vevent.uid.value) if vevent.uid else None,
                    "summary": str(vevent.summary.value) if vevent.summary else "",
                    "start": _format_dt(getattr(vevent.dtstart, "value", None)),
                    "end": _format_dt(getattr(vevent.dtend, "value", None)),
                    "description": str(getattr(vevent.description, "value", "")) if hasattr(vevent, "description") and vevent.description is not None else "",
                    "location": str(getattr(vevent.location, "value", "")) if hasattr(vevent, "location") and vevent.location is not None else "",
                })
            except Exception:
                continue

        return {"calendar": calendar_name or calendar_url or "default", "start": start, "end": end, "count": len(result), "events": result}
    except Exception as e:
        return {"error": str(e)}


@mcp.tool()
def create_event(
    summary: str,
    start: str,
    end: str,
    calendar_name: Optional[str] = None,
    calendar_url: Optional[str] = None,
    description: Optional[str] = None,
    location: Optional[str] = None,
) -> Dict[str, Any]:
    """Create a calendar event.

    Args:
        summary: Event title
        start: Start datetime ISO 8601
        end: End datetime ISO 8601
        calendar_name: Target calendar name (uses first if omitted)
        calendar_url: Exact calendar URL (overrides calendar_name)
        description: Event description
        location: Event location

    Returns:
        Created event UID and details
    """
    try:
        client = _get_client()
        principal = client.principal()

        if calendar_url:
            cal = [c for c in principal.calendars() if str(c.url) == calendar_url]
            cal = cal[0] if cal else None
        elif calendar_name:
            cal = next((c for c in principal.calendars() if c.name.lower() == calendar_name.lower()), None)
        else:
            cal = principal.calendars()[0] if principal.calendars() else None

        if cal is None:
            return {"error": "Calendar not found"}

        ev = cal.save_event(
            dtstart=datetime.fromisoformat(start),
            dtend=datetime.fromisoformat(end),
            summary=summary,
            description=description or "",
            location=location or "",
        )
        return {
            "uid": ev.url.split("/")[-1].replace(".ics", "") if ev.url else None,
            "summary": summary,
            "start": start,
            "end": end,
            "calendar": calendar_name or calendar_url or "default",
        }
    except Exception as e:
        return {"error": str(e)}


@mcp.tool()
def update_event(
    uid: str,
    calendar_url: Optional[str] = None,
    calendar_name: Optional[str] = None,
    summary: Optional[str] = None,
    start: Optional[str] = None,
    end: Optional[str] = None,
    description: Optional[str] = None,
    location: Optional[str] = None,
) -> Dict[str, Any]:
    """Update an existing calendar event by UID.

    Args:
        uid: Event UID
        calendar_url: Calendar URL (optional, searches all if omitted)
        calendar_name: Calendar name filter (optional)
        summary: New title
        start: New start datetime ISO 8601
        end: New end datetime ISO 8601
        description: New description
        location: New location

    Returns:
        Updated event details
    """
    try:
        client = _get_client()
        principal = client.principal()

        if calendar_url:
            calendars = [c for c in principal.calendars() if str(c.url) == calendar_url]
        elif calendar_name:
            calendars = [c for c in principal.calendars() if c.name.lower() == calendar_name.lower()]
        else:
            calendars = principal.calendars()

        if not calendars:
            return {"error": "No calendars found"}

        for cal in calendars:
            try:
                events = cal.events()
                for ev in events:
                    try:
                        vevent = ev.instance.vevent
                        if vevent.uid and str(vevent.uid.value) == uid:
                            vevent.summary.value = summary or str(vevent.summary.value)
                            if start:
                                vevent.dtstart.value = datetime.fromisoformat(start)
                            if end:
                                vevent.dtend.value = datetime.fromisoformat(end)
                            if description is not None:
                                vevent.description.value = description
                            if location is not None:
                                vevent.location.value = location
                            ev.save()
                            return {
                                "uid": uid,
                                "summary": str(vevent.summary.value),
                                "start": _format_dt(getattr(vevent.dtstart, "value", None)),
                                "end": _format_dt(getattr(vevent.dtend, "value", None)),
                                "updated": True,
                            }
                    except Exception:
                        continue
            except Exception:
                continue

        return {"error": f"Event not found: {uid}", "uid": uid}
    except Exception as e:
        return {"error": str(e), "uid": uid}


@mcp.tool()
def delete_event(
    uid: str,
    calendar_url: Optional[str] = None,
    calendar_name: Optional[str] = None,
) -> Dict[str, Any]:
    """Delete a calendar event by UID.

    Args:
        uid: Event UID
        calendar_url: Calendar URL (optional, searches all if omitted)
        calendar_name: Calendar name filter (optional)

    Returns:
        Deletion confirmation
    """
    try:
        client = _get_client()
        principal = client.principal()

        if calendar_url:
            calendars = [c for c in principal.calendars() if str(c.url) == calendar_url]
        elif calendar_name:
            calendars = [c for c in principal.calendars() if c.name.lower() == calendar_name.lower()]
        else:
            calendars = principal.calendars()

        if not calendars:
            return {"error": "No calendars found"}

        for cal in calendars:
            try:
                events = cal.events()
                for ev in events:
                    try:
                        vevent = ev.instance.vevent
                        if vevent.uid and str(vevent.uid.value) == uid:
                            summary = str(vevent.summary.value) if vevent.summary else "unknown"
                            ev.delete()
                            return {"uid": uid, "summary": summary, "deleted": True}
                    except Exception:
                        continue
            except Exception:
                continue

        return {"error": f"Event not found: {uid}", "uid": uid}
    except Exception as e:
        return {"error": str(e), "uid": uid}


def main():
    logger.info(f"Starting CalDAV MCP server on 0.0.0.0:{PORT}")
    mcp.run(transport="http", host="0.0.0.0", port=PORT)


if __name__ == "__main__":
    main()
