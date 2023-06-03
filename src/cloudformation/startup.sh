sudo apt-get update -y
sudo add-apt-repository ppa:deadsnakes/ppa -y
sudo apt-get update -y
sudo apt-get install python3.11 python3.11-distutils git -y
git clone https://github.com/kevinl95/Ampease.git
cd Ampease
cd src
curl -sS https://bootstrap.pypa.io/get-pip.py | python3.11
python3.11 -m pip install poetry
python3.11 -m poetry install
cd webapp
python3.11 -m poetry run uvicorn main:app --reload