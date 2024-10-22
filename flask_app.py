from flask import Flask, render_template, request, jsonify, send_file, Response, current_app
import flask
from extractor import extract_video_data_from_url
from settings import FEATURES
import subprocess
import tempfile
import os
import json
import traceback
import shutil
import logging
from werkzeug.exceptions import HTTPException
from flask_cors import CORS
import time
import yt_dlp


app = Flask(__name__, static_url_path='/static')
CORS(app)
logging.basicConfig(level=logging.DEBUG)
logger = app.logger

def get_video_info(url):
    """Extract video metadata with enhanced error handling and anti-bot measures."""
    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'extract_flat': False,
        'format': 'best',
        # Enhanced browser-like headers
        'http_headers': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Sec-Fetch-User': '?1',
            'Sec-Fetch-Dest': 'document',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Cookie': ''  # Will be populated by yt-dlp
        },
        # Advanced extractor configuration
        'extractor_args': {
            'youtube': {
                'player_client': ['android', 'web'],  # Try multiple clients
                'player_skip': ['webpage', 'config', 'js'],  # Skip unnecessary data
                'skip': ['hls', 'dash']  # Skip streaming formats
            }
        },
        'socket_timeout': 30,
        'retries': 5,  # Increase retry attempts
        'nocheckcertificate': True,
        'ignoreerrors': False
    }
    
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        try:
            # First attempt - normal extraction
            try:
                info = ydl.extract_info(url, download=False)
            except Exception as e:
                if "Sign in to confirm you're not a bot" in str(e):
                    # Modify options for retry with different approach
                    ydl_opts.update({
                        'extractor_args': {
                            'youtube': {
                                'player_client': ['tv_embedded', 'android'],
                                'player_skip': ['webpage'],
                                'skip': ['hls']
                            }
                        }
                    })
                    # Retry with modified options
                    with yt_dlp.YoutubeDL(ydl_opts) as ydl_retry:
                        info = ydl_retry.extract_info(url, download=False)
                else:
                    raise

            if info is None:
                raise Exception("Could not extract video information")
            
            # Filter and clean formats
            formats = []
            seen_qualities = set()
            
            for f in info.get('formats', []):
                # Skip formats without video
                if f.get('vcodec') == 'none':
                    continue
                    
                # Create quality identifier
                height = f.get('height', 0)
                if height == 0:
                    continue
                    
                quality = f"{height}p"
                if quality in seen_qualities:
                    continue
                    
                seen_qualities.add(quality)
                
                formats.append({
                    'format_id': f['format_id'],
                    'ext': f.get('ext', 'mp4'),
                    'height': height,
                    'filesize': f.get('filesize', 0),
                    'tbr': f.get('tbr', 0),
                    'quality': quality,
                    'vcodec': f.get('vcodec', ''),
                    'acodec': f.get('acodec', '')
                })
            
            # Sort formats by height (quality)
            formats.sort(key=lambda x: x['height'], reverse=True)
            
            return {
                'title': info.get('title', 'Untitled'),
                'formats': formats,
                'duration': info.get('duration', 0),
                'thumbnail': info.get('thumbnail', '')
            }

        except Exception as e:
            error_message = str(e)
            if "Sign in to confirm you're not a bot" in error_message:
                raise Exception("This video requires additional verification. Please try again later or use a different URL.")
            elif "This video is private" in error_message:
                raise Exception("This video is private and cannot be accessed.")
            elif "Video unavailable" in error_message:
                raise Exception("This video is unavailable. It may have been removed or deleted.")
            else:
                logger.error(f"Error extracting info: {error_message}")
                raise Exception("Failed to extract video information. Please try again later.")


@app.errorhandler(Exception)
def handle_exception(e):
    # Pass through HTTP errors
    if isinstance(e, HTTPException):
        return e

    # Now you're handling non-HTTP exceptions only
    logger.error(f"An error occurred: {str(e)}")
    logger.error(traceback.format_exc())
    return jsonify(error=str(e)), 500

@app.route('/')
def home():
    return render_template('index.html', features=FEATURES)

@app.route("/download", methods=["POST"])
def download():
    video_url = request.form.get("video_url")
    if not video_url:
        return jsonify({"error": "No video URL provided"}), 400
        
    try:
        video_data = get_video_info(video_url)
        
        if not video_data.get('formats'):
            return jsonify({"error": "No downloadable formats found for this video"}), 400
            
        return render_template(
            "download.html",
            title=video_data["title"],
            thumbnail=video_data["thumbnail"],
            quality_options=video_data["formats"],
            features=FEATURES,
            video_url=video_url
        )
    except Exception as e:
        error_message = str(e)
        logger.error(f"Download error: {error_message}")
        return jsonify({"error": error_message}), 400

@app.route('/download_video', methods=['POST', 'GET'])

