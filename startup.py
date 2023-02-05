# region Importing important imports

from flask import Flask, request, jsonify, Response
import json
import numpy as np
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from collections import defaultdict
from datetime import datetime
from dateutil import tz

# endregion Importing important imports


# region Inits

# filenames
SCOREBOARD_DS_NAME = "Content_datathon2023_scoreboard"
EVAL_DS_NAME = "Eval_datathon2023"
EVAL_DF_PATH = "data/eval_datathon2023.pkl"
PRIVATE_PATHS = "configs/private_paths" # deleted later
SCOREBOARD_PATH = "data/scoreboard2023.pkl"
TEAMBOARD_PATH = "data/teamboard2023.pkl"
LOG_PATH = "logs/dt2023.logs"
CMS_KEY = "configs/cms_key.json"


# use creds to create a client to interact with the Google Drive API
SCOPE = ['https://spreadsheets.google.com/feeds',
        'https://www.googleapis.com/auth/drive']
CREDS = ServiceAccountCredentials.from_json_keyfile_name(CMS_KEY, SCOPE)

AM_TZ = tz.gettz("Asia/Yerevan")
TASK_REVEAL = datetime(2023, 2, 10, 19, 0, tzinfo = AM_TZ)
ACCEPTING_SUBMISSIONS = datetime(2023, 2, 11, 17, 40, tzinfo = AM_TZ)
END_OF_SUBMISSIONS = datetime(2023, 2, 11, 18, 15, tzinfo = AM_TZ)

team_passwords = defaultdict(lambda: [])

# setting non-public path for updating the dataset to 
# avoid google sheet api limit hits by other parties 
with open(PRIVATE_PATHS, "r") as f:
    p_paths = [p.replace("\n", "") for p in f.readlines()]
del PRIVATE_PATHS


NOT_REVEALED_MSG = "I value your acumen and interest, but the task is not yet revealed."
TEAM_NOT_FOUND_MSG = f"Your team was not found in the list, please contact Mher Movsisyan - phone: ({p_paths[3]})."
ENDED_MSG = "The datathon has ended :( \nContact Mher Movsisyan if you think this is a mistake."
DIFF_LEN_MSG = """The length of the list `predictions` doesn't match the evaluation data length.
Also, make sure that the order of predicted labels matches the fetched dataset."""
NOT_ALL_DATA_MSG = "This is not all the data, once the submission process begins you will be \
given a larger dataset through this endpoint."


app = Flask(__name__)


#endregion Inits
    
    
    
# region Gugo's sheets
    
# region Evaluation dataset

@app.route(p_paths[0])
def fetch_dataset(req=True):
    """Pulls and stores the eval dataset from google sheets onto the file system"""
    client = gspread.authorize(CREDS)
    wb = client.open(EVAL_DS_NAME)
    datasheet = wb.get_worksheet(0)
    dataframe = pd.DataFrame(datasheet.get_all_records())
    
    dataframe.to_pickle(EVAL_DF_PATH)
    
    return Response(f"Success: fetched {len(dataframe)} rows worth of data", status=200) if req else dataframe
    
def load_dataset():
    """Loads eval dataset from the file system, if no file exists it fetches from the google sheets"""
    try:
        return pd.read_pickle(EVAL_DF_PATH)
    except FileNotFoundError as e:
        return fetch_dataset(req=False)
    
# endregion Evaluation dataset
    
eval_df = load_dataset()


# region Teams
print(p_paths)

@app.route(p_paths[1])
def fetch_teams(req=True):
    """Fetches and stores team credentials"""
    
    client = gspread.authorize(CREDS)
    wb = client.open(SCOREBOARD_DS_NAME)
    
    # get teams and their participants
    teamsheet = wb.worksheet("teams")
    teams_df = pd.DataFrame(teamsheet.get_all_records())
        
    teams_df.to_pickle(TEAMBOARD_PATH)
    
    for i, team, name, password in teams_df.itertuples():
        team_passwords[team] += [password]
        
    return Response(f"Success. Participants are {teams_df.Name.values}") if req else teams_df

def load_teams():
    """Loads teams from the file system, if no file exists it fetches from google sheets"""
    try:
        teams_df = pd.read_pickle(TEAMBOARD_PATH)
        
        for i, team, name, password in teams_df.itertuples():
            team_passwords[team] += [password]
            
        return teams_df
    except FileNotFoundError as e:
        return fetch_teams(req=False)
        
# endregion Teams

teams_df = load_teams()



# region Scoreboard
        
@app.route(p_paths[2])
def fetch_scoreboard(req=True):
    """Fetches and stores scoreboard data"""
    client = gspread.authorize(CREDS)
    wb = client.open(SCOREBOARD_DS_NAME)
    
    scoreboard = wb.worksheet("scoreboard")
    score_df = pd.DataFrame(scoreboard.get_all_records())
    
    score_df.to_pickle(SCOREBOARD_PATH)
    
    return Response(f"Success. Teams are {score_df.Team.values}") if req else teams_df

def load_scoreboard():
    """Loads the scoreboard from the file system, if no file exists it fetches from google sheets"""
    try:
        return pd.read_pickle(SCOREBOARD_PATH)
    except FileNotFoundError as e:
        return fetch_scoreboard(req=False)
    

# To make `accept_submission` thread-safe, I will use only write
# to the `scoreboard` sheet and append to the `submissions` sheet

