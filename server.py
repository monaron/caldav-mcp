"""
CalDAV MCP Server — Calendar operations via FastMCP streamable-http.
Credentials are per-call (not pod-level). Each user passes their own CalDAV config.
"""
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

import caldav
from fastmcp import FastMCP

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("caldav-mcp")

PORT = 8769

mcp = FastMCP("caldav-mcp")


def _resolve(url: str = "", username: str = "", password: str = ""):
    from fastmcp.server.dependencies import get_http_request
    try:
        hdrs = get_http_request().headers
    except RuntimeError:
        hdrs = {}
    u = url or hdrs.get("x-caldav-url", "")
    un = username or hdrs.get("x-caldav-username", "")
    pw = password or hdrs.get("x-caldav-password", "")
    if not u or not un or not pw:
        raise ValueError("Credentials required (params or x-caldav-* headers)")
    return u, un, pw


def _get_client(url: str, username: str, password: str) -> caldav.DAVClient:
    return caldav.DAVClient(url=url, username=username, password=password)


def _format_dt(dt):
    if dt is None:
        return None
    if hasattr(dt, "isoformat"):
        return dt.isoformat()
    return str(dt)


@mcp.tool()
def list_calendars(
    caldav_url: str = "",
    caldav_username: str = "",
    caldav_password: str = "",
) -> Dict[str, Any]:
    """List all available calendars.

    Args:
        caldav_url: CalDAV server URL (e.g. https://caldav.icloud.com)
        caldav_username: Username
        caldav_password: Password or app-specific password
    """
    try:
        url, username, password = _resolve(caldav_url, caldav_username, caldav_password)
        client = _get_client(url, username, password)
        principal = client.principal()
        calendars = principal.calendars()
        result = []
        for cal in calendars:
            result.append({
                "name": cal.name,
                "url": str(cal.url) if cal.url else None,
            })
        return {"count": len(result), "calendars": result}
    except Exception as e:
        return {"error": str(e)}


@mcp.tool()
def list_events(
    caldav_url: str = "",
    caldav_username: str = "",
    caldav_password: str = "",
    start: str,
    end: str,
    calendar_name: Optional[str] = None,
    calendar_url: Optional[str] = None,
) -> Dict[str, Any]:
    """List events in a time range.

    Args:
        caldav_url: CalDAV server URL
        caldav_username: Username
        caldav_password: Password
        start: Start datetime ISO 8601 (e.g. 2026-07-01T00:00:00)
        end: End datetime ISO 8601
        calendar_name: Calendar name filter (e.g. "personal")
        calendar_url: Exact calendar URL (overrides calendar_name)
    """
    try:
        url, username, password = _resolve(caldav_url, caldav_username, caldav_password)
        client = _get_client(url, username, password)
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
            calendars = principal.calendars()
            cal = calendars[0] if calendars else None
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
    caldav_url: str = "",
    caldav_username: str = "",
    caldav_password: str = "",
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
        caldav_url: CalDAV server URL
        caldav_username: Username
        caldav_password: Password
        summary: Event title
        start: Start datetime ISO 8601
        end: End datetime ISO 8601
        calendar_name: Target calendar name (uses first if omitted)
        calendar_url: Exact calendar URL (overrides calendar_name)
        description: Event description
        location: Event location
    """
    try:
        url, username, password = _resolve(caldav_url, caldav_username, caldav_password)
        client = _get_client(url, username, password)
        principal = client.principal()

        if calendar_url:
            cal = [c for c in principal.calendars() if str(c.url) == calendar_url]
            cal = cal[0] if cal else None
        elif calendar_name:
            cal = next((c for c in principal.calendars() if c.name.lower() == calendar_name.lower()), None)
        else:
            calendars = principal.calendars()
            cal = calendars[0] if calendars else None

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
        }
    except Exception as e:
        return {"error": str(e)}


@mcp.tool()
def update_event(
    caldav_url: str = "",
    caldav_username: str = "",
    caldav_password: str = "",
    uid: str,
    calendar_name: Optional[str] = None,
    calendar_url: Optional[str] = None,
    summary: Optional[str] = None,
    start: Optional[str] = None,
    end: Optional[str] = None,
    description: Optional[str] = None,
    location: Optional[str] = None,
) -> Dict[str, Any]:
    """Update an existing event by UID.

    Args:
        caldav_url: CalDAV server URL
        caldav_username: Username
        caldav_password: Password
        uid: Event UID
        calendar_name: Calendar name filter
        calendar_url: Exact calendar URL (overrides calendar_name)
        summary: New title
        start: New start datetime ISO 8601
        end: New end datetime ISO 8601
        description: New description
        location: New location
    """
    try:
        url, username, password = _resolve(caldav_url, caldav_username, caldav_password)
        client = _get_client(url, username, password)
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
                for ev in cal.events():
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
                            return {"uid": uid, "summary": str(vevent.summary.value), "updated": True}
                    except Exception:
                        continue
            except Exception:
                continue

        return {"error": f"Event not found: {uid}"}
    except Exception as e:
        return {"error": str(e)}


@mcp.tool()
def delete_event(
    caldav_url: str = "",
    caldav_username: str = "",
    caldav_password: str = "",
    uid: str,
    calendar_name: Optional[str] = None,
    calendar_url: Optional[str] = None,
) -> Dict[str, Any]:
    """Delete an event by UID.

    Args:
        caldav_url: CalDAV server URL
        caldav_username: Username
        caldav_password: Password
        uid: Event UID
        calendar_name: Calendar name filter
        calendar_url: Exact calendar URL (overrides calendar_name)
    """
    try:
        url, username, password = _resolve(caldav_url, caldav_username, caldav_password)
        client = _get_client(url, username, password)
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
                for ev in cal.events():
                    try:
                        vevent = ev.instance.vevent
                        if vevent.uid and str(vevent.uid.value) == uid:
                            sv = str(vevent.summary.value) if vevent.summary else "unknown"
                            ev.delete()
                            return {"uid": uid, "summary": sv, "deleted": True}
                    except Exception:
                        continue
            except Exception:
                continue

        return {"error": f"Event not found: {uid}"}
    except Exception as e:
        return {"error": str(e)}


def main():
    logger.info(f"Starting CalDAV MCP server on 0.0.0.0:{PORT}")
    mcp.run(transport="http", host="0.0.0.0", port=PORT)


if __name__ == "__main__":
    main()
