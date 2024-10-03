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

def find_mp4_files(serie_name, maindir):
    """ Suche nach mp4-Dateien basierend auf dem Seriennamen im angegebenen Verzeichnis. """
    mp4_files = []

    # Suche nach dem genauen Verzeichnis
    serie_path = os.path.join(maindir, serie_name)
    if os.path.isdir(serie_path):
        # Suche nach mp4-Dateien in diesem Verzeichnis und dessen Unterverzeichnissen
        for root, dirs, files in os.walk(serie_path):
            mp4_files.extend([os.path.join(root, f) for f in files if f.endswith('.mp4')])
    else:
        print(f"{serie_path} not found")


    # Suche nach Unterordnern, die den Seriennamen als Substring enthalten
    for root, dirs, files in os.walk(maindir):
        # Überprüfen, ob der Ordnername den Seriennamen als Substring enthält
        if serie_name.lower() in os.path.basename(root).lower():
            mp4_files.extend([os.path.join(root, f) for f in files if f.endswith('.mp4')])

    return mp4_files

def find_series_directory(serie_name, maindir):
    """ Suche nach dem Serienverzeichnis im Hauptverzeichnis. """
    exact_matches = []
    substring_matches = []

    # Durchsuche die Verzeichnisse im Hauptverzeichnis
    for dir_name in os.listdir(maindir):
        full_path = os.path.join(maindir, dir_name)

        if os.path.isdir(full_path):
            # Überprüfen auf exakte Übereinstimmung (case-sensitive)
            if dir_name == serie_name:
                exact_matches.append(full_path)
            # Überprüfen auf exakte Übereinstimmung (case-insensitive)
            elif dir_name.lower() == serie_name.lower():
                exact_matches.append(full_path)
            # Überprüfen auf Substring-Übereinstimmung (case-insensitive)
            elif serie_name.lower() in dir_name.lower():
                substring_matches.append(full_path)

    # Überprüfen der gefundenen Übereinstimmungen
    if len(exact_matches) == 1:
        return exact_matches[0]
    elif len(exact_matches) > 1:
        error(f"Mehrere exakte Übereinstimmungen gefunden: {exact_matches}", 5)
    elif len(substring_matches) == 1:
        return substring_matches[0]
    elif len(substring_matches) > 1:
        error(f"Mehrere Substring-Übereinstimmungen gefunden: {substring_matches}", 6)
    
    error("Kein passendes Serienverzeichnis gefunden.", 3)

def main():
    parser = argparse.ArgumentParser(description='Process some options.')

    parser.add_argument('--debug', action='store_true', default=False, help='Enable debug mode.')
    parser.add_argument('--maindir', type=str, required=True, help='Set main directory.')
    parser.add_argument('--serie', type=str, required=True, help='Set serie.')

    args = parser.parse_args()

    # Check if the maindir exists
    if not os.path.isdir(args.maindir):
        error(f"--maindir {args.maindir} not found")

    # Define the series name
    serie_name = find_series_directory(args.serie, args.maindir)

    # Find mp4 files
    mp4_files = find_mp4_files(serie_name, args.maindir)

    # Handle cases based on found mp4 files
    if len(mp4_files) == 0:
        error("No .mp4 files found.", 3)
    elif len(mp4_files) > 1:
        # Sort by Levenshtein distance (example to a specific string, change as needed)
        potential_matches = sorted(mp4_files, key=lambda x: levenshtein_distance(x.lower(), serie_name.lower()))
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
