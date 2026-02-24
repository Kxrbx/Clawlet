"""
Health command module.
"""

import asyncio

import typer

from clawlet.cli import __version__, app, console, print_section, print_footer
from clawlet.health import quick_health_check


@app.command(name="health")
def health():
    """🌸 Run health checks on all components."""
    print_section("Health Checks", "Checking system components")
    
    async def run_checks():
        result = await quick_health_check()
        return result
    
    result = asyncio.run(run_checks())
    
    # Display results
    for check in result.get("checks", []):
        status = check["status"]
        if status == "healthy":
            console.print(f"│  [green]✓[/green] {check['name']}: {check['message']}")
        elif status == "degraded":
            console.print(f"│  [yellow]![/yellow] {check['name']}: {check['message']}")
        else:
            console.print(f"│  [red]✗[/red] {check['name']}: {check['message']}")
    
    print_footer()
    
    # Overall status
    overall = result.get("status", "unknown")
    console.print()
    if overall == "healthy":
        console.print("[green]✓ All systems operational[/green]")
    elif overall == "degraded":
        console.print("[yellow]! Some systems degraded[/yellow]")
    else:
        console.print("[red]✗ Some systems unhealthy[/red]")
    console.print()
