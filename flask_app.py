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

app = Flask(__name__, static_url_path='/static')
CORS(app)
logging.basicConfig(level=logging.DEBUG)
logger = app.logger

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
    video_url = request.form["video_url"]
    try:
        video_data = extract_video_data_from_url(video_url)
        title = video_data["title"]
        thumbnail = video_data["thumbnails"][-1] if video_data["thumbnails"] else ""
        quality_options = video_data["quality_options"]
        return render_template("download.html", title=title, thumbnail=thumbnail,
                               quality_options=quality_options, features=FEATURES, video_url=video_url)
    except Exception as e:
        return jsonify({"error": str(e)}), 400

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
    app.run()