python -m venv venv
source venv/Scripts/activate
python -m pip install --upgrade pip
python -m pip install --upgrade setuptools
pip install -r requirements.txt --no-deps
apt-get update && apt-get install -y ffmpeg