def accept_submission(team, score):
    """Handles succesfull submissions in a thread-safe manner"""

    
    այժմ = datetime.now().astimezone(AM_TZ).strftime("%Y-%m-%d %H:%M:%S")
    
    client = gspread.authorize(CREDS)
    wb = client.open(SCOREBOARD_DS_NAME)
    submissions = wb.worksheet("submissions")
    
    # Append submission to list
    submissions.append_row([team, score, այժմ])
    
    
    ### Mash the submissions into a scoreboard ###
    # Get all submissions
    score_df = pd.DataFrame(submissions.get_all_records())
    score_df.Score = score_df.Score.astype("float")
    
    # Get the maximum per team
    team_max = score_df.groupby("Team").max("Score").reset_index()
    _isin = score_df[["Team", "Score"]].stack().isin(team_max.stack().values).unstack()
    score_df = score_df[_isin.all(axis=1)].groupby("Team").first().reset_index()
    
    # Sort
    score_df = score_df.sort_values("Score", ascending=False)
    # Post updated scoreboard
    scoreboard = wb.worksheet("scoreboard")
    scoreboard.update([score_df.columns.values.tolist()] + score_df.values.tolist())
    score_df.to_pickle(SCOREBOARD_PATH)
    
    return score_df

#endregion Scoreboard


# endregion Gugo's sheets



paths = {
    "accuracy": "/d2023/accuracy",
    "data": "/d2023/data",
    "main": "/d2023"
}


@app.route(paths["main"], methods=["GET"])
def instructions():
    """Instructs on API usage """
    return jsonify({'message': f'''To submit your results, make a POST request to the "{paths["accuracy"]}"
        endpoint with a JSON object containing the keys `predictions`, `team`, `auth_token`. The 
        value of `predictions` is a list of model outputs. Don\'t alter the order of the eval data. 
        You can access the evaluation data by sending a GET request to "{paths["data"]}".''' + \
        '''\n
        Sample request body:
        {
            "predictions": [0,0,1,1,0,1,...,1,0,0,1],
            "team": "Conquerors",
            "auth_token": "secret_token"
        }
        
        '''})
    

@app.route(paths["accuracy"], methods=["POST"])
def calculate_accuracy():
    """Handles submission requests"""
    data = request.get_json()
    print("\n" + str(data))
    այժմ = datetime.now().astimezone(AM_TZ)
    competing = False
    
    # region Checks
    
    for k in ["predictions", "team", "auth_token"]:
        if k not in data.keys():
            return Response(f"Please specify `{k}` in the request.", status=400)
    
    if data["team"] not in team_passwords.keys():
        return Response(TEAM_NOT_FOUND_MSG, 
                        status=400)
        
    if data["auth_token"] not in team_passwords[data["team"]]:
        return Response("Wrong authentication token.", 
                        status=401)
    
    if len(data["predictions"]) != (101 if (այժմ > TASK_REVEAL and այժմ < ACCEPTING_SUBMISSIONS) else len(eval_df)):
        return Response(DIFF_LEN_MSG, status=422)
        
    # endregion Checks
        
    submitted_list = np.array(data['predictions'])
    accuracy = -1 # placeholder
    
    if այժմ < TASK_REVEAL:
        return Response(json.dumps({"message": NOT_REVEALED_MSG}), status=403)
    else:
        if այժմ > END_OF_SUBMISSIONS:
            return Response(json.dumps({"message": ENDED_MSG}), status=403)
        
        if այժմ < ACCEPTING_SUBMISSIONS:
            accuracy = np.sum(eval_df.loc[250:350].Label == data["predictions"])/101
            accuracy = np.round(accuracy, 5) * 100
        else:
            competing = True
        

    if competing:
        accuracy = np.sum(eval_df.Label == data["predictions"])/len(eval_df) 

        accuracy = np.round(accuracy, 5) * 100
        accept_submission(data["team"], accuracy)
    
    
    with open(LOG_PATH, "a") as f:
        f.write("\n" + "\t".join([
            այժմ.strftime("%Y-%m-%d %H:%M:%S"), 
            str(data["team"]), 
            str(data["auth_token"]), 
            str(accuracy)
        ]))
    
    return jsonify({
            "message": "Success." + (" This will be reflected in the scoreboard." if competing else 
                                     " This ssubmission will not be reflected on the scoreboard, submit" + \
                                     " again once we start accepting full submissions"),
            "team": data["team"],
            "accuracy": str(accuracy)
        })


@app.route(paths["data"], methods=["GET"])
def serve_data():
    """This is the endpoint used by participants to fetch evaluation data. 
    (No labels will be sent out)"""
    
    այժմ = datetime.now().astimezone(AM_TZ)
    
    if այժմ < TASK_REVEAL:
        return Response(json.dumps({"message": NOT_REVEALED_MSG}), status=403)
    else:
        if այժմ > END_OF_SUBMISSIONS:
            return Response(json.dumps({"message": ENDED_MSG}), status=403)
        
        if այժմ < ACCEPTING_SUBMISSIONS:
            return Response(
                json.dumps(
                    {
                        "data": eval_df.loc[250:350].X.to_list(), 
                        "message": NOT_ALL_DATA_MSG
                    }
                ), 
                status=200)
            
        return Response(
            json.dumps(
                {
                "data": eval_df.X.to_list(), 
                "message": "Good luck!"
                }
            ), 
            status=200)
    

if __name__ == '__main__':
    app.run()