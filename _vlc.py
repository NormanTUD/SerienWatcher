import subprocess

def play_video(video_path):
    # Starte den VLC-Player mit dem Video und der Option, VLC zu schließen, wenn das Video zu Ende ist
    process = subprocess.Popen(['vlc', '--play-and-exit', '--fullscreen', video_path])
    
    # Warte, bis der VLC-Prozess beendet ist
    process.wait()

def main():
    videos = ["1.mp4", "2.mp4"]  # Liste der Videos

    for video in videos:
        print(f"Spiele {video}...")
        play_video(video)  # Spiel das Video ab
        print(f"{video} beendet.")

if __name__ == "__main__":
    main()

