#!/usr/bin/python3

import os
import sys
import vlc
import argparse
import random
import time
from rich.console import Console
from rich.progress import Progress
from Levenshtein import distance as levenshtein_distance  # Import Levenshtein library
import subprocess

console = Console()

def error(message, exit_code=1):
    console.print(f"[bold red]Error:[/bold red] {message}")
    sys.exit(exit_code)

def find_mp4_files(directory):
    """Search for MP4 files in the specified directory."""
    mp4_files = []
    seasons = os.listdir(directory)
    
    with Progress(transient=True) as progress:
        task = progress.add_task("[cyan]Searching for MP4 files...", total=len(seasons))
        
        for season in seasons:
            season_path = os.path.join(directory, season)
            if not os.path.isdir(season_path):
                console.print(f"[bold yellow]Warning:[/bold yellow] {season_path} is not a directory.")
                continue
            
            for file_name in os.listdir(season_path):
                full_path = os.path.join(season_path, file_name)
                if os.path.isfile(full_path) and file_name.lower().endswith('.mp4'):
                    mp4_files.append(full_path)

            # Update progress
            progress.update(task, advance=1)

    if not mp4_files:
        error("No MP4 files found.", 3)
    
    return mp4_files

def find_series_directory(serie_name: str, maindir: str) -> str:
    """Find the directory for the specified series."""
    exact_matches = []
    substring_matches = []
    potential_matches = []

    with Progress(transient=True) as progress:
        task = progress.add_task("[cyan]Searching directories...", total=len(os.listdir(maindir)))

        for dir_name in os.listdir(maindir):
            full_path = os.path.join(maindir, dir_name)
            if os.path.isdir(full_path):
                if dir_name.lower() == serie_name.lower():
                    exact_matches.append(full_path)
                elif serie_name.lower() in dir_name.lower():
                    substring_matches.append(full_path)
                else:
                    potential_matches.append(dir_name)

            progress.update(task, advance=1)

    # Processing results for matches
    if len(exact_matches) == 1:
        return exact_matches[0]
    elif len(exact_matches) > 1:
        error(f"Multiple exact matches found: {exact_matches}", 5)
    elif len(substring_matches) == 1:
        return substring_matches[0]
    elif len(substring_matches) > 1:
        error(f"Multiple substring matches found: {substring_matches}", 6)

    # Suggest closest match using Levenshtein distance
    if potential_matches:
        closest_match = min(potential_matches, key=lambda x: levenshtein_distance(x.lower(), serie_name.lower()))
        error(f"No suitable series directory found. Closest match: {closest_match}", 3)

    error("No suitable series directory found.", 3)

def load_db_file(db_file_path):
    """Lädt die .db.txt-Datei und gibt eine Map mit Pfaden und Unix-Zeiten zurück."""
    if not os.path.isfile(db_file_path):
        return {}

    db_entries = {}
    with open(db_file_path, 'r') as db_file:
        for line in db_file:
            path, unix_time = line.strip().split(':::')
            db_entries[path] = int(unix_time)

    return db_entries

def update_db_file(db_file_path, mp4_file, unix_time):
    """Aktualisiert die .db.txt-Datei mit dem neuen Eintrag."""
    with open(db_file_path, 'a') as db_file:
        db_file.write(f"{mp4_file}:::{unix_time}\n")

def select_mp4_file(mp4_files, db_entries):
    """Wählt eine MP4-Datei basierend auf den Unix-Zeiten aus."""
    candidates = []
    for mp4_file in mp4_files:
        if mp4_file not in db_entries:  # Kein Eintrag vorhanden
            return mp4_file  # Sofort zurückgeben

        candidates.append((mp4_file, db_entries[mp4_file]))

    # Sortiere nach der Unix-Zeit (älteste zuerst) und wähle zufällig
    candidates.sort(key=lambda x: x[1])  # Älteste zuerst
    weights = [1 / (time.time() - entry[1]) for entry in candidates]  # Gewichtung basierend auf der Zeit
    total_weight = sum(weights)

    # Auswahl einer Datei basierend auf Gewichtung
    selection = random.choices(candidates, weights=weights, k=1)
    return selection[0][0]

def play_video(video_path):
    # Starte den VLC-Player mit dem Video und der Option, VLC zu schließen, wenn das Video zu Ende ist
    process = subprocess.Popen(['vlc', '--play-and-exit', '--fullscreen', video_path])
    
    # Warte, bis der VLC-Prozess beendet ist
    process.wait()

def main():
    parser = argparse.ArgumentParser(description='Process some options.')
    parser.add_argument('--debug', action='store_true', default=False, help='Enable debug mode.')
    parser.add_argument('--maindir', type=str, required=True, help='Set main directory.')
    parser.add_argument('--serie', type=str, required=True, help='Set series name.')

    args = parser.parse_args()

    # Check if the main directory exists
    if not os.path.isdir(args.maindir):
        error(f"--maindir {args.maindir} not found")

    # Find the series name
    serie_name = find_series_directory(args.serie, args.maindir)

    # Find mp4 files
    mp4_files = find_mp4_files(os.path.join(args.maindir, serie_name))

    # Handle cases based on found mp4 files
    if len(mp4_files) == 0:
        error("No .mp4 files found.", 3)

    # Load existing entries from .db.txt
    db_file_path = os.path.join(args.maindir, '.db.txt')
    db_entries = load_db_file(db_file_path)

    # Select an MP4 file to play
    selected_file = select_mp4_file(mp4_files, db_entries)

    # Update the .db.txt file with the current Unix time if needed
    if selected_file not in db_entries:
        current_time = int(time.time())
        update_db_file(db_file_path, selected_file, current_time)
        console.print(f"[bold green]Added new entry for:[/bold green] {selected_file} with time {current_time}")

    # Start VLC with the selected file
    console.print(f"[bold blue]Starting VLC for:[/bold blue] {selected_file}")

    play_video(selected_file)

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        console.print("[bold yellow]Process interrupted gracefully.[/bold yellow]")
        sys.exit(0)
