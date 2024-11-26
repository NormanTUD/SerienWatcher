#!/usr/bin/python3

import os
import sys
import vlc
import argparse
import random
import time
from pprint import pprint
from rich.console import Console
from rich.progress import Progress
from Levenshtein import distance as levenshtein_distance  # Import Levenshtein library
import subprocess
import unittest
from unittest.mock import patch, mock_open, MagicMock

def dier (msg):
    pprint(msg)
    sys.exit(10)

db_entries = None

console = Console()

parser = argparse.ArgumentParser(description='Process some options.')
parser.add_argument('--debug', action='store_true', default=False, help='Enable debug mode.')
parser.add_argument('--maindir', type=str, default="", help='Set main directory.')
parser.add_argument('--serie', type=str, default="", help='Set series name.')
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
            if not season.isnumeric():
                continue

            season_number = int(season)

            # Überprüfe, ob die Staffelnummer gültig ist
            if args.staffel != -1 and args.staffel != season_number:
                continue  # Staffel stimmt nicht überein, weiter zur nächsten
            
            if args.min_staffel != -1 and season_number < args.min_staffel:
                continue  # Staffel liegt unter der minimalen Staffel

            if args.max_staffel != -1 and season_number > args.max_staffel:
                continue  # Staffel liegt über der maximalen Staffel

            season_path = os.path.join(directory, season)
            if not os.path.isdir(season_path):
                console.print(f"[bold yellow]Warning:[/bold yellow] {season_path} is not a directory.")
            else:
                for file_name in os.listdir(season_path):
                    full_path = os.path.join(season_path, file_name)
                    if os.path.isfile(full_path) and file_name.lower().endswith('.mp4'):
                        mp4_files.append(full_path)
                    else:
                        debug(f"{full_path} not found")

            # Update progress
            progress.update(task, advance=1)

    # Stelle sicher, dass immer eine Liste zurückgegeben wird
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

def clean_db_file(db_file_path):
    """Cleans the .db.txt file, keeping only the newest entry for each mp4_file."""
    # Überprüfen, ob der Dateipfad gültig ist
    debug(f"Starting to clean {db_file_path}")
    if not db_file_path or not isinstance(db_file_path, str):
        raise ValueError(f"Invalid file path: {db_file_path}")

    # Datei erstellen, falls sie nicht existiert
    if not os.path.exists(db_file_path):
        try:
            debug(f"File {db_file_path} does not exist. Creating it.")
            open(db_file_path, 'w').close()
        except Exception as e:
            print(f"[ERROR] Unable to create {db_file_path}: {e}")
            sys.exit(1)
        return

    # Überprüfen, ob die Datei lesbar ist
    if not os.access(db_file_path, os.R_OK):
        print(f"[ERROR] File {db_file_path} is not readable.")
        sys.exit(2)

    # Dateiinhalt einlesen
    try:
        debug(f"Opening {db_file_path} for reading.")
        with open(db_file_path, 'r') as db_file:
            lines = db_file.readlines()
            debug(f"Read {len(lines)} lines from {db_file_path}.")
    except FileNotFoundError:
        print(f"[WARNING] File {db_file_path} not found. Nothing to clean.")
        return
    except Exception as e:
        print(f"[ERROR] Unexpected error while reading {db_file_path}: {e}")
        sys.exit(3)

    # Map zur Speicherung des neuesten Eintrags für jede mp4_file
    latest_entries = {}
    for idx, line in enumerate(lines):
        debug(f"Processing line {idx}: {line.strip()}")
        if ":::" in line:
            try:
                mp4_file, unix_time = line.strip().split(":::")
                unix_time = int(unix_time)
                if mp4_file not in latest_entries or unix_time > latest_entries[mp4_file]:
                    debug(f"Updating latest entry for {mp4_file} to {unix_time}.")
                    latest_entries[mp4_file] = unix_time
            except ValueError as e:
                print(f"[WARNING] Malformed line {idx}: {line.strip()}. Error: {e}")
        else:
            print(f"[WARNING] Ignoring malformed line {idx}: {line.strip()}")

    old_umask = os.umask(0)
    # Bereinigte Datei schreiben
    try:
        debug(f"Checking write permissions for {db_file_path}.")
        if not os.access(db_file_path, os.W_OK):
            raise PermissionError(f"File {db_file_path} is not writable.")

        debug(f"Opening {db_file_path} for writing.")
        with open(db_file_path, 'w') as db_file:
            for entry, unix_time in latest_entries.items():
                entry = entry.replace('"', '')
                new_line = f'"{entry}":::{unix_time}\n'
                debug(f"Writing line: {new_line.strip()}")
                db_file.write(new_line)
    except PermissionError as e:
        print(f"[ERROR] Permission error while writing {db_file_path}: {e}")
        sys.exit(5)
    except Exception as e:
        print(f"[ERROR] Unexpected error while writing {db_file_path}: {e}")
        sys.exit(6)
    finally:
        os.umask(old_umask)

    debug(f"Successfully cleaned and updated {db_file_path}.")

