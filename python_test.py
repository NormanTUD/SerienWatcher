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

def find_mp4_files(directory):
    #print(directory)
    """ Suche nach MP4-Dateien im angegebenen Verzeichnis. """
    mp4_files = []

    with Progress(transient=True) as progress:
        task = progress.add_task("[cyan]Durchsuche nach MP4-Dateien...", total=len(os.listdir(directory)))
        
        for season in os.listdir(directory):
            # Durchsuche die Dateien im angegebenen Verzeichnis
            for file_name in os.listdir(os.path.join(directory, season)):
                full_path = os.path.join(directory,  season, file_name)

                if os.path.isfile(full_path) and file_name.lower().endswith('.mp4'):
                    mp4_files.append(full_path)

            # Fortschritt aktualisieren
            progress.update(task, advance=1)

    # Überprüfen der gefundenen MP4-Dateien
    if len(mp4_files) == 0:
        error("Keine MP4-Dateien gefunden.", 3)
    
    return mp4_files

def find_series_directory(serie_name, maindir):
    exact_matches = []
    substring_matches = []
    potential_matches = []

    with Progress(transient=True) as progress:
        task = progress.add_task("[cyan]Durchsuche Verzeichnisse...", total=len(os.listdir(maindir)))

        for dir_name in os.listdir(maindir):
            full_path = os.path.join(maindir, dir_name)
            if os.path.isdir(full_path):
                if dir_name == serie_name:
                    exact_matches.append(full_path)
                elif dir_name.lower() == serie_name.lower():
                    exact_matches.append(full_path)
                elif serie_name.lower() in dir_name.lower():
                    substring_matches.append(full_path)
                else:
                    potential_matches.append(dir_name)

            progress.update(task, advance=1)

    if len(exact_matches) == 1:
        return exact_matches[0]
    elif len(exact_matches) > 1:
        error(f"Mehrere exakte Übereinstimmungen gefunden: {exact_matches}", 5)
    elif len(substring_matches) == 1:
        return substring_matches[0]
    elif len(substring_matches) > 1:
        error(f"Mehrere Substring-Übereinstimmungen gefunden: {substring_matches}", 6)

    # Suggest closest match using Levenshtein distance
    if potential_matches:
        closest_match = min(potential_matches, key=lambda x: levenshtein_distance(x.lower(), serie_name.lower()))
        error(f"Kein passendes Serienverzeichnis gefunden. Nahegelegene Übereinstimmung: {closest_match}", 3)

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
    mp4_files = find_mp4_files(os.path.join(args.maindir, serie_name))

    # Handle cases based on found mp4 files
    if len(mp4_files) == 0:
        error("No .mp4 files found.", 3)

    print(mp4_files)

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        console.print("[bold yellow]Process interrupted gracefully.[/bold yellow]")
        sys.exit(0)
