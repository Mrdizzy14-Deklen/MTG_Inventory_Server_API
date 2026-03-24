#!/bin/bash
python -m venv venv
source venv/bin/activate
pip install --upgrade pip
if [ -f requirements.txt ]; then
    pip install -r requirements.txt
    echo "Dependencies installed successfully."
else
    echo "requirements.txt not found."
fi