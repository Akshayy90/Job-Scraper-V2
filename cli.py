import argparse
from pathlib import Path

import pandas as pd
from rich.console import Console
from rich.table import Table

from scraper.config import get_settings
from scraper.pipeline import run_pipeline
from scraper.sheets import GoogleSheetsClient

console = Console()


def print_jobs(jobs):
    table = Table(title=f"Scraped Jobs ({len(jobs)})")
    table.add_column("Company", overflow="fold")
    table.add_column("Role", overflow="fold")
    table.add_column("Location", overflow="fold")
    table.add_column("Link", overflow="fold")

    for job in jobs:
        table.add_row(
            job.company_name,
            job.role,
            job.location,
            job.link,
        )

    console.print(table)


def save_csv(jobs, path):
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame([job.to_dict() for job in jobs]).to_csv(output, index=False)
    console.print(f"[green]Saved:[/green] {output.resolve()}")


def scrape_command(args):
    settings = get_settings()
    jobs = run_pipeline(settings)
    print_jobs(jobs)

    if args.csv:
        save_csv(jobs, args.csv)

    if args.sync:
        client = GoogleSheetsClient(settings)
        result = client.upsert_jobs(jobs)
        console.print(
            f"[green]Sheets:[/green] {result['added']} added, "
            f"{result['updated']} updated, "
            f"{result['total']} total"
        )


def sync_command(args):
    settings = get_settings()
    path = Path(args.csv)

    if not path.exists():
        raise FileNotFoundError(path)

    df = pd.read_csv(path).fillna("")
    from scraper.models import Job

    jobs = [Job.from_dict(row.to_dict()) for _, row in df.iterrows()]
    client = GoogleSheetsClient(settings)
    result = client.upsert_jobs(jobs)

    console.print(
        f"[green]Sheets:[/green] {result['added']} added, "
        f"{result['updated']} updated, "
        f"{result['total']} total"
    )


def main():
    parser = argparse.ArgumentParser(description="Multi-site job scraper")
    sub = parser.add_subparsers(dest="command", required=True)

    scrape = sub.add_parser("scrape", help="Scrape configured target URLs")
    scrape.add_argument("--csv", help="Save scraped jobs to CSV")
    scrape.add_argument(
        "--sync",
        action="store_true",
        help="Also synchronize scraped jobs to Google Sheets",
    )
    scrape.set_defaults(func=scrape_command)

    run = sub.add_parser("run", help="Scrape and optionally sync")
    run.add_argument("--sync", action="store_true")
    run.add_argument("--csv", default="output/jobs.csv")
    run.set_defaults(func=scrape_command)

    sync = sub.add_parser("sync", help="Sync an existing CSV to Google Sheets")
    sync.add_argument("--csv", required=True)
    sync.set_defaults(func=sync_command)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
