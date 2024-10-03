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

def die(message):
    console.print(f"[bold red]Error:[/bold red] {message}")
    sys.exit(1)

def extract_frames(video_path, output_dir):
    """Extract frames from the video using ffmpeg."""
    command = f"ffmpeg -i \"{video_path}\" -r 2 -to 00:02:00 \"{output_dir}/output_%04d.png\""
    subprocess.run(command, shell=True, check=True)

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

    for k in sorted(hash_to_image, key=lambda k: len(hash_to_image[k]), reverse=True):
        for item in hash_to_image[k]:
            match = re.match(rf"{tmpdir}/(.*)/output_(\d*).png", item)
            if match:
                thisfile = match.group(1)
                thisframe = int(match.group(2))

                if thisfile not in last_file_to_frame or last_file_to_frame[thisfile] < thisframe:
                    last_file_to_frame[thisfile] = thisframe

    return last_file_to_frame

def main(args):
    if not os.path.isdir(args.dir):
        die(f"Directory '{args.dir}' does not exist")

    tmpdir = os.path.join(args.tmp, "frames")
    os.makedirs(tmpdir, exist_ok=True)

    # Process each video file
    with Progress(transient=True) as progress:
        task = progress.add_task("[cyan]Processing videos...", total=len(os.listdir(args.dir)))
        for video_file in os.listdir(args.dir):
            if video_file.endswith(".mp4"):
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

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Video frame extractor and image analyzer.")
    parser.add_argument("--dir", type=str, required=True, help="Directory containing video files.")
    parser.add_argument("--tmp", type=str, default="./tmp", help="Temporary directory for extracted frames.")
    
    args = parser.parse_args()
    
    main(args)

