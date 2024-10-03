#!/usr/bin/python3

import os
import sys
import argparse
from textual.app import App, ComposeResult
from textual.widgets import Input, ListView, ListItem, Button, Static
from textual.reactive import Reactive
from rich.console import Console

console = Console()

def error(message, exit_code=1):
    console.print(f"[bold red]Error:[/bold red] {message}")
    sys.exit(exit_code)

class MainApp(App):
    series_name: Reactive[str] = Reactive("")
    filtered_series: Reactive[list] = Reactive([])

    def compose(self) -> ComposeResult:
        yield Static("Enter Series Name:")
        self.input_widget = Input(placeholder="Enter Series Name", name="series_input")
        yield self.input_widget
        yield Button("Exit", id="exit_button")  # Button to exit the application

        # Create a ListView for displaying filtered series
        self.series_list_view = ListView(name="series_list")
        yield self.series_list_view

        self.bind("change", self.on_series_input_change)  # Bind change event to input widget

    async def on_mount(self) -> None:
        self.series_names = self.get_available_series()  # Load series names when the app is mounted

    async def on_series_input_change(self, event):
        search_value = self.input_widget.value.strip().lower()

        # Filter the series names based on input
        filtered = [name for name in self.series_names if search_value in name.lower()]
        await self.populate_series_list(filtered)

    async def populate_series_list(self, series_names):
        # Clear the current list
        self.series_list_view.clear()

        # Add filtered series names to the ListView
        for series in series_names:
            list_item = ListItem(Static(series))
            self.series_list_view.append(list_item)

        # If there's only one series left, select it automatically
        if len(series_names) == 1:
            self.series_name = series_names[0]
            await self.on_submit()

    async def on_list_item_selected(self, event) -> None:
        selected_item = event.item.child.text.strip()
        self.series_name = selected_item
        await self.on_submit()

    async def on_submit(self):
        self.exit()  # Exit the app and return the selected series name

    def get_available_series(self):
        if not os.path.isdir(self.maindir):
            error(f"--maindir {self.maindir} not found")

        return [item for item in os.listdir(self.maindir) if os.path.isdir(os.path.join(self.maindir, item))]

def ask_for_series_name(series_names, maindir):
    app = MainApp()
    app.maindir = maindir
    app.series_names = series_names
    app.run()
    return app.series_name

def main():
    parser = argparse.ArgumentParser(description='Process some options.')
    parser.add_argument('--maindir', type=str, required=True, help='Set main directory.')

    args = parser.parse_args()

    if not os.path.isdir(args.maindir):
        error(f"--maindir {args.maindir} not found")

    series_names = os.listdir(args.maindir)  # Get all series names

    series_name = ask_for_series_name(series_names, args.maindir)

    console.print(f"Selected Series: [bold green]{series_name}[/bold green]")

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("Cancelled by pressing CTRL-c.")
