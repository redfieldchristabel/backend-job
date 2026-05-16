#!/bin/bash

# install packages
python -m pip install -r requirements.txt

# run server
python -m uvicorn src.app:app --host 0.0.0.0 --port 8000 --reload