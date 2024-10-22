import json
import subprocess
import time
import random
import os

def format_size(size_bytes):
    """Convert size in bytes to a human-readable format."""
    if size_bytes is None:
        return "Unknown"
    try:
        size_bytes = float(size_bytes)
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size_bytes < 1024.0:
                return f"{size_bytes:.2f} {unit}"
            size_bytes /= 1024.0
    except (ValueError, TypeError):
        return "Unknown"
    

def is_format_downloadable(format_id, url):
    try:
        command = ['youtube-dl', '-f', format_id, '-g', url]
        result = subprocess.run(command, capture_output=True, text=True, timeout=10)
        return result.returncode == 0
    except subprocess.TimeoutExpired:
        return False
def extract_format_data(format_data, duration):
    filesize = format_data.get("filesize") or format_data.get("filesize_approx")
    if filesize is None and format_data.get("tbr") is not None and duration is not None:
        try:
            estimated_size = (float(format_data["tbr"]) * 1024 * float(duration)) / 8  # in bytes
            filesize = round(estimated_size)
        except (ValueError, TypeError):
            filesize = None
    
    return {
        "extension": format_data.get("ext", ""),
        "format_name": format_data.get("format", ""),
        "url": format_data.get("url", ""),
        "format_id": format_data.get("format_id", ""),
        "acodec": format_data.get("acodec", "none"),
        "vcodec": format_data.get("vcodec", "none"),
        "height": format_data.get("height"),
        "width": format_data.get("width"),
        "filesize": filesize,
        "tbr": format_data.get("tbr"),  # Total bitrate
     }

def extract_video_data_from_url(url):
    def run_command(command, max_retries=3, initial_delay=1, max_delay=3):
       for attempt in range(max_retries):
           try:
               result = subprocess.run(command, capture_output=True, text=True, check=True)
               return json.loads(result.stdout)
           except subprocess.CalledProcessError as e:
               print(f"Attempt {attempt + 1} failed: {e}")
               print(f"Error output: {e.stderr}")
               if attempt + 1 == max_retries:
                   print("Max retries reached. Giving up.")
                   return None
               delay = min(initial_delay * (2 ** attempt) + random.uniform(0, 1), max_delay)
               print(f"Retrying in {delay:.2f} seconds...")
               time.sleep(delay) 


     # Path to the yt-dlp binary
    yt_dlp_path = os.path.join(os.getcwd(), 'bin', 'yt-dlp_linux')
    
    # Make sure the binary is executable
    os.chmod(yt_dlp_path, 0o755)

    # Try yt-dlp first
    yt_dlp_command = [yt_dlp_path, '-J', '--no-playlist', '--socket-timeout', '30', url]
    info = run_command(yt_dlp_command)

    # If yt-dlp fails, try youtube-dl
    if info is None:
        youtube_dl_command = ['youtube-dl', '-J', '--no-playlist', '--socket-timeout', '60', url]
        info = run_command(youtube_dl_command)

    quality_options = []
    if info is None:
        raise Exception("Failed to extract video information")
    

    title = info.get('title', 'Unknown Title')
    formats = info.get('formats', [])
    thumbnails = info.get('thumbnails', [])
    duration = info.get('duration')

    formats = [extract_format_data(format_data, duration) for format_data in formats]
    def find_best_audio_match(video_format, audio_formats):
        video_bitrate = video_format.get('tbr', 0) or 0
        return min(audio_formats, key=lambda a: abs((a.get('tbr', 0) or 0) - video_bitrate))
    
    # Extract video-only formats
    video_formats = [f for f in info.get('formats', []) if f.get('vcodec') != 'none' and f.get('acodec') == 'none']
    
    # Extract audio-only formats
    audio_formats = [f for f in info.get('formats', []) if f.get('acodec') != 'none' and f.get('vcodec') == 'none']
        
    if video_formats and audio_formats:
        # Sort video formats by quality (using height as a proxy for quality)
        video_formats.sort(key=lambda x: (x.get('height', 0) or 0, x.get('tbr', 0) or 0), reverse=True)
        # Sort audio formats by quality (using bitrate as a proxy for quality)
        audio_formats.sort(key=lambda x: x.get('tbr', 0) or 0, reverse=True)
        # Create quality options
        for v_format in video_formats:
                # Find the best matching audio format
                best_audio = find_best_audio_match(v_format, audio_formats) # Find the best matching audio format
                quality_name = f"{v_format.get('height', 'Unknown')}p"
                video_size = v_format.get('filesize') or 0
                audio_size = best_audio.get('filesize') or 0
                total_size = video_size + audio_size
                if total_size > 0:
                    size_str = format_size(total_size)
                else:
                    size_str = "Unknown"
                quality_options.append({
                            "quality": quality_name,
                            "video_format_id": v_format.get('format_id', ''),
                            "audio_format_id": best_audio.get('format_id', ''),
                            "extension": v_format.get('ext', 'mp4'),
                            "total_size": size_str,
                            "video_tbr": f"{v_format.get('tbr', 0):.2f} Kbps" if v_format.get('tbr') is not None else "Unknown",
                            "audio_tbr": f"{best_audio.get('tbr', 0):.2f} Kbps" if best_audio.get('tbr') is not None else "Unknown"
                        })
    else:
            # Use all formats as quality options
            for format_data in formats:
                if is_format_downloadable(format_data["format_id"],url) or format_data["format_id"].find("hls"):
                    quality_name = f"{format_data.get('height', 'Unknown')}p"
                    size_str = format_size(format_data.get('filesize'))
                    quality_options.append({
                                        "quality": quality_name,
                                        "video_format_id": format_data.get('format_id', ''),
                                        "audio_format_id": format_data.get('format_id', ''),
                                        "extension": format_data.get('ext', 'mp4'),
                                        "total_size": size_str,
                                        "video_tbr": f"{format_data.get('tbr', 0):.2f} Kbps" if format_data.get('tbr') is not None else "Unknown",
                                        
                                })
    return {
        "title": title,
        "quality_options": quality_options,
        "thumbnails": thumbnails
    }
