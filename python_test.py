#!/usr/bin/python3

import os
import sys
import argparse
from textual.app import App, ComposeResult
from textual.widgets import Input, ListView, ListItem, Button, Static
from textual.reactive import Reactive
from rich.console import Console
from rich.progress import Progress

console = Console()

def error(message, exit_code=1):
    console.print(f"[bold red]Error:[/bold red] {message}")
    sys.exit(exit_code)

class MainApp(App):
    series_name: Reactive[str] = Reactive("")
    filtered_series: Reactive[list] = Reactive([])

    def compose(self) -> ComposeResult:
        yield Static("Series Name:")
        yield Input(placeholder="Enter Series Name", name="series_input", on_change=self.on_series_input_change)
        yield Static("Available Series:")
        
        # Create the ListView without items initially
        self.series_list_view = ListView(name="series_list")
        yield self.series_list_view  # Yield the ListView

        yield Button("Submit", id="submit_button")

    async def on_mount(self) -> None:
        # Populate series names once the app is mounted
        self.series_names = self.get_available_series()
        await self.populate_series_list(self.series_names)

    async def populate_series_list(self, series_names):
        # Clear the current list
        self.series_list_view.clear()

        # Add filtered series names to the ListView
        for series in series_names:
            list_item = ListItem(Static(series))  # Create a ListItem for each series with Static widget
            self.series_list_view.append(list_item)  # Add it to the ListView
        
        # Automatically submit if only one series is left
        if len(series_names) == 1:
            self.series_name = series_names[0]
            await self.on_submit()

    async def on_series_input_change(self, event):
        input_widget = self.query_one(Input)
        search_value = input_widget.value.strip().lower()

        # Filter the series names based on input
        filtered = [name for name in self.series_names if search_value in name.lower()]
        await self.populate_series_list(filtered)

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "submit_button":
            input_widget = self.query_one(Input)
            self.series_name = input_widget.value.strip()
            await self.on_submit()

    async def on_list_item_pressed(self, event) -> None:
        self.series_name = event.item.child.text.strip()
        await self.on_submit()

    async def on_submit(self):
        # Stop the application and return the selected series name
        self.exit()  # No await needed

    def get_available_series(self):
        # Assuming args.maindir is available in the scope
        if not os.path.isdir(self.maindir):
            error(f"--maindir {self.maindir} not found")

        series_names = [item for item in os.listdir(self.maindir) if os.path.isdir(os.path.join(self.maindir, item))]
        return series_names

def ask_for_series_name(series_names, maindir):
    app = MainApp()
    app.maindir = maindir
    app.series_names = series_names
    app.run()
    return app.series_name  # Return the input

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

    # List available series in the main directory
    series_names = []
    for item in os.listdir(args.maindir):
        if os.path.isdir(os.path.join(args.maindir, item)):
            series_names.append(item)

    # Ask for series name if not provided
    series_name = args.serie if args.serie else ask_for_series_name(series_names, args.maindir)

    # Create the options dictionary with defaults from argparse
    options = vars(args)
    options['serie'] = series_name

    # Set the dbfile path based on maindir
    options['dbfile'] = os.path.join(options['maindir'], ".db.txt")

    # Search for directories that only contain numbers and list mp4 files
    with Progress() as progress:
        task = progress.add_task("[cyan]Searching for directories...[/cyan]", total=None)

        # Only search within the selected series directory
        series_dir = os.path.join(options['maindir'], options['serie'])
        for root, dirs, files in os.walk(series_dir):
            # Check if the directory name is numeric (2nd level only)
            if os.path.basename(root).isdigit():
                # Check parent directory for numeric directories
                parent_dir = os.path.dirname(root)
                if os.path.basename(parent_dir).isalpha():  # Ensure the parent is not numeric
                    mp4_files = [f for f in files if f.endswith('.mp4')]
                    if mp4_files:
                        progress.update(task, advance=1)
                        console.print(f"\nFound directory: [bold green]{root}[/bold green]")
                        for mp4 in mp4_files:
                            console.print(f" - [bold blue]{mp4}[/bold blue]")

        progress.stop()

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("Cancelled by pressing CTRL-c.")
