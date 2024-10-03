#!/usr/bin/python3

import os
import sys
import vlc
import argparse
from rich.console import Console
from rich.progress import Progress
from Levenshtein import distance as levenshtein_distance  # Levenshtein-Bibliothek importieren

console = Console()

def error(message, exit_code=1):
    console.print(f"[bold red]Error:[/bold red] {message}")
    sys.exit(exit_code)

def find_mp4_files(serie_path):
    """ Suche nach mp4-Dateien im angegebenen Serienverzeichnis und seinen Unterordnern. """
    mp4_files = []

    # Prüfen auf die existierende Serie im direkten Verzeichnis
    if os.path.isdir(serie_path):
        mp4_files.extend([os.path.join(serie_path, f) for f in os.listdir(serie_path) if f.endswith('.mp4')])

    # Suche nach Unterordnern
    for root, dirs, files in os.walk(os.path.dirname(serie_path)):
        if os.path.basename(root).lower() == os.path.basename(serie_path).lower():  # Exakte Übereinstimmung
            continue  # Verhindert doppelte Überprüfung des gleichen Ordners

        if os.path.basename(serie_path).lower() in root.lower():  # Substring-Übereinstimmung
            mp4_files.extend([os.path.join(root, f) for f in files if f.endswith('.mp4')])

    return mp4_files

def main():
    parser = argparse.ArgumentParser(description='Process some options.')

    parser.add_argument('--debug', action='store_true', default=False, help='Enable debug mode.')
    parser.add_argument('--maindir', type=str, required=True, help='Set main directory.')
    parser.add_argument('--serie', type=str, required=True, help='Set serie.')

    args = parser.parse_args()

    # Check if the maindir exists
    if not os.path.isdir(args.maindir):
        error(f"--maindir {args.maindir} not found")

    # Define the series path
    serie_path = os.path.join(args.maindir, args.serie)

    # Ensure the series directory exists
    if not os.path.isdir(serie_path):
        error(f"Series directory {serie_path} does not exist.", 2)

    # Find mp4 files
    mp4_files = find_mp4_files(serie_path)

    # Handle cases based on found mp4 files
    if len(mp4_files) == 0:
        error("No .mp4 files found.", 3)
    elif len(mp4_files) > 1:
        # Sort by Levenshtein distance (example to a specific string, change as needed)
        potential_matches = sorted(mp4_files, key=lambda x: levenshtein_distance(x.lower(), serie_path.lower()))
        error(f"Multiple matches found: {potential_matches}", 4)
    
    # Proceed with further logic using the found mp4 file if there's only one
    mp4_file = mp4_files[0]
    console.print(f"Found mp4 file: [bold blue]{mp4_file}[/bold blue]")

    # Here you can implement the VLC player logic if needed

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        console.print("[bold yellow]Process interrupted gracefully.[/bold yellow]")
        sys.exit(0)
