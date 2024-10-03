import os
import sys
import re
import imagehash
import argparse
import pandas as pd
from PIL import Image
from rich.console import Console
from rich.progress import Progress
import subprocess

console = Console()

# Global process variable
process_tasks = []

def die(message):
    """Print an error message and exit."""
    console.print(f"[bold red]Error:[/bold red] {message}")
    sys.exit(1)

def debug_print(debug, message):
    """Print debug messages if debug mode is enabled."""
    if debug:
        console.print(f"[bold yellow]Debug:[/bold yellow] {message}")

def run_command(command):
    """Run a shell command and track subprocess tasks."""
    debug_print(args.debug, f"Running command: {command}")
    process = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    process_tasks.append(process)
    return process

def extract_frames(video_path, output_dir):
    """Extract frames from the video using ffmpeg."""
    command = f"ffmpeg -i \"{video_path}\" -r 2 -to 00:02:00 \"{output_dir}/output_%04d.png\""
    process = run_command(command)
    stdout, stderr = process.communicate()

    if process.returncode != 0:
        console.print(f"[bold red]FFmpeg error:[/bold red] {stderr.decode()}")
        die("Failed to extract frames.")
    debug_print(args.debug, f"Extracted frames to {output_dir}")

def analyze_images(tmpdir):
    """Analyze images and return the last frame for each unique hash."""
    hash_to_image = {}
    last_file_to_frame = {}
    info_file_path = os.path.join(tmpdir, ".intro_cutter_info.csv")

    # Check if the info file exists and load it
    if os.path.exists(info_file_path):
        debug_print(args.debug, f"Loading existing data from {info_file_path}")
        existing_info = pd.read_csv(info_file_path)
        for _, row in existing_info.iterrows():
            last_file_to_frame[row['filename']] = row['last_frame']

    for directory in os.listdir(tmpdir):
        dir_path = os.path.join(tmpdir, directory)
        if not os.path.isdir(dir_path):
            continue

        for filename in os.listdir(dir_path):
            if filename.endswith(".png"):
                filepath = os.path.join(dir_path, filename)
                this_hash = imagehash.average_hash(Image.open(filepath))

                if str(this_hash) not in hash_to_image:
                    hash_to_image[str(this_hash)] = []

                if str(this_hash) != "0000000000000000":
                    hash_to_image[str(this_hash)].append(filepath)
                    debug_print(args.debug, f"Hash {this_hash} for file {filepath}")
    import pprint
    pprint.pprint(hash_to_image)

    console.print(f"\n[cyan]Analyzing {len(hash_to_image)} unique hashes...[/cyan]")

    # Store hashes and frames if the option is enabled
    if args.save_hashes:
        hashes_list = []

    for k in sorted(hash_to_image, key=lambda k: len(hash_to_image[k]), reverse=True):
        for item in hash_to_image[k]:
            match = re.match(rf"{tmpdir}/(.*)/output_(\d*).png", item)
            if match:
                thisfile = match.group(1)
                thisframe = int(match.group(2))

                if thisfile not in last_file_to_frame or last_file_to_frame[thisfile] < thisframe:
                    last_file_to_frame[thisfile] = thisframe
                    debug_print(args.debug, f"Found last frame for {thisfile}: {thisframe}")
                    
                    # Save to hashes list if option is enabled
                    if args.save_hashes:
                        hashes_list.append({"hash": k, "filename": thisfile, "last_frame": thisframe})

    console.print(f"[green]Found last frames for {len(last_file_to_frame)} files.[/green]")

    # Save results to .intro_cutter_info.csv
    if args.save_hashes:
        hash_info_file_path = os.path.join(tmpdir, "hashes_info.csv")
        debug_print(args.debug, f"Saving hash analysis results to {hash_info_file_path}")
        hashes_df = pd.DataFrame(hashes_list)
        hashes_df.to_csv(hash_info_file_path, index=False)

    return last_file_to_frame

def main(args):
    if not os.path.isdir(args.dir):
        die(f"Directory '{args.dir}' does not exist")

    tmpdir = os.path.join(args.tmp, "frames")
    os.makedirs(tmpdir, exist_ok=True)
    debug_print(args.debug, f"Temporary directory created at {tmpdir}")

    # Process each video file
    video_files = [f for f in os.listdir(args.dir) if f.endswith(".mp4")]
    debug_print(args.debug, f"Found {len(video_files)} video files to process.")

    with Progress(transient=True) as progress:
        task = progress.add_task("[cyan]Processing videos...", total=len(video_files))
        for video_file in video_files:
            video_path = os.path.join(args.dir, video_file)
            md5_hash = os.path.basename(video_path)  # Placeholder for actual MD5 hash

            output_dir = os.path.join(tmpdir, md5_hash)
            os.makedirs(output_dir, exist_ok=True)
            debug_print(args.debug, f"Output directory created for {video_file}: {output_dir}")

            if not os.path.exists(f"{args.dir}/.intro_endtime"):
                extract_frames(video_path, output_dir)
            else:
                console.print(f"\n[red]{args.dir}/.intro_endtime already exists.[/red]")
                sys.exit(0)

            progress.update(task, advance=1)

        # Analyze images
        last_frames = analyze_images(tmpdir)

        with open(f"{args.dir}/.intro_endtime", 'a') as fh:
            for filename, frame in last_frames.items():
                t = frame // 2  # Adjust frame to time (assuming 2 fps)
                file = os.path.basename(filename)
                fh.write(f"{file} ::: {t}\n")
                console.print(f"[green]{file} ::: {t}[/green]")

    # Wait for all subprocesses to complete
    for process in process_tasks:
        process.wait()

if __name__ == "__main__":
    try:
        parser = argparse.ArgumentParser(description="Video frame extractor and image analyzer.")
        parser.add_argument("--dir", type=str, required=True, help="Directory containing video files.")
        parser.add_argument("--tmp", type=str, default="./tmp", help="Temporary directory for extracted frames.")
        parser.add_argument("--debug", action='store_true', help="Enable debug output.")
        parser.add_argument("--save_hashes", action='store_true', help="Save hashes and frames to CSV.")

        args = parser.parse_args()
    
        main(args)
    except KeyboardInterrupt:
        console.print("[bold yellow]You cancelled the operation.[/bold yellow]")
        sys.exit(0)
