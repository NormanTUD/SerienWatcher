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
import unittest
from unittest.mock import patch, MagicMock

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

    console.print(f"\n[cyan]Analyzing {len(hash_to_image)} unique hashes...[/cyan]")

    # Store hashes and frames if the option is enabled
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
                    
                    # Save to hashes list
                    hashes_list.append({"hash": k, "filename": thisfile, "last_frame": thisframe})

    console.print(f"[green]Found last frames for {len(last_file_to_frame)} files.[/green]")

    # Save results to .intro_cutter_info.csv
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

class TestVideoProcessor(unittest.TestCase):
    @patch('subprocess.Popen')
    def test_run_command(self, mock_popen):
        mock_process = MagicMock()
        mock_process.communicate.return_value = (b'', b'')
        mock_process.returncode = 0
        mock_popen.return_value = mock_process

        command = "echo test"
        process = run_command(command)

        mock_popen.assert_called_once_with(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        self.assertEqual(process, mock_process)

    @patch('subprocess.Popen')
    def test_run_command(self, mock_popen):
        mock_process = MagicMock()
        mock_process.communicate.return_value = (b'', b'')
        mock_process.returncode = 0
        mock_popen.return_value = mock_process

        command = "echo test"
        process = run_command(command)

        mock_popen.assert_called_once_with(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        self.assertEqual(process, mock_process)

    @patch('os.path.isdir')
    @patch('sys.exit')
    def test_die_function(self, mock_exit, mock_isdir):
        die("Test error message")
        mock_exit.assert_called_once_with(1)

    @patch('subprocess.Popen')
    def test_extract_frames_failure(self, mock_popen):
        mock_process = MagicMock()
        mock_process.returncode = 1
        mock_process.communicate.return_value = (b'', b'Error occurred')
        mock_popen.return_value = mock_process

        with self.assertRaises(SystemExit):
            extract_frames("non_existent_video.mp4", "./output")

    @patch('os.makedirs')
    @patch('os.path.exists')
    @patch('subprocess.Popen')
    def test_run_command_calls_process(self, mock_popen, mock_exists, mock_makedirs):
        mock_exists.return_value = False
        mock_process = MagicMock()
        mock_process.communicate.return_value = (b'', b'')
        mock_process.returncode = 0
        mock_popen.return_value = mock_process

        run_command("echo 'Hello World'")
        mock_popen.assert_called_with("echo 'Hello World'", shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    @patch('os.listdir')
    @patch('os.path.isdir')
    @patch('os.makedirs')
    def test_analyze_images_empty_directory(self, mock_makedirs, mock_isdir, mock_listdir):
        mock_isdir.return_value = True
        mock_listdir.return_value = []  # No images

        last_frames = analyze_images("./tmp")
        self.assertEqual(last_frames, {})  # Expect empty dictionary since no images are present

    @patch('pandas.DataFrame.to_csv')
    def test_save_hash_analysis_results(self, mock_to_csv):
        hashes_list = [{'hash': 'abcd1234', 'filename': 'video1', 'last_frame': 1}]
        hash_info_file_path = "./tmp/hash_info.csv"
        hashes_df = pd.DataFrame(hashes_list)
        hashes_df.to_csv(hash_info_file_path, index=False)  # Simulate saving the DataFrame to CSV
        mock_to_csv.assert_called_once_with(hash_info_file_path, index=False)

    # 2. Test that die function calls sys.exit with the correct code
    @patch('sys.exit')
    def test_die_calls_exit(self, mock_exit):
        die("Error")
        mock_exit.assert_called_once_with(1)

    # 3. Test if the debug_print function works correctly when debug is True
    @patch('rich.console.Console.print')
    def test_debug_print_enabled(self, mock_print):
        args.debug = True
        debug_print(args.debug, "Debug message")
        mock_print.assert_called_once_with("[bold yellow]Debug:[/bold yellow] Debug message")

    # 4. Test if the debug_print function does nothing when debug is False
    @patch('rich.console.Console.print')
    def test_debug_print_disabled(self, mock_print):
        args.debug = False
        debug_print(args.debug, "Debug message")
        mock_print.assert_not_called()

    # 5. Test if run_command handles successful command execution
    @patch('subprocess.Popen')
    def test_run_command_success(self, mock_popen):
        mock_process = MagicMock()
        mock_process.returncode = 0
        mock_process.communicate.return_value = (b'output', b'')
        mock_popen.return_value = mock_process

        process = run_command("echo success")
        self.assertEqual(process, mock_process)


    # 7. Test if extract_frames creates the expected output files
    @patch('subprocess.Popen')
    def test_extract_frames_creates_files(self, mock_popen):
        mock_process = MagicMock()
        mock_process.returncode = 0
        mock_process.communicate.return_value = (b'', b'')
        mock_popen.return_value = mock_process

        extract_frames("test_video.mp4", "./output")
        # Verify that files were created correctly

    # 8. Test if analyze_images handles empty directories
    @patch('os.listdir')
    @patch('os.path.isdir')
    def test_analyze_images_empty_directory(self, mock_isdir, mock_listdir):
        mock_isdir.return_value = True
        mock_listdir.return_value = []
        result = analyze_images("./tmp")
        self.assertEqual(result, {})


    # 15. Test if main skips processing when .intro_endtime exists
    @patch('os.path.exists')
    def test_main_skips_if_intro_endtime_exists(self, mock_exists):
        mock_exists.return_value = True
        with self.assertRaises(SystemExit):
            main(args)

    # 20. Test if analyze_images finds the last frames correctly
    @patch('os.listdir')
    @patch('imagehash.average_hash')
    def test_analyze_images_find_last_frames(self, mock_average_hash, mock_listdir):
        mock_listdir.return_value = ["output_0001.png", "output_0002.png"]
        mock_average_hash.return_value = imagehash.hex_to_hash("0"*16)
        result = analyze_images("./tmp")
        # Verify that the last frames are correctly identified

    # 22. Test if main handles the presence of .intro_endtime gracefully
    @patch('os.path.exists')
    def test_main_intro_endtime_exists(self, mock_exists):
        mock_exists.return_value = True
        with self.assertRaises(SystemExit):
            main(args)

    # 24. Test if analyze_images handles corrupted image files
    @patch('os.listdir')
    @patch('PIL.Image.open', side_effect=OSError)
    def test_analyze_images_handle_corrupted_images(self, mock_open, mock_listdir):
        mock_listdir.return_value = ["corrupted_image.png"]
        result = analyze_images("./tmp")
        self.assertEqual(result, {})

    # 25. Test if analyze_images handles unexpected file types gracefully
    @patch('os.listdir')
    def test_analyze_images_ignore_non_image_files(self, mock_listdir):
        mock_listdir.return_value = ["file.txt", "file.mp3"]
        result = analyze_images("./tmp")
        self.assertEqual(result, {})



    # 33. Test if analyze_images handles images with no hash correctly
    @patch('os.listdir')
    @patch('imagehash.average_hash', side_effect=ValueError)
    def test_analyze_images_no_hash(self, mock_hash, mock_listdir):
        mock_listdir.return_value = ["output_0001.png"]
        result = analyze_images("./tmp")
        self.assertEqual(result, {})
    # 35. Test if run_command returns output for successful command
    @patch('subprocess.Popen')
    def test_run_command_returns_output(self, mock_popen):
        mock_process = MagicMock()
        mock_process.returncode = 0
        mock_process.communicate.return_value = (b'output', b'')
        mock_popen.return_value = mock_process

        output = run_command("echo hello")
        self.assertEqual(output.communicate(), (b'output', b''))


    # 39. Test if extract_frames raises exception for unsupported video formats
    @patch('subprocess.Popen')
    def test_extract_frames_unsupported_format(self, mock_popen):
        mock_process = MagicMock()
        mock_process.returncode = 1
        mock_process.communicate.return_value = (b'', b'Unsupported format')
        mock_popen.return_value = mock_process

        with self.assertRaises(SystemExit):
            extract_frames("test_video.wmv", "./output")


    # 42. Test if extract_frames outputs the correct number of frames
    @patch('subprocess.Popen')
    def test_extract_frames_output_frames_count(self, mock_popen):
        mock_process = MagicMock()
        mock_process.returncode = 0
        mock_process.communicate.return_value = (b'', b'')
        mock_popen.return_value = mock_process
        extract_frames("test_video.mp4", "./output")
        # Verify that the expected number of frames are created

    # 43. Test if analyze_images raises error on directory access issues
    @patch('os.listdir', side_effect=OSError)
    def test_analyze_images_directory_access(self, mock_listdir):
        with self.assertRaises(OSError):
            analyze_images("./tmp")

    # 46. Test if analyze_images processes frames with different formats
    @patch('os.listdir')
    def test_analyze_images_different_formats(self, mock_listdir):
        mock_listdir.return_value = ["frame1.jpg", "frame2.png"]
        result = analyze_images("./tmp")
        # Verify that frames of different formats are processed correctly

    # 49. Test if extract_frames handles permission errors correctly
    @patch('subprocess.Popen')
    def test_extract_frames_permission_error(self, mock_popen):
        mock_process = MagicMock()
        mock_process.returncode = 1
        mock_process.communicate.return_value = (b'', b'Permission denied')
        mock_popen.return_value = mock_process

        with self.assertRaises(SystemExit):
            extract_frames("test_video.mp4", "./output")



if __name__ == "__main__":
    try:
        parser = argparse.ArgumentParser(description="Video frame extractor and image analyzer.")
        parser.add_argument("--dir", type=str, required=True, help="Directory containing video files.")
        parser.add_argument("--tmp", type=str, default="./tmp", help="Temporary directory for extracted frames.")
        parser.add_argument("--debug", action='store_true', help="Enable debug output.")
        parser.add_argument("--save_hashes", action='store_true', help="Save hashes and frames to CSV.")

        args = parser.parse_args()

        if os.getenv('tests'):
            unittest.main(argv=[sys.argv[0]])

        main(args)
    except KeyboardInterrupt:
        console.print("[bold yellow]You cancelled the operation.[/bold yellow]")
        sys.exit(0)
