from flask import Flask, render_template, request, jsonify
import yt_dlp
import logging
from flask_cors import CORS
import random
import time
from functools import lru_cache
import requests
from settings import FEATURES
import json
from bs4 import BeautifulSoup
import pickle
from datetime import datetime, timedelta
import base64
import isodate
import urllib.parse
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import os
import re
from http.server import BaseHTTPRequestHandler
from urllib.parse import parse_qs, unquote
from requests.adapters import HTTPAdapter  
from concurrent.futures import ThreadPoolExecutor, TimeoutError
import functools
from requests.adapters import Retry
from requests.sessions import Session





app = Flask(__name__, static_url_path='/static')
CORS(app,resources={r"/*": {"origins": "*"}})
# Enhanced logging setup
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = app.logger
API_KEY = 'AIzaSyDD2lvW5RRswUJOLpyE-6l5wZdjkmhmT6Y'
YOUTUBE_API_SERVICE_NAME = 'youtube'
YOUTUBE_API_VERSION = 'v3'
RATE_LIMIT_REQUESTS = 100  # Quota units per user
RATE_LIMIT_WINDOW = 3600   # 1 hour window
MAX_RETRIES = 3

executor = ThreadPoolExecutor(max_workers=3)
def timeout_handler(timeout):
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            future = executor.submit(func, *args, **kwargs)
            try:
                result = future.result(timeout=timeout)
                return result
            except TimeoutError:
                future.cancel()
                raise TimeoutError("Operation timed out")
        return wrapper
    return decorator

@app.route('/')
def home():
    return render_template('index.html', features=FEATURES)
