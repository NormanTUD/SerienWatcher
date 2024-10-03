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

db_entries = None

console = Console()

parser = argparse.ArgumentParser(description='Process some options.')
parser.add_argument('--debug', action='store_true', default=False, help='Enable debug mode.')
parser.add_argument('--maindir', type=str, required=True, help='Set main directory.')
parser.add_argument('--serie', type=str, required=True, help='Set series name.')
parser.add_argument('--staffel', type=int, default=-1, help='Season.')
parser.add_argument('--min_staffel', type=int, default=-1, help='Season.')
parser.add_argument('--max_staffel', type=int, default=-1, help='Season.')

args = parser.parse_args()

def error(message, exit_code=1):
    console.print(f"[bold red]Error:[/bold red] {message}")
    sys.exit(exit_code)

def debug(message):
    if args.debug:
        console.print(f"[bold yellow]Debug:[/bold yellow] {message}")

def find_mp4_files(directory):
    """Search for MP4 files in the specified directory."""
    mp4_files = []
    seasons = os.listdir(directory)
    
    with Progress(transient=True) as progress:
        task = progress.add_task("[cyan]Searching for MP4 files...", total=len(seasons))
        
        for season in seasons:
            debug(f"find_mp4_files: .staffel: {args.staffel}, season = {season}")
            no_staffel_or_staffel_matches = (args.staffel == -1 or args.staffel == int(season))
            no_max_staffel_or_staffel_matches = (args.max_staffel != -1 or args.max_staffel <= int(season))
            no_min_staffel_or_staffel_matches = (args.min_staffel != -1 or args.min_staffel >= int(season))
                                                 
            if no_staffel_or_staffel_matches or (no_max_staffel_or_staffel_matches and no_min_staffel_or_staffel_matches)):
                season_path = os.path.join(directory, season)
                print(f"!!! season_path: {season_path}")
                sys.exit(0)
                if not os.path.isdir(season_path):
                    console.print(f"[bold yellow]Warning:[/bold yellow] {season_path} is not a directory.")
                    continue
                
                for file_name in os.listdir(season_path):
                    full_path = os.path.join(season_path, file_name)
                    if os.path.isfile(full_path) and file_name.lower().endswith('.mp4'):
                        mp4_files.append(full_path)
                    else:
                        debug(f"{full_path} not found")

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
    """Loads the .db.txt file and returns a map with paths and Unix times."""
    if not os.path.isfile(db_file_path):
        return {}

    _db_entries = {}
    with open(db_file_path, 'r') as db_file:
        for line in db_file:
            path, unix_time = line.strip().split(':::')
            # Normalize the path by removing slashes variations
            normalized_path = path.replace('/', '').replace('\\', '')  # Remove slashes
            if normalized_path in _db_entries:
                # Keep the entry with the latest timestamp
                if _db_entries[normalized_path] < int(unix_time):
                    _db_entries[normalized_path] = int(unix_time)
            else:
                _db_entries[normalized_path] = int(unix_time)

    return _db_entries

def update_db_file(db_file_path, mp4_file, unix_time):
    """Updates the .db.txt file with the new entry."""
    with open(db_file_path, 'a') as db_file:
        db_file.write(f"{mp4_file}:::{unix_time}\n")

def select_mp4_file(mp4_files, db_file_path, last_played=None):
    global db_entries
    
    """Selects an MP4 file based on Unix times, ensuring the last played is not repeated."""
    candidates = []

    # Normalisiere den letzten Dateinamen, um Fehler zu vermeiden
    normalized_last_played = last_played.replace('/', '').replace('\\', '') if last_played else None

    # Durchlaufe alle MP4-Dateien und baue die Kandidatenliste
    for mp4_file in mp4_files:
        normalized_path = mp4_file #.replace('/', '').replace('\\', '')  # Normalize the path

        # Überprüfe, ob es keinen Eintrag gibt
        if normalized_path not in db_entries and normalized_last_played and normalized_last_played == normalized_path:
            debug(f"No entry found for: {mp4_file}. Directly using it.")  # Debugging-Ausgabe
            current_time = int(time.time())
            update_db_file(db_file_path, mp4_file, current_time)
            
            db_entries = load_db_file(db_file_path)
            return mp4_file

        # Überprüfe, ob die Datei die zuletzt abgespielte ist
        if normalized_last_played and normalized_last_played == normalized_path:
            debug(f"Skipping last played file: {mp4_file}")  # Debugging-Ausgabe
            continue

        if os.path.exists(mp4_file):
            candidates.append((mp4_file, 0))
        else:
            debug(f"Cannot add {mp4_file}")

    if not candidates:
        error("No new MP4 files available to play.", 3)

    # Berechne die Gewichte basierend auf der Zeit seit dem letzten Abspielen
    current_time = time.time()
    weights = [current_time - entry[1] for entry in candidates]  # Zeit seit dem letzten Abspielen

    # Debugging-Ausgabe für die Kandidaten und ihre Gewichte
    debug("Candidates and their weights:")
    for candidate, weight in zip(candidates, weights):
        debug(f"Candidate: {candidate[0]}, Weight: {weight}")

    # Wähle eine Datei basierend auf den Gewichten aus
    selection = random.choices(candidates, weights=weights, k=1)
    selected_file = selection[0][0]
    debug(f"Selected file: {selected_file}")  # Debugging-Ausgabe
    return selected_file


def play_video(video_path):
    # Start VLC player with the video and option to close VLC when the video ends
    # Trying to start VLC with a non-existing file to check if it will exit on its own.
    process = subprocess.Popen(['vlc', '--play-and-exit', video_path, '/dev/doesnt_exist'], stderr=subprocess.PIPE, stdout=subprocess.PIPE)

    # Wait until the VLC process ends and capture stdout and stderr
    stdout, stderr = process.communicate()

    return stdout.decode(), stderr.decode()

def main():
    global db_entries
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

    last_played_file = None  # Track the last played file

    # Loop to continuously select and play video files
    while True:
        # Select an MP4 file to play
        selected_file = select_mp4_file(mp4_files, db_file_path, last_played_file)

        # Update the .db.txt file with the current Unix time if needed
        normalized_path = selected_file.replace('//*', '/') # Normalize the path
        if normalized_path not in db_entries:
            current_time = int(time.time())
            update_db_file(db_file_path, selected_file, current_time)
            console.print(f"[bold green]Added new entry for:[/bold green] {selected_file} with time {current_time}")

        # Start VLC with the selected file
        console.print(f"[bold blue]vlc[/bold blue] '[italic green]{selected_file}[/italic green]'")

        # Play video and check output
        stdout, stderr = play_video(selected_file)

        # Check if VLC exited correctly
        if "/dev/doesnt_exist" in stderr:
            last_played_file = selected_file  # Update the last played file
        else:
            console.print("[bold yellow]VLC was manually closed.[/bold yellow]")
            break  # Exit if VLC was closed manually

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        console.print("[bold yellow]Process interrupted gracefully.[/bold yellow]")
        sys.exit(0)