def update_db_file(db_file_path, mp4_file, unix_time):
    clean_db_file(db_file_path)

    """Updates the .db.txt file with the new entry."""
    with open(db_file_path, 'a') as db_file:
        db_file.write(f"{mp4_file}:::{unix_time}\n")

def select_mp4_file(mp4_files, db_file_path, last_played=None):
    global db_entries
    
    """Selects an MP4 file based on Unix times, ensuring the last played is not repeated."""
    candidates = []

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

def get_skip_value(filename, filepath):
    try:
        with open(filepath, 'r') as file:
            for line in file:
                parts = line.strip().split(' ::: ')
                if len(parts) == 2:
                    file_name, skip_value = parts
                    # Überprüfe, ob der Dateiname übereinstimmt
                    if file_name == filename:
                        return int(skip_value)  # Den Wert zurückgeben
        return None  # Wenn kein Wert gefunden wurde
    except FileNotFoundError:
        debug(f"The file {filepath} was not found.")
        return None

def play_video(video_path):
    # Start VLC player with the video and option to close VLC when the video ends
    # Trying to start VLC with a non-existing file to check if it will exit on its own.
    start_time = "";
    file_name = os.path.basename(video_path)
    folder_path = os.path.dirname(video_path)

    intro_skipper_file = os.path.join(folder_path, ".intro_endtime")

    start_time = get_skip_value(file_name, intro_skipper_file)

    if start_time:
        process = subprocess.Popen(['vlc', '--no-random', '--play-and-exit', f"--start-time={start_time}", video_path, '/dev/doesnt_exist', "vlc://quit"], stderr=subprocess.PIPE, stdout=subprocess.PIPE)
    else:
        process = subprocess.Popen(['vlc', '--no-random', '--play-and-exit', video_path, '/dev/doesnt_exist', "vlc://quit"], stderr=subprocess.PIPE, stdout=subprocess.PIPE)

    # Wait until the VLC process ends and capture stdout and stderr
    stdout, stderr = process.communicate()

    return stdout.decode(), stderr.decode()

def main():
    if os.getenv("tests"):
        unittest.main()
        sys.exit(0)
    
    if args.maindir == "":
        console.print("[red]--maindir needs to be set[/red]")
        sys.exit(1)
    
    if args.serie == "":
        console.print("[red]--serie needs to be set[/red]")
        sys.exit(1)

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
    db_file_path = os.path.join(os.getenv("HOME"), '.db.txt')
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
            debug(f"[bold green]Added new entry for:[/bold green] {selected_file} with time {current_time}")

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


