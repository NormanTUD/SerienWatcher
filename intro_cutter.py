import os
import sys
import re
import imagehash
import argparse
from PIL import Image
from rich.console import Console
from rich.progress import Progress
from rich.text import Text
import subprocess

console = Console()

# Global process variable
process_tasks = []

def die(message):
    console.print(f"[bold red]Error:[/bold red] {message}")
    sys.exit(1)

def run_command(command):
    """Run a shell command and track subprocess tasks."""
    #console.print(f"[yellow]Running command:[/yellow] {command}")
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

def analyze_images(tmpdir):
    """Analyze images and return the last frame for each unique hash."""
    hash_to_image = {}
    last_file_to_frame = {}

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

    console.print(f"[cyan]Analyzing {len(hash_to_image)} unique hashes...[/cyan]")

    for k in sorted(hash_to_image, key=lambda k: len(hash_to_image[k]), reverse=True):
        for item in hash_to_image[k]:
            match = re.match(rf"{tmpdir}/(.*)/output_(\d*).png", item)
            if match:
                thisfile = match.group(1)
                thisframe = int(match.group(2))

                if thisfile not in last_file_to_frame or last_file_to_frame[thisfile] < thisframe:
                    last_file_to_frame[thisfile] = thisframe

    console.print(f"[green]Found last frames for {len(last_file_to_frame)} files.[/green]")
    return last_file_to_frame

def main(args):
    if not os.path.isdir(args.dir):
        die(f"Directory '{args.dir}' does not exist")

    tmpdir = os.path.join(args.tmp, "frames")
    os.makedirs(tmpdir, exist_ok=True)

    # Process each video file
    video_files = [f for f in os.listdir(args.dir) if f.endswith(".mp4")]
    with Progress(transient=True) as progress:
        task = progress.add_task("[cyan]Processing videos...", total=len(video_files))
        for video_file in video_files:
            video_path = os.path.join(args.dir, video_file)
            md5_hash = os.path.basename(video_path)  # Placeholder for actual MD5 hash

            output_dir = os.path.join(tmpdir, md5_hash)
            os.makedirs(output_dir, exist_ok=True)

            if not os.path.exists(f"{args.dir}/.intro_endtime"):
                extract_frames(video_path, output_dir)

            progress.update(task, advance=1)

        # Analyze images
        last_frames = analyze_images(tmpdir)

        with open(f"{args.dir}/.intro_endtime", 'a') as fh:
            for filename, frame in last_frames.items():
                t = frame // 2
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
        
        args = parser.parse_args()
    
        main(args)
    except KeyboardInterrupt:
        console.print("[bold yellow]You cancelled the operation.[/bold yellow]")
        sys.exit(0)
