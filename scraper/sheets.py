from __future__ import annotations

import os
from datetime import datetime

import gspread
from google.oauth2.service_account import Credentials

from .config import Settings
from .models import Job, SHEET_COLUMNS


SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]


class GoogleSheetsClient:
    def __init__(self, settings: Settings):
        if not settings.google_sheets_url:
            raise ValueError("GOOGLE_SHEETS_URL is empty.")

        if not os.path.exists(settings.google_service_account_file):
            raise FileNotFoundError(
                "Google service account file not found: "
                f"{settings.google_service_account_file}"
            )

        credentials = Credentials.from_service_account_file(
            settings.google_service_account_file,
            scopes=SCOPES,
        )
        self.client = gspread.authorize(credentials)
        self.spreadsheet = self.client.open_by_url(
            settings.google_sheets_url
        )

    def _worksheet(self):
        try:
            return self.spreadsheet.sheet1
        except Exception:
            return self.spreadsheet.add_worksheet(
                title="Jobs",
                rows=1000,
                cols=len(SHEET_COLUMNS),
            )

    def _ensure_header(self, ws):
        existing = ws.row_values(1)

        if existing[: len(SHEET_COLUMNS)] != SHEET_COLUMNS:
            ws.update(
                "A1:H1",
                [SHEET_COLUMNS],
                value_input_option="USER_ENTERED",
            )

    def upsert_jobs(self, jobs: list[Job]) -> dict[str, int]:
        ws = self._worksheet()
        self._ensure_header(ws)

        values = ws.get_all_values()
        existing_rows = values[1:] if len(values) > 1 else []

        link_to_row = {}
        for idx, row in enumerate(existing_rows, start=2):
            if len(row) >= 3 and row[2].strip():
                link_to_row[row[2].strip().rstrip("/")] = idx

        added = 0
        updated = 0
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        for job in jobs:
            link = job.link.strip().rstrip("/")
            if not link:
                continue

            job.last_checked = now
            row = [
                job.company_name,
                job.role,
                job.link,
                job.location,
                job.date_added or datetime.now().strftime("%Y-%m-%d"),
                job.deadline,
                job.status or "Open",
                job.last_checked,
            ]

            existing_row_number = link_to_row.get(link)

            if existing_row_number:
                # Preserve original Date Added when updating an existing row.
                existing = existing_rows[existing_row_number - 2]
                if len(existing) >= 5 and existing[4].strip():
                    row[4] = existing[4]

                ws.update(
                    f"A{existing_row_number}:H{existing_row_number}",
                    [row],
                    value_input_option="USER_ENTERED",
                )
                updated += 1
            else:
                ws.append_row(row, value_input_option="USER_ENTERED")
                added += 1

        return {
            "added": added,
            "updated": updated,
            "total": len(ws.get_all_values()) - 1,
        }