class TestMainFunctions(unittest.TestCase):
    @patch('os.listdir')
    @patch('os.path.isdir')
    def test_find_mp4_files(self, mock_isdir, mock_listdir):
        mock_listdir.return_value = ['1', '2', 'invalid']
        mock_isdir.return_value = True
        mock_isfile = MagicMock(return_value=True)
        
        with patch('os.path.isfile', mock_isfile):
            result = find_mp4_files('/dummy_dir')
            self.assertEqual(len(result), 0)  # No .mp4 files, but directories are checked

    @patch('os.listdir')
    @patch('os.path.isdir')
    def test_find_series_directory(self, mock_isdir, mock_listdir):
        mock_listdir.return_value = ['SeriesA', 'SeriesB', 'AnotherSeries']
        mock_isdir.return_value = True
        
        result = find_series_directory('SeriesA', '/dummy_maindir')
        self.assertEqual(result, '/dummy_maindir/SeriesA')

    @patch('os.listdir')
    @patch('os.path.isdir')
    def test_find_mp4_files_non_mp4_files(self, mock_isdir, mock_listdir):
        mock_listdir.return_value = ['file1.txt', 'file2.jpg']
        mock_isdir.return_value = True
        mock_isfile = MagicMock(return_value=False)
        
        with patch('os.path.isfile', mock_isfile):
            result = find_mp4_files('/dummy_dir')
            self.assertEqual(len(result), 0)

    @patch('os.listdir')
    @patch('os.path.isdir')
    def test_find_series_directory_case_insensitive(self, mock_isdir, mock_listdir):
        mock_listdir.return_value = ['seriesA', 'SeriesB']
        mock_isdir.return_value = True
        
        result = find_series_directory('SeriesA', '/dummy_maindir')
        self.assertEqual(result, '/dummy_maindir/seriesA')

    @patch('os.listdir')
    @patch('os.path.isdir')
    def test_find_series_directory_multiple_matches(self, mock_isdir, mock_listdir):
        mock_listdir.return_value = ['SeriesA', 'SeriesA-extended']
        mock_isdir.return_value = True
        
        result = find_series_directory('SeriesA', '/dummy_maindir')
        self.assertEqual(result, '/dummy_maindir/SeriesA')

    @patch('builtins.open', new_callable=mock_open)
    def test_update_db_file_no_permission(self, mock_open):
        mock_open.side_effect = PermissionError
        
        with self.assertRaises(PermissionError):
            update_db_file('/dummy_db_path/.db.txt', 'file1.mp4', 123456789)

    @patch('os.listdir')
    @patch('os.path.isdir')
    def test_find_series_directory_with_spaces(self, mock_isdir, mock_listdir):
        mock_listdir.return_value = ['Series A', 'Series B']
        mock_isdir.return_value = True
        
        result = find_series_directory('Series A', '/dummy_maindir')
        self.assertEqual(result, '/dummy_maindir/Series A')

    @patch('os.listdir')
    @patch('os.path.isdir')
    def test_find_series_directory_special_characters(self, mock_isdir, mock_listdir):
        mock_listdir.return_value = ['Series_A$', 'Series@B']
        mock_isdir.return_value = True
        
        result = find_series_directory('Series_A$', '/dummy_maindir')
        self.assertEqual(result, '/dummy_maindir/Series_A$')

    @patch('os.listdir')
    @patch('os.path.isdir')
    def test_find_series_directory_ignore_case(self, mock_isdir, mock_listdir):
        mock_listdir.return_value = ['seriesa', 'seriesb']
        mock_isdir.return_value = True
        
        result = find_series_directory('SERIESA', '/dummy_maindir')
        self.assertEqual(result, '/dummy_maindir/seriesa')

    @patch('os.listdir')
    @patch('os.path.isdir')
    def test_find_series_directory_no_match(self, mock_isdir, mock_listdir):
        mock_listdir.return_value = ['AnotherSeries', 'DifferentSeries']
        mock_isdir.return_value = True
        
        with self.assertRaises(SystemExit):
            find_series_directory('SeriesX', '/dummy_maindir')

    @patch('os.listdir')
    @patch('os.path.isdir')
    def test_find_series_directory_empty_directory(self, mock_isdir, mock_listdir):
        mock_listdir.return_value = []
        mock_isdir.return_value = True
        
        with self.assertRaises(SystemExit):
            find_series_directory('SeriesA', '/dummy_maindir')

    @patch('builtins.open', new_callable=mock_open)
    def test_update_db_file_with_new_entry(self, mock_open):
        mock_file = mock_open.return_value.__enter__.return_value
        mock_file.read.return_value = ''
        
        update_db_file('/dummy_db_path/.db.txt', 'file2.mp4', 987654321)
        mock_file.write.assert_called_with('file2.mp4:::987654321\n')

    @patch('os.listdir')
    @patch('os.path.isdir')
    def test_find_series_directory_ignore_leading_whitespace(self, mock_isdir, mock_listdir):
        mock_listdir.return_value = [' SeriesA', 'SeriesB']
        mock_isdir.return_value = True
        
        result = find_series_directory('SeriesA', '/dummy_maindir')
        self.assertEqual(result, '/dummy_maindir/ SeriesA')

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        console.print("[bold yellow]Process interrupted gracefully.[/bold yellow]")
        sys.exit(0)
