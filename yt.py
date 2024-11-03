import subprocess
import sys
import re
from urllib.parse import urlparse

def validate_url(url):
    """Validate if the URL is properly formatted."""
    try:
        result = urlparse(url)
        return all([result.scheme, result.netloc])
    except:
        return False

def run_you_get(url, debug=False, info_only=True):
    """
    Run you-get with error handling and debugging
    
    Args:
        url (str): The URL to download from
        debug (bool): Whether to run in debug mode
        info_only (bool): Only show video info without downloading
    """
    if not validate_url(url):
        return "Invalid URL format"
    
    # Prepare the command
    cmd = ['you-get']
    if debug:
        cmd.append('--debug')
    if info_only:
        cmd.append('--info')
    cmd.append(url)
    
    try:
        # Run the command and capture output
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=False  # Don't raise exception on non-zero return
        )
        
        if result.returncode != 0:
            # If there's an error, provide more detailed information
            error_msg = f"""
Error running you-get. Details:
Return code: {result.returncode}
Error output: {result.stderr}
Standard output: {result.stdout}

Troubleshooting steps:
1. Check your internet connection
2. Verify you have the latest version of you-get:
   pip install --upgrade you-get
3. Try running with debug mode:
   {' '.join(cmd[:-1])} --debug {cmd[-1]}
4. Make sure the URL is accessible in your browser
"""
            return error_msg
        
        return result.stdout
    
    except FileNotFoundError:
        return """
you-get is not installed or not in PATH. 
Install it using: pip install you-get
"""
    except Exception as e:
        return f"Unexpected error: {str(e)}"

if __name__ == "__main__":
    # Example usage
    url = "https://www.youtube.com/watch?v=2b2IbOm05Ww"
    print(run_you_get(url, debug=True, info_only=True))