def download_video():
    if request.method == 'GET':
        return jsonify({"error": "This endpoint only accepts POST requests"}), 405
    
    video_url = request.form.get('video_url')
    video_format_id = request.form.get('video_format_id')
    audio_format_id = request.form.get('audio_format_id')

    if not video_url or not video_format_id:
        return jsonify({"success": False, "error": "Missing URL or format IDs"}), 400

    def generate():
        with app.app_context():
            try:
                with tempfile.TemporaryDirectory() as temp_dir:
                    output_file = os.path.join(temp_dir, 'output.mp4')
                     # Check if we're dealing with a combined format or separate video/audio
                    
                    if video_format_id == audio_format_id:
                        download_command = [
                            'yt-dlp',
                            '-f', f'{video_format_id}+{audio_format_id}' if video_format_id != audio_format_id else video_format_id,
                            '--merge-output-format', 'mp4',
                            '-o', output_file,
                            '--no-check-certificates',
                            '--no-playlist',
                            '--user-agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                            video_url
                            ]
                        yield f"data: {json.dumps({'progress': 'Starting download'})}\n\n"
                        download_process = subprocess.Popen(download_command, 
                                                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True)
                        for line in download_process.stdout:
                            yield f"data: {json.dumps({'progress': 'Downloading: ' + line.strip()})}\n\n"
                        download_process.wait()
                        if download_process.returncode != 0:
                            yield f"data: {json.dumps({'error': 'Download failed'})}\n\n"
                            return
                    else:
                        video_file = os.path.join(temp_dir, 'video.mp4')
                        audio_file = os.path.join(temp_dir, 'audio.m4a')
                        # Download video
                        yield f"data: {json.dumps({'progress': 'Starting video download'})}\n\n"
                        logger.info('Starting video download')
                        video_process = subprocess.Popen(['yt-dlp', '-f', video_format_id, '-o', video_file, video_url], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True)
                        for line in video_process.stdout:
                            logger.debug(f"yt-dlp output: {line.strip()}")
                            yield f"data: {json.dumps({'progress': 'Downloading video: ' + line.strip()})}\n\n"
                        video_process.wait()
                        if video_process.returncode != 0:
                            yield f"data: {json.dumps({'error': 'Video download failed'})}\n\n"
                            return
                        # Download audio
                        yield f"data: {json.dumps({'progress': 'Starting audio download'})}\n\n"
                        audio_process = subprocess.Popen(['yt-dlp', '-f', audio_format_id, '-o', audio_file, video_url], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True)
                        for line in audio_process.stdout:
                            yield f"data: {json.dumps({'progress': 'Downloading audio: ' + line.strip()})}\n\n"
                        audio_process.wait()
                        if audio_process.returncode != 0:
                            yield f"data: {json.dumps({'error': 'Audio download failed'})}\n\n"
                            return

                        # Merge video and audio
                        yield f"data: {json.dumps({'progress': 'Merging video and audio'})}\n\n"
                        merge_process = subprocess.Popen(['ffmpeg', '-i', video_file, '-i', audio_file, '-c', 'copy', output_file], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True)
                        for line in merge_process.stdout:
                            yield f"data: {json.dumps({'progress': 'Merging: ' + line.strip()})}\n\n"
                        merge_process.wait()
                        if merge_process.returncode != 0:
                            yield f"data: {json.dumps({'error': 'Merging failed'})}\n\n"
                            return

                    # Get video info
                    yield f"data: {json.dumps({'progress': 'Getting video info'})}\n\n"
                    max_retries = 3
                    retry_delay = 3
                    for attempt in range(max_retries):
                        info_command = ['yt-dlp', '-J', '--no-playlist', '--socket-timeout', '30', 
                                            '--no-check-certificates',
                                             video_url]
                        info_process = subprocess.Popen(info_command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                        info_output, info_stderr = info_process.communicate()
                        if info_process.returncode == 0:
                            break
                        elif attempt < max_retries - 1:
                            yield f"data: {json.dumps({'progress': f'Retry {attempt + 1}/{max_retries}: Getting video info failed. Retrying in {retry_delay} seconds...'})}\n\n"
                            time.sleep(retry_delay)
                        else:
                            yield f"data: {json.dumps({'error': f'Failed to get video info after {max_retries} attempts: {info_stderr.decode()}'})}\n\n"
                            return 

                    if info_process.returncode != 0:
                        yield f"data: {json.dumps({'error': f'Failed to get video info: {info_stderr.decode()}'})}\n\n"
                        return

                    video_info = json.loads(info_output)
                    title = video_info.get('title', 'video')
                    ext = 'mp4'
                    filename = f"{title}.{ext}"
                    downloads_folder = os.path.join(os.path.expanduser('~'), 'Downloads')
                    final_output_path = os.path.join(downloads_folder, filename)

                    # Move the file to the Downloads folder
                    os.makedirs(downloads_folder, exist_ok=True)
                    shutil.move(output_file, final_output_path)

                    yield f"data: {json.dumps({'success': True, 'output_path': final_output_path})}\n\n"
            except Exception as e:
                current_app.logger.error(f"Error in download process: {str(e)}")
                yield f"data: {json.dumps({'error': f'An error occurred: {str(e)}'})}\n\n"
    response = Response(generate(), mimetype='text/event-stream')
    response.headers.add('Access-Control-Allow-Origin', '*')  # السماح بكل الأصول
    response.headers.add('Cache-Control', 'no-cache')
    response.headers.add('X-Accel-Buffering', 'no')  # منع التخزين المؤقت
    return response

if __name__ == '__main__':
    app.run(debug=True)
