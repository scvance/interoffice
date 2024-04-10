#!/bin/bash
mkdir -p ~/.virtualenvs
python3 -m venv ~/.virtualenvs/interoffice_venv
source ~/.virtualenvs/interoffice_venv/bin/activate
pip3 install -r requirements.txt
python3 server.py
