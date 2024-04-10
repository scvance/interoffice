#!/bin/bash
mkdir -p ~/.virtualenvs
venv_location="$HOME/.virtualenvs/interoffice_venv"
if [ -d "$venv_location" ]; then
	echo "Already set up, skipping setup steps..."
	source ~/.virtualenvs/interoffice_venv/bin/activate
else
	python3 -m venv ~/.virtualenvs/interoffice_venv
	source ~/.virtualenvs/interoffice_venv/bin/activate
	pip3 install -r requirements.txt
fi
python3 server.py
