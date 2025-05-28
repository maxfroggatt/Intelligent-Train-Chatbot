# Train Chatbot System (CMP-6040B AI Coursework)

This project is a conversational AI system developed as part of the CMP-6040B Artificial Intelligence coursework at UEA. The chatbot is designed to assist users in:

- **Finding the cheapest train tickets** in the UK
- **Predicting train arrival times** in case of delays
- **Interacting via a GUI** built with Tkinter in Python

## Technologies Used

- **Python 3.8+**
- **Tkinter** - GUI
- **spaCy / NLTK** - NLP
- **Scikit-learn** - ML model
- **Selenium** - Web scraping
- **SQLite / CSV** - Data storage (optional)

## Setup Instructions

Run gui.py (for the tkinter GUI interface) or main.py (for CLI based interaction)

These should already be currently completed for you, but if you encounter any errors/issues then Run:
1. load_data.py (to load the data from the XML file into a SQLite database)
2. feature_engineering.py (to create features for the ML model)
3. model_evaluation.py (to evaluate the ML model)
4. Make sure RandomForest_best_model.joblib is in the chatbot directory.
5. Make sure the env file has:

DARWIN_AWS_KEY=AKIA3CA6JZWQYBAEVZHX
DARWIN_AWS_SECRET=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
REGION=eu-west-1
BUCKET_NAME=darwin.xmltimetable
PREFIX=PPTimetable/

6. Run gui.py (for the tkinter GUI interface) or main.py (for CLI based interaction)

Test input for train prediction: '202412247127459, NRW, 10, LST'

Note: The webscraper for national rail could potentially break if the website changes.
It currently fully works as of 28-05-2025.