class YouTubeExtractor:
    def __init__(self, api_key):
        self.api_key = api_key
        self.youtube = build('youtube', 'v3', developerKey=api_key)
        self.session = requests.Session()
        self.timeout = 15  # Increased timeout
        self._setup_session()
        
        # Setup detailed logging
        # self.logger = logging.getLogger(__name__)
        # self.logger.setLevel(logging.DEBUG)
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logging.DEBUG)
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
        self.logger.addHandler(handler)

    def _get_rotating_headers(self):
        """Generate different header combinations to avoid detection"""
        user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:120.0) Gecko/20100101 Firefox/120.0',
            'Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1'
        ]
        
        headers = {
            'User-Agent': random.choice(user_agents),
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
            'Origin': 'https://www.youtube.com',
            'Referer': 'https://www.youtube.com/',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Sec-Fetch-User': '?1',
            'Upgrade-Insecure-Requests': '1',
            'Connection': 'keep-alive',
            'DNT': '1'
        }
        
        # self.logger.debug(f"Generated headers: {headers}")
        return headers

    def _setup_session(self):
        """Setup session with retry mechanism"""
        retry_strategy = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)
        
        self.session.headers.update(self._get_rotating_headers())
        
        # Set required cookies with longer expiry
        cookies = {
            'CONSENT': 'YES+1',
            'VISITOR_INFO1_LIVE': str(random.randint(100000, 999999)),
            'PREF': f'f4={random.randint(4000, 8000)}&hl=en',
            'GPS': '1'
        }
        
        for name, value in cookies.items():
            self.session.cookies.set(name, value, domain='.youtube.com')

    def safe_request(self, url, method='get', **kwargs):
        """Make a safe request with retries and error handling"""
        try:
            kwargs['timeout'] = kwargs.get('timeout', self.timeout)
            response = getattr(self.session, method)(url, **kwargs)
            response.raise_for_status()
            return response
        except requests.Timeout:
            self.logger.error(f"Timeout occurred while requesting {url}")
            raise
        except requests.RequestException as e:
            self.logger.error(f"Request failed for {url}: {str(e)}")
            raise
    def _parse_player_config(self, html):
        """Parse the player configuration from HTML with improved patterns"""
        try:
            # self.logger.debug("Starting player config extraction")
            
            # Method 1: Direct ytInitialPlayerResponse
            match = re.search(r'ytInitialPlayerResponse\s*=\s*({.+?});', html)
            if match:
                # self.logger.debug("Found ytInitialPlayerResponse")
                return json.loads(match.group(1))
                

            # Method 2: From ytInitialData
            match = re.search(r'ytInitialData\s*=\s*({.+?});', html)
            if match:
                # self.logger.debug("Found ytInitialData")
                    data = json.loads(match.group(1))
                    if 'playerResponse' in data:
                        return data['playerResponse']
                

            # Method 3: From script tags
            soup = BeautifulSoup(html, 'html.parser')
            for script in soup.find_all('script'):
                if script.string and 'ytInitialPlayerResponse' in script.string:
                    match = re.search(r'ytInitialPlayerResponse\s*=\s*({.+?});', script.string)
                    if match:
                        # self.logger.debug("Found ytInitialPlayerResponse in script tag")
                        return json.loads(match.group(1))
                        

            # self.logger.warning("No valid player config found")

            
        except Exception as e:
            # self.logger.error(f"Error in _parse_player_config: {str(e)}")
            return None

    def _extract_formats_from_config(self, config):
        """Safer format extraction with validation"""
        if not config or not isinstance(config, dict):
            return []

        formats = []
        try:
            streaming_data = config.get('streamingData', {})
            if not streaming_data:
                return formats

            for format_list_name in ['adaptiveFormats', 'formats']:
                format_list = streaming_data.get(format_list_name, [])
                
                for format_data in format_list:
                    try:
                        if not isinstance(format_data, dict):
                            continue

                        # Validate required fields
                        mime_type = format_data.get('mimeType', '')
                        if not mime_type.startswith('video/'):
                            continue

                        format_info = {
                            'format_id': format_data.get('itag'),
                            'ext': mime_type.split('/')[-1].split(';')[0],
                            'height': format_data.get('height', 0),
                            'quality': format_data.get('qualityLabel', f"{format_data.get('height', 0)}p"),
                            'vcodec': format_data.get('codecs', '').split('.')[0],
                            'acodec': 'mp4a.40.2' if format_list_name == 'formats' else 'none',
                            'url': None
                        }

                        # Safe URL extraction
                        if 'url' in format_data:
                            format_info['url'] = format_data['url']
                        elif 'signatureCipher' in format_data:
                            cipher_data = parse_qs(format_data['signatureCipher'])
                            if cipher_data.get('url'):
                                base_url = unquote(cipher_data['url'][0])
                                signature = unquote(cipher_data.get('s', [''])[0])
                                sp = cipher_data.get('sp', ['signature'])[0]
                                
                                format_info['url'] = f"{base_url}&{sp}={signature}" if signature else base_url

                        # Validate format_info before adding
                        if format_info['url'] and all(k in format_info for k in [
                            'format_id', 'ext', 'height', 'quality', 'vcodec', 'acodec'
                        ]):
                            formats.append(format_info)

                    except Exception as e:
                        self.logger.warning(f"Error processing format: {str(e)}")
                        continue

            return formats

        except Exception as e:
            self.logger.error(f"Error extracting formats: {str(e)}")
            return formats

    def extract_video_id(self, url):
        """Extract video ID from various YouTube URL formats"""
        import re
        patterns = [
            r'(?:v=|\/videos\/|embed\/|youtu.be\/|\/v\/|\/e\/|watch\?v%3D|watch\?feature=player_embedded&v=|%2Fvideos%2F|embed%\u200C\u200B2F|youtu.be%2F|%2Fv%2F)([^#\&\?\n]*)',
            r'(?:https?:\/\/)?(?:www\.)?(?:youtube\.com|youtu\.be)\/(?:watch\?v=)?(.+)',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        return None

    def get_video_info(self, url, max_retries=3):
        """Enhanced video info extraction with better error handling"""
        start_time = time.time()
        self.logger.info(f"Starting video extraction for URL: {url}")
        
        try:
            video_id = self.extract_video_id(url)
            if not video_id:
                raise ValueError("Could not extract video ID")

            # First try to get video metadata from API
            for attempt in range(max_retries):
                try:
                    # API request with timeout
                    video_response = self.youtube.videos().list(
                        part='snippet,contentDetails',
                        id=video_id
                    ).execute()

                    if not video_response.get('items'):
                        raise ValueError("No video found in API response")

                    video = video_response['items'][0]
                    snippet = video.get('snippet', {})
                    content_details = video.get('contentDetails', {})

                    # Validate required fields
                    if not snippet or not content_details:
                        raise ValueError("Missing required video metadata")

                    # Get thumbnail with validation
                    thumbnails = snippet.get('thumbnails', {})
                    thumbnail_url = None
                    for quality in ['maxres', 'high', 'medium', 'default']:
                        thumb = thumbnails.get(quality, {})
                        if thumb and thumb.get('url'):
                            thumbnail_url = thumb['url']
                            break
                    
                    if not thumbnail_url:
                        raise ValueError("No thumbnail URL found")

                    # Try different URL patterns with timeouts
                    formats = None
                    urls_to_try = [
                        f"https://www.youtube.com/watch?v={video_id}",
                        f"https://www.youtube.com/embed/{video_id}"
                    ]

                    for url_to_try in urls_to_try:
                        try:
                            response = self.safe_request(
                                url_to_try,
                                headers=self._get_rotating_headers()
                            )
                            
                            config = self._parse_player_config(response.text)
                            if config:
                                formats = self._extract_formats_from_config(config)
                                if formats:
                                    break
                                
                        except Exception as e:
                            self.logger.warning(f"Failed to extract from {url_to_try}: {str(e)}")
                            continue

                    if not formats:
                        raise ValueError("Could not extract video formats")

                    # Create result with validation
                    try:
                        duration = isodate.parse_duration(content_details.get('duration', 'PT0S'))
                        result = {
                            'title': snippet.get('title', 'Untitled'),
                            'duration': int(duration.total_seconds()),
                            'thumbnail': thumbnail_url,
                            'formats': formats
                        }
                        
                        # Validate result
                        if not all(k in result for k in ['title', 'duration', 'thumbnail', 'formats']):
                            raise ValueError("Missing required fields in result")
                            
                        self.logger.info(f"Successfully extracted video info in {time.time() - start_time:.2f}s")
                        return result

                    except (ValueError, AttributeError) as e:
                        raise ValueError(f"Error creating result: {str(e)}")

                except Exception as e:
                    self.logger.error(f"Attempt {attempt + 1} failed: {str(e)}")
                    if attempt < max_retries - 1:
                        time.sleep(min(2 ** attempt, 8))  # Cap maximum sleep time
                    else:
                        raise

        except Exception as e:
            self.logger.error(f"Failed to extract video info: {str(e)}")
            return None

class CustomYTDLP(yt_dlp.YoutubeDL):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.success_count = 0
        self.last_request_time = 0
        
    def _download_webpage(self, *args, **kwargs):
        # Add delay between requests
        current_time = time.time()
        if self.last_request_time:
            time_diff = current_time - self.last_request_time
            if time_diff < 2:  # Minimum 2 second delay between requests
                time.sleep(2 - time_diff)
        
        self.last_request_time = time.time()
        return super()._download_webpage(*args, **kwargs)

# youtube_api = YouTubeAPI(API_KEY)

def check_rate_limit(request):
    """Rate limiting with IP-based quota tracking"""
    client_ip = request.headers.get('X-Forwarded-For', request.remote_addr)
    client_ip = base64.b64encode(client_ip.encode()).decode()
    
    current_time = time.time()
    
    if not hasattr(app, 'rate_limit_cache'):
        app.rate_limit_cache = {}
        
    # Clean up old entries
    app.rate_limit_cache = {
        k: v for k, v in app.rate_limit_cache.items() 
        if current_time - v['timestamp'] < RATE_LIMIT_WINDOW
    }
    
    if client_ip not in app.rate_limit_cache:
        app.rate_limit_cache[client_ip] = {
            'quota': RATE_LIMIT_REQUESTS - 1,
            'timestamp': current_time
        }
        return True
        
    if current_time - app.rate_limit_cache[client_ip]['timestamp'] < RATE_LIMIT_WINDOW:
        if app.rate_limit_cache[client_ip]['quota'] <= 0:
            return False
        app.rate_limit_cache[client_ip]['quota'] -= 1
    else:
        app.rate_limit_cache[client_ip] = {
            'quota': RATE_LIMIT_REQUESTS - 1,
            'timestamp': current_time
        }
    
    return True

def get_rotating_user_agent():
    """Rotate between different user agents to avoid detection."""
    user_agents = [
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/115.0',
        'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    ]
    return random.choice(user_agents)

@lru_cache(maxsize=100)
def get_video_info(url):
    """Extract video metadata with enhanced error handling and anti-bot measures."""
    retry_count = 0
    max_retries = 3
    
    while retry_count < max_retries:
        try:
            ydl_opts = {
                'quiet': True,
                'no_warnings': True,
                'extract_flat': False,
                'format': 'best',
                'http_headers': {
                    'User-Agent': get_rotating_user_agent(),
                    'Accept-Language': 'en-US,en;q=0.9',
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
                    'Sec-Fetch-Mode': 'navigate',
                    'Sec-Fetch-Site': 'none',
                    'Sec-Fetch-User': '?1',
                    'Sec-Fetch-Dest': 'document',
                },
                'extractor_args': {
                    'youtube': {
                        'player_client': ['android', 'web'],
                        'player_skip': ['webpage', 'config', 'js'],
                        'skip': ['hls', 'dash']
                    }
                },
                'socket_timeout': 30,
                'retries': 5,
                'nocheckcertificate': True,
                'ignoreerrors': False
            }

            with CustomYTDLP(ydl_opts) as ydl:
                try:
                    info = ydl.extract_info(url, download=False)
                except Exception as e:
                    if "Sign in to confirm you're not a bot" in str(e):
                        # Try alternative extraction method
                        ydl_opts.update({
                            'extractor_args': {
                                'youtube': {
                                    'player_client': ['tv_embedded', 'android'],
                                    'player_skip': ['webpage'],
                                    'skip': ['hls']
                                }
                            }
                        })
                        # Add delay before retry
                        time.sleep(random.uniform(2, 4))
                        with CustomYTDLP(ydl_opts) as ydl_retry:
                            info = ydl_retry.extract_info(url, download=False)
                    else:
                        raise

                if info is None:
                    return None

                # Process formats with validation
                formats = []
                seen_qualities = set()
                
                for f in info.get('formats', []):
                    if not isinstance(f, dict):
                        continue
                        
                    if f.get('vcodec') == 'none':
                        continue
                        
                    height = f.get('height', 0)
                    if not isinstance(height, (int, float)) or height <= 0:
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

                formats.sort(key=lambda x: x['height'], reverse=True)
                
                # Validate required fields
                title = info.get('title')
                if not title or not isinstance(title, str):
                    title = 'Untitled'
                
                thumbnail = info.get('thumbnail', '')
                if not isinstance(thumbnail, str):
                    thumbnail = ''
                
                duration = info.get('duration', 0)
                if not isinstance(duration, (int, float)):
                    duration = 0
                
                return {
                    'title': title,
                    'formats': formats,
                    'duration': duration,
                    'thumbnail': thumbnail
                }

        except Exception as e:
            retry_count += 1
            error_message = str(e)
            
            if retry_count >= max_retries:
                if "Sign in to confirm you're not a bot" in error_message:
                   return None
                elif "This video is private" in error_message:
                   return None
                elif "Video unavailable" in error_message:
                    return None
                else:
                    logger.error(f"Error extracting info: {error_message}")
                    return None
            
            # Add exponential backoff delay before retry
            time.sleep(2 ** retry_count)


@app.route("/download", methods=["POST"])
def download():
    """Enhanced download endpoint using YouTube Data API"""

    video_url = request.form.get("video_url")
    if not video_url:
        return jsonify({"error": "No video URL provided"}), 400
        
    try:
        @timeout_handler(timeout=25)  # 25 second timeout
        def extract_info(url):
            extractor = YouTubeExtractor(API_KEY)
            return extractor.get_video_info(url)    
        # if not check_rate_limit(request):
        #     return jsonify({
        #         "error": "Rate limit exceeded",
        #         "retry_after": RATE_LIMIT_WINDOW,
        #         "message": "Please try again later"
        #     }), 429
        video_data = get_video_info(video_url)
        if video_data:
            # return jsonify(video_data)
            return render_template(
            "download.html",
            title=video_data["title"],
            thumbnail=video_data["thumbnail"],
            quality_options=video_data["formats"],
            features=FEATURES,
            video_url=video_url
            )
        else :
            logger.info(f"Processing download request for URL: {video_url}")
            video_data = extract_info(video_url)

        # if not video_data:
        #     return jsonify({
        #         "error": "Video processing failed",
        #         "message": "Unable to extract video information. Please check the URL and try again."
        #     }), 400

        # if not video_data.get('formats'):
        #     return jsonify({
        #         "error": "No formats available",
        #         "message": "No downloadable formats found for this video."
        #     }), 400

            logger.info(f"Successfully processed video: {video_data['title']}")
            logger.debug(f"Available formats: {json.dumps(video_data['formats'], indent=2)}")
            return jsonify(video_data)
        # return render_template(
        #     "download.html",
        #     title=video_data["title"],
        #     thumbnail=video_data["thumbnail"],
        #     quality_options=video_data["formats"],
        #     features=FEATURES,
        #     video_url=video_url
        #  )
            # if not video_data:
            #     return jsonify({
            #         "error": "Invalid YouTube URL",
            #         "message": "Please provide a valid YouTube video URL"
            #     }), 400
            
            # video_data = youtube_api.get_video_details(video_id)
            
            # if not video_data.get('formats'):
            #     return jsonify({
            #         "error": "No downloadable formats",
            #         "message": "This video might be restricted or unavailable"
            #     }), 400
                
            # return jsonify(video_data)
            # return render_template(
            # "download.html",
            # title=video_data["title"],
            # thumbnail=video_data["thumbnail"],
            # quality_options=video_data["formats"],
            # features=FEATURES,
            # video_url=video_url
            # )
        
    except HttpError as e:
        error_message = str(e)
        logger.error(f"YouTube API error: {error_message}")
        
        if e.resp.status == 403:
            return jsonify({
                "error": "API quota exceeded",
                "message": "Please try again later"
            }), 429
        elif e.resp.status == 404:
            return jsonify({
                "error": "Video not found",
                "message": "The requested video does not exist or is private"
            }), 404
        else:
            return jsonify({
                "error": "YouTube API error",
                "message": "Please try again later"
            }), 500
            
    except Exception as e:
        error_message = str(e)
        logger.error(f"Download error: {error_message}")
        return jsonify({
            "error": "Failed to process video",
            "message": "Please try again later"
        }), 500

if __name__ == '__main__':
    app.run(debug=False)    