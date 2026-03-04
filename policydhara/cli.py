"""
PolicyDhara CLI — search, filter, classify, and explore Indian policy data.

Usage:
    policydhara search "renewable energy"
    policydhara filter --sector Health --state Maharashtra
    policydhara classify "National EV Charging Infrastructure Scheme"
    policydhara stats
    policydhara export --format csv --sector Education > education.csv
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import click

from policydhara import __version__
from policydhara.classifier import PolicyClassifier
from policydhara.store import PolicyStore


def _load_store(data: str | None) -> PolicyStore:
    """Load the policy store, with helpful error messages."""
    try:
        return PolicyStore.load(data)
    except FileNotFoundError:
        click.echo(
            "Error: No policies.json found. Run from the project root "
            "or pass --data path/to/policies.json",
            err=True,
        )
        sys.exit(1)


@click.group()
@click.version_option(__version__, prog_name="policydhara")
def cli():
    """PolicyDhara — Indian development policy tracker."""
    pass


@cli.command()
@click.argument("query")
@click.option("--sector", "-s", help="Filter by sector name")
@click.option("--limit", "-n", default=20, help="Max results (default: 20)")
@click.option("--data", "-d", help="Path to policies.json")
def search(query: str, sector: str | None, limit: int, data: str | None):
    """Search policies by keyword."""
    store = _load_store(data)

    if sector:
        results = store.query(text=query, sector=sector, limit=limit)
    else:
        results = store.search(query, limit=limit)

    if not results:
        click.echo(f"No policies found for '{query}'")
        return

    click.echo(f"Found {len(results)} {'result' if len(results) == 1 else 'results'}:\n")
    for p in results:
        sectors = ", ".join(p.sectors) if p.sectors else "—"
        click.echo(f"  [{p.date}] {p.title}")
        click.echo(f"           {sectors} | {p.source_short or p.source_name} | {p.type}")
        if p.link:
            click.echo(f"           {p.link}")
        click.echo()


@cli.command("filter")
@click.option("--sector", "-s", help="Filter by sector")
@click.option("--state", help="Filter by state")
@click.option("--type", "policy_type", help="Filter by type (legislation, scheme, etc.)")
@click.option("--source", help="Filter by source ID")
@click.option("--level", help="Filter by level (central, state)")
@click.option("--from", "date_start", help="Start date (YYYY-MM-DD)")
@click.option("--to", "date_end", help="End date (YYYY-MM-DD)")
@click.option("--limit", "-n", default=0, help="Max results (0 = all)")
@click.option("--data", "-d", help="Path to policies.json")
def filter_cmd(sector, state, policy_type, source, level, date_start, date_end, limit, data):
    """Filter policies by sector, state, type, source, date."""
    store = _load_store(data)

    results = store.query(
        sector=sector,
        state=state,
        policy_type=policy_type,
        source=source,
        level=level,
        date_start=date_start,
        date_end=date_end,
        limit=limit,
    )

    if not results:
        click.echo("No matching policies found.")
        return

    click.echo(f"Found {len(results)} {'policy' if len(results) == 1 else 'policies'}:\n")
    for p in results:
        sectors = ", ".join(p.sectors)
        click.echo(f"  [{p.date}] {p.title}")
        click.echo(f"           {sectors} | {p.type}")
        click.echo()


@cli.command()
@click.argument("text")
def classify(text: str):
    """Classify a policy title/description into sectors."""
    classifier = PolicyClassifier()
    scores = classifier.scores(text)

    if not scores:
        click.echo(f"No sectors matched for: {text}")
        click.echo("Default fallback: Governance & Reform")
        return

    click.echo(f"Classification for: {text}\n")
    for sector, score in scores.items():
        bar = "#" * score
        click.echo(f"  {sector:<30} {bar} ({score})")


@cli.command()
@click.option("--data", "-d", help="Path to policies.json")
def stats(data: str | None):
    """Show summary statistics."""
    store = _load_store(data)

    click.echo(f"\n  PolicyDhara Statistics")
    click.echo(f"  {'=' * 40}")
    click.echo(f"  Total policies:    {len(store)}")

    dates = [p.date for p in store.policies if p.date]
    if dates:
        click.echo(f"  Date range:        {min(dates)} to {max(dates)}")

    sectors = store.sector_counts()
    click.echo(f"  Sectors:           {len(sectors)}")

    sources = store.source_counts()
    click.echo(f"  Sources:           {len(sources)}")

    types = store.type_counts()
    click.echo(f"  Types:             {len(types)}")

    click.echo(f"\n  Top Sectors:")
    for sector, count in list(sectors.items())[:10]:
        click.echo(f"    {sector:<30} {count}")

    click.echo(f"\n  Policy Types:")
    for t, count in types.items():
        click.echo(f"    {t:<20} {count}")

    click.echo()


@cli.command()
@click.option("--format", "fmt", type=click.Choice(["json", "csv"]), default="json", help="Output format")
@click.option("--sector", "-s", help="Filter by sector before export")
@click.option("--state", help="Filter by state before export")
@click.option("--output", "-o", help="Output file (default: stdout)")
@click.option("--data", "-d", help="Path to policies.json")
def export(fmt: str, sector: str | None, state: str | None, output: str | None, data: str | None):
    """Export policies as JSON or CSV."""
    store = _load_store(data)

    if sector or state:
        results = store.query(sector=sector, state=state)
        store = PolicyStore(results)

    if fmt == "csv":
        content = store.to_csv(output)
    else:
        content = store.to_json(output)

    if not output:
        click.echo(content)
    else:
        click.echo(f"Exported {len(store)} policies to {output}")


@cli.command()
def sectors():
    """List all 21 tracked sectors."""
    classifier = PolicyClassifier()
    click.echo(f"\n  PolicyDhara tracks {len(classifier.sectors)} sectors:\n")
    for i, sector in enumerate(classifier.sectors, 1):
        click.echo(f"  {i:>2}. {sector}")
    click.echo()


def main():
    cli()


if __name__ == "__main__":
    main()
