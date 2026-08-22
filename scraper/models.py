from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


SHEET_COLUMNS = [
    "Company Name",
    "Role",
    "Link",
    "Location",
    "Date Added",
    "Deadline",
    "Status",
    "Last Checked",
]


@dataclass
class Job:
    company_name: str = ""
    role: str = ""
    link: str = ""
    location: str = ""
    date_added: str = ""
    deadline: str = ""
    status: str = "Open"
    last_checked: str = ""
    source: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "Company Name": self.company_name,
            "Role": self.role,
            "Link": self.link,
            "Location": self.location,
            "Date Added": self.date_added,
            "Deadline": self.deadline,
            "Status": self.status,
            "Last Checked": self.last_checked,
            "Source": self.source,
        }

    @classmethod
    def from_dict(cls, row: dict[str, Any]) -> "Job":
        return cls(
            company_name=str(row.get("Company Name", "")),
            role=str(row.get("Role", "")),
            link=str(row.get("Link", "")),
            location=str(row.get("Location", "")),
            date_added=str(row.get("Date Added", "")),
            deadline=str(row.get("Deadline", "")),
            status=str(row.get("Status", "Open")),
            last_checked=str(row.get("Last Checked", "")),
            source=str(row.get("Source", "")),
        )
