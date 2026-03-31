# Python BankBot – AI Chatbot for Banking Queries

## Technologies Used
- Python
- Rasa
- Flask
- MySQL

## Features
- FAQ chatbot
- Account queries
- Banking assistance
- Web interface

## Setup Instructions

1. Clone repository
2. Create virtual environment:
   python -m venv rasa_env
3. Activate:
   rasa_env\Scripts\activate
4. Install dependencies:
   pip install -r requirements.txt

## Run Project
use on termial, use 4 different terminals-
rasa train
rasa run actions
rasa run --enable-api --cors "*"
python app.py
