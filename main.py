import os
import logging
from dotenv import load_dotenv
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler
import requests

load_dotenv()

app_token=os.environ.get("SLACK_APP_TOKEN")
bot_token=os.environ.get("SLACK_BOT_TOKEN")
signing_secret=os.environ.get("SLACK_SIGNING_SECRET")
program_base_url=os.environ.get("PROGRAMS_BASE_URL")
channelmanager_base_url=os.environ.get("CHANNELMANAGER_BASE_URL")
channel_id=os.environ.get("SLACK_NOTIFICATION_CHANNEL_ID")

app=App(token=bot_token, signing_secret=signing_secret)
COUNT=5

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)

def user_is_cm(channel_id):
    try:
        r=requests.get(f"{channelmanager_base_url}/cman/{channel_id}", timeout=30)
        r.raise_for_status()
        if r.json().get("error"):
            return None
        else:
            return r.json().get("data")
    except requests.RequestException:
        return False

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

def fetch_image(project):
    if not project["has_media"]:
        return None
    try:
        r=requests.get(f"{program_base_url}/api/v1/media/{project['id']}", timeout=30)
        r.raise_for_status()
        for media in r.json():
            if media.get("mime_type", "").startswith("image/"):
                return media["thumb_large_url"] or media["url"]
    except requests.RequestException:
        pass
    return None

def is_url(url):
    return isinstance(url, str) and url.startswith(("http://", "https://"))

def build_blocks(program, rank, image_url):
    name=program["inferred_repo"] or f"Project {program['id']}"
    desc=(program["description"] or "No description").strip()
    if len(desc) > 500:
        desc=desc[:497]+"..."

    stats=[f"⭐ {program['github_stars']}"]
    stats.append(f"⏱ {program['hours']}h")

    blocks = [
        {"type": "section", "text": {"type": "mrkdwn",
            "text": f"*# {rank} {name}*\n{desc}\n{'  |  '.join(stats)}"}},
    ]
    if is_url(image_url):
        blocks.append({"type": "image", "image_url": image_url, "alt_text": name})

    buttons=[]
    for label, key in [("Code", "code_url"), ("Demo", "demo_url"),
                       ("Archived repo", "archived_repo"), ("Archived demo", "archived_demo")]:
        if is_url(program[key]):
            buttons.append({"type": "button", "text": {"type": "plain_text", "text": label},
                            "url": program[key]})
    if buttons:
        blocks.append({"type": "actions", "elements": buttons})
    blocks.append({"type": "divider"})
    return blocks

@app.command("/ships")
def handle_some_command(ack, respond, command, logger, client):
    ack()
    logger.info(f"Called by {command['user_name']}({command['user_id']}) in channel {command['channel_name']}({command['channel_id']}) using command {command['command']}")
    raw=command.get("text", "").strip()
    channel_id=command.get("channel_id")

    if user_is_cm(channel_id) is None:
        respond(f"Channel <#{channel_id}> is a private channel. This command can only be used in public channels.")
        return
    elif command['user_id'] not in user_is_cm(channel_id):
        respond(f"You are not a channel manager for the <#{channel_id}>. Only channel managers can use this command.")
        return

    text=raw.split()

    if not raw:
        respond("Usage: `/ships <program> [count]`, e.g. `/ships name 5`")
        return

    if len(text) >= 2 and text[-1].isdigit():
        COUNT=int(text[-1])
        text.pop()
    else:
        COUNT=5
    program_name=" ".join(text)
    program_name=program_name.strip().lower().title()

    if check_program_exists(program_name):
        respond(f"Sending top {COUNT} projects from {program_name} in channel <#{channel_id}>...")
        projects=fetch_projects(COUNT, program_name)
        print(f"Fetched {len(projects)} projects for program {program_name}")    
        for i, p in enumerate(projects):
            blocks=build_blocks(p, i+1, fetch_image(p))
            client.chat_postMessage(channel=channel_id, text=f"Project #{i+1}", blocks=blocks)
        return
    else:
        respond(f"Program {program_name} not found, please try again with exact program name.")
        return

if __name__ == "__main__":
    if app_token:
        SocketModeHandler(app, app_token).start()
    else:
        app.start(port=int(os.environ.get("PORT", 3000)))
