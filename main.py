import os
import logging
from dotenv import load_dotenv
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler
import requests

load_dotenv()

app_token=os.environ.get("SLACK_APP_TOKEN")
bot_token=os.environ.get("SLACK_BOT_TOKEN")
program_base_url=os.environ.get("PROGRAMS_BASE_URL")
channel_id=os.environ.get("SLACK_NOTIFICATION_CHANNEL_ID")

app=App(token=bot_token)
COUNT=5

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)

def fetch_programs():
    r=requests.get(f"{program_base_url}/api/v1/ysws/list", timeout=30)
    r.raise_for_status()
    return r.json()

def check_program_exists(program_name):
    programs=fetch_programs()
    for p in programs:
        if p==program_name:
            return True
    return False

def fetch_projects(n, program_name):
    r=requests.post(f"{program_base_url}/api/v1/query", json=
        {
        "filters": [{"field": "ysws", "op": "eq", "value": program_name}],
        "limit": n,
        "order_by": "airtable_id",
        "page": 1,
        "sort_direction": "desc"
        }
    )
    r.raise_for_status()
    return r.json()["data"][:n]

@app.command("/ships")
def handle_some_command(ack, respond, command, logger, client):
    ack()
    logger.info(f"Called by {command['user_name']}({command['user_id']}) in channel {command['channel_name']}({command['channel_id']}) using command {command['command']}")
    raw=command.get("text", "").strip()
    channel_id=command.get("channel_id")
    text=raw.split()

    if not raw:
        respond("Usage: `/ships <program> [count]`, e.g. `/ships name 5`")
        return

    if len(text) >= 2 and text[-1].isdigit():
        COUNT=int(text[-1])
        text.pop()
    program_name=" ".join(text)
    program_name=program_name.strip().lower().title()

    if check_program_exists(program_name):
        respond(f"Sending top {COUNT} projects from {program_name} in channel <#{channel_id}>...")
        print(fetch_projects(COUNT, program_name))
        return
    else:
        respond(f"Program {program_name} not found, please try again with exact program name.")
        return

if __name__ == "__main__":
    SocketModeHandler(app, app_token).start()
