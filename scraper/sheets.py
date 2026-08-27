from __future__ import annotations

import json
import os

import gspread
from google.oauth2.service_account import Credentials

from .config import Settings
from .models import Job, SHEET_COLUMNS


SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]


class GoogleSheetsClient:
    """
    Google Sheets client.

    Local development:
        Uses GOOGLE_SERVICE_ACCOUNT_FILE if GOOGLE_SERVICE_ACCOUNT_JSON
        is not configured.

    Render / cloud deployment:
        Uses GOOGLE_SERVICE_ACCOUNT_JSON directly from the environment.
    """

    def __init__(self, settings: Settings):
        if not settings.google_sheets_url:
            raise ValueError("GOOGLE_SHEETS_URL is empty.")

        credentials = self._load_credentials(settings)

        self.client = gspread.authorize(credentials)

        try:
            self.spreadsheet = self.client.open_by_url(
                settings.google_sheets_url
            )
        except Exception as exc:
            raise RuntimeError(
                "Unable to open GOOGLE_SHEETS_URL. "
                "Check that the URL is correct and that the "
                "service account has Editor access to the sheet."
            ) from exc

    @staticmethod
    def _load_credentials(settings: Settings) -> Credentials:
        """
        Load Google credentials.

        Priority:
        1. GOOGLE_SERVICE_ACCOUNT_JSON
           Recommended for Render/cloud deployment.
        2. GOOGLE_SERVICE_ACCOUNT_FILE
           Useful for local development.
        """

        credentials_json = os.getenv(
            "GOOGLE_SERVICE_ACCOUNT_JSON"
        )

        if credentials_json:
            try:
                info = json.loads(credentials_json)
            except json.JSONDecodeError as exc:
                raise ValueError(
                    "GOOGLE_SERVICE_ACCOUNT_JSON is not valid JSON."
                ) from exc

            required_fields = [
                "type",
                "project_id",
                "private_key",
                "client_email",
                "token_uri",
            ]

            missing = [
                field
                for field in required_fields
                if not info.get(field)
            ]

            if missing:
                raise ValueError(
                    "GOOGLE_SERVICE_ACCOUNT_JSON is missing "
                    f"required fields: {', '.join(missing)}"
                )

            try:
                return Credentials.from_service_account_info(
                    info,
                    scopes=SCOPES,
                )
            except Exception as exc:
                raise ValueError(
                    "Unable to create Google credentials from "
                    "GOOGLE_SERVICE_ACCOUNT_JSON."
                ) from exc

        # Local development fallback.
        credential_file = (
            settings.google_service_account_file
            or "credentials/service-account.json"
        )

        if not os.path.exists(credential_file):
            raise FileNotFoundError(
                "Google credentials not found. Set "
                "GOOGLE_SERVICE_ACCOUNT_JSON for cloud deployment, "
                "or provide GOOGLE_SERVICE_ACCOUNT_FILE locally. "
                f"Expected local file: {credential_file}"
            )

        try:
            return Credentials.from_service_account_file(
                credential_file,
                scopes=SCOPES,
            )
        except Exception as exc:
            raise ValueError(
                "Unable to load Google service-account credentials "
                f"from: {credential_file}"
            ) from exc

    def _worksheet(self):
        """
        Return the first worksheet.

        If the spreadsheet has no accessible first sheet, create
        a 'Jobs' worksheet.
        """

        try:
            return self.spreadsheet.sheet1
        except Exception:
            return self.spreadsheet.add_worksheet(
                title="Jobs",
                rows=1000,
                cols=len(SHEET_COLUMNS),
            )

    def _ensure_header(self, ws):
        """
        Make sure the first row contains the expected headers.
        """

        existing = ws.row_values(1)

        if existing[: len(SHEET_COLUMNS)] != SHEET_COLUMNS:
            ws.update(
                "A1:H1",
                [SHEET_COLUMNS],
                value_input_option="USER_ENTERED",
            )

    def upsert_jobs(self, jobs: list[Job]) -> dict[str, int]:
        """
        Insert new jobs and update existing jobs.

        Jobs are identified by their Link.

        Existing jobs:
            - Preserve original Date Added
            - Update Last Checked
            - Update other scraped fields

        New jobs:
            - Use the Job.date_added value
            - Set Last Checked to current time
        """

        ws = self._worksheet()

        self._ensure_header(ws)

        values = ws.get_all_values()

        existing_rows = (
            values[1:]
            if len(values) > 1
            else []
        )

        # Map normalized job URL -> spreadsheet row number.
        link_to_row: dict[str, int] = {}

        for idx, row in enumerate(
            existing_rows,
            start=2,
        ):
            if len(row) >= 3:
                link = row[2].strip()

                if link:
                    normalized_link = (
                        link
                        .split("#")[0]
                        .rstrip("/")
                    )

                    link_to_row[
                        normalized_link
                    ] = idx

        added = 0
        updated = 0

        from datetime import datetime

        now = datetime.now().strftime(
            "%Y-%m-%d %H:%M:%S"
        )

        for job in jobs:
            if not job.link:
                continue

            link = (
                job.link
                .strip()
                .split("#")[0]
                .rstrip("/")
            )

            if not link:
                continue

            # Always update Last Checked.
            job.last_checked = now

            row = [
                job.company_name,
                job.role,
                job.link,
                job.location,
                job.date_added or datetime.now().strftime(
                    "%Y-%m-%d"
                ),
                job.deadline,
                job.status or "Open",
                job.last_checked,
            ]

            existing_row_number = link_to_row.get(link)

            if existing_row_number:
                # Preserve the original Date Added value.
                existing = existing_rows[
                    existing_row_number - 2
                ]

                if (
                    len(existing) >= 5
                    and existing[4].strip()
                ):
                    row[4] = existing[4]

                ws.update(
                    f"A{existing_row_number}:H{existing_row_number}",
                    [row],
                    value_input_option="USER_ENTERED",
                )

                updated += 1

            else:
                ws.append_row(
                    row,
                    value_input_option="USER_ENTERED",
                )

                added += 1

        total_values = ws.get_all_values()

        return {
            "added": added,
            "updated": updated,
            "total": max(len(total_values) - 1, 0),
        }