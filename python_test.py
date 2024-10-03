#!/usr/bin/python3

import os
import sys
import vlc
import argparse
from rich.console import Console
from rich.progress import Progress
import subprocess

console = Console()

def error(message, exit_code=1):
    console.print(f"[bold red]Error:[/bold red] {message}")
    sys.exit(exit_code)

def ask_for_series_name():
    try:
        # Use whiptail to ask for the series name
        result = subprocess.run(
            ['whiptail', '--inputbox', 'Enter the series name:', '10', '60', ''],
            capture_output=True,
            text=True
        )
        return result.stdout.strip()  # Return the input
    except Exception as e:
        error(f"Failed to get input: {e}")

def main():
    parser = argparse.ArgumentParser(description='Process some options.')

    parser.add_argument('--debug', action='store_true', default=False, help='Enable debug mode.')
    parser.add_argument('--debuglevel', type=int, default=None, help='Set debug level.')
    parser.add_argument('--noplay', action='store_true', default=False, help='Disable play mode.')
    parser.add_argument('--maindir', type=str, required=True, help='Set main directory.')
    parser.add_argument('--serie', type=str, default=None, help='Set serie.')
    parser.add_argument('--zufall', action='store_true', default=False, help='Enable random mode.')
    parser.add_argument('--staffel', type=int, default=None, help='Set staffel.')
    parser.add_argument('--min_staffel', type=int, default=None, help='Set minimum staffel.')
    parser.add_argument('--max_staffel', type=int, default=None, help='Set maximum staffel.')
    parser.add_argument('--min_percentage_runtime_to_count', type=float, default=None, help='Set minimum percentage runtime to count.')

    args = parser.parse_args()

    # Check if the maindir exists
    if not os.path.isdir(args.maindir):
        error(f"--maindir {args.maindir} not found")

    # Ask for series name if not provided
    series_name = args.serie if args.serie else ask_for_series_name()
    
    # Create the options dictionary with defaults from argparse
    options = vars(args)
    options['serie'] = series_name

    # Set the dbfile path based on maindir
    options['dbfile'] = os.path.join(options['maindir'], ".db.txt")

    # Search for directories that only contain numbers and list mp4 files
    with Progress() as progress:
        task = progress.add_task("[cyan]Searching for directories...[/cyan]", total=None)

        for entry in os.listdir(options['maindir']):
            full_path = os.path.join(options['maindir'], entry)

            # Check if the entry is a directory and consists only of numbers
            if os.path.isdir(full_path) and entry.isdigit():
                mp4_files = [f for f in os.listdir(full_path) if f.endswith('.mp4')]
                if mp4_files:
                    progress.update(task, advance=1)
                    console.print(f"\nFound directory: [bold green]{full_path}[/bold green]")
                    for mp4 in mp4_files:
                        console.print(f" - [bold blue]{mp4}[/bold blue]")
        
        progress.stop()

if __name__ == '__main__':
    main()

