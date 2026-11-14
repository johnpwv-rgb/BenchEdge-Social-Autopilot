#!/usr/bin/env python3
"""
BenchEdge Systems — Multi-Channel Automation Engine (YouTube, TikTok & Reddit)
Reads scheduled campaigns from Google Sheets (90_Day_Content_Calendar) or local JSON/CSV,
and dispatches uploads/posts safely with rate-limit guards and --dry-run mode.

Required pip packages on your host / GitHub Actions runner:
  pip install google-api-python-client google-auth-oauthlib gspread praw requests
"""

import argparse
import json
import os
import sys
import time
import requests

# Default Sheet ID for BenchEdge_Marketing_Command_Center_and_Content_Tracker
DEFAULT_SHEET_ID = "1G4OOvtKdmRdw57NDi-bi9wEHCQBLUn7cMeYEYv_NsV8"


def load_campaigns_from_gsheet(sheet_id: str, tab_name: str = "90_Day_Content_Calendar"):
    import gspread
    from google.oauth2.service_account import Credentials

    creds_json = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON")
    if not creds_json:
        raise RuntimeError("Missing GOOGLE_SERVICE_ACCOUNT_JSON environment variable.")
    info = json.loads(creds_json)
    scopes = ["https://www.googleapis.com/auth/spreadsheets"]
    creds = Credentials.from_service_account_info(info, scopes=scopes)
    gc = gspread.authorize(creds)
    ws = gc.open_by_key(sheet_id).worksheet(tab_name)
    return ws.get_all_records()


def upload_youtube_video(mp4_path: str, title: str, description: str, tags: list, privacy: str = "private", dry_run: bool = True):
    """
    Uploads an MP4 to YouTube via YouTube Data API v3 (videos.insert).
    Default quota: 100 videos.insert calls/day, 10,000 units/day.
    Note: Unverified OAuth apps upload as 'private' until Google API audit approval.
    """
    if dry_run:
        print(f"[DRY-RUN][YouTube] Would upload '{mp4_path}' | Title: {title} | Privacy: {privacy}")
        return {"status": "dry_run", "title": title}

    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaFileUpload

    token_json = os.environ.get("YOUTUBE_OAUTH_TOKEN_JSON")
    if not token_json:
        raise RuntimeError("Missing YOUTUBE_OAUTH_TOKEN_JSON environment variable.")

    creds = Credentials.from_authorized_user_info(json.loads(token_json))
    youtube = build("youtube", "v3", credentials=creds)

    body = {
        "snippet": {
            "title": title[:100],
            "description": description,
            "tags": tags,
            "categoryId": "28",  # Science & Technology
        },
        "status": {
            "privacyStatus": privacy,
            "selfDeclaredMadeForKids": False,
        },
    }
    media = MediaFileUpload(mp4_path, chunksize=-1, resumable=True, mimetype="video/mp4")
    request = youtube.videos().insert(part="snippet,status", body=body, media_body=media)
    response = None
    while response is None:
        status, response = request.next_chunk()
        if status:
            print(f"[YouTube] Upload progress: {int(status.progress() * 100)}%")
    print(f"[YouTube] Uploaded Video ID: {response.get('id')}")
    return response


def upload_tiktok_video(mp4_path: str, caption: str, mode: str = "MEDIA_UPLOAD", dry_run: bool = True):
    """
    Uploads an MP4 to TikTok via Content Posting API v2.
    - MEDIA_UPLOAD: Sends video to creator's TikTok Inbox/Drafts (no Direct Post audit required).
    - DIRECT_POST: Publishes immediately to TikTok feed (requires audited TikTok app).
    """
    if dry_run:
        print(f"[DRY-RUN][TikTok] Mode={mode} | File='{mp4_path}' | Caption='{caption[:60]}...'")
        return {"status": "dry_run", "mode": mode}

    access_token = os.environ.get("TIKTOK_ACCESS_TOKEN")
    if not access_token:
        raise RuntimeError("Missing TIKTOK_ACCESS_TOKEN environment variable.")

    file_size = os.path.getsize(mp4_path)
    endpoint = (
        "https://open.tiktokapis.com/v2/post/publish/inbox/video/init/"
        if mode == "MEDIA_UPLOAD"
        else "https://open.tiktokapis.com/v2/post/publish/video/init/"
    )
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json; charset=UTF-8",
    }
    payload = {
        "post_info": {"title": caption[:150], "privacy_level": "SELF_ONLY"},
        "source_info": {
            "source": "FILE_UPLOAD",
            "video_size": file_size,
            "chunk_size": file_size,
            "total_chunk_count": 1,
        },
    }
    init_resp = requests.post(endpoint, headers=headers, json=payload, timeout=30)
    init_resp.raise_for_status()
    data = init_resp.json().get("data", {})
    upload_url = data["upload_url"]

    with open(mp4_path, "rb") as video_file:
        put_headers = {
            "Content-Type": "video/mp4",
            "Content-Range": f"bytes 0-{file_size - 1}/{file_size}",
        }
        put_resp = requests.put(upload_url, headers=put_headers, data=video_file, timeout=120)
        put_resp.raise_for_status()

    print(f"[TikTok] Uploaded successfully ({mode}). Publish ID: {data.get('publish_id')}")
    return data


def post_reddit_thread(subreddit_name: str, title: str, body_md: str, dry_run: bool = True):
    """
    Submits a technical text post to Reddit using PRAW (OAuth2 free tier: 100 QPM).
    Always test with dry_run=True first and verify subreddit self-promotion rules.
    """
    if dry_run:
        print(f"[DRY-RUN][Reddit] r/{subreddit_name} | Title: {title}\nBody Preview: {body_md[:140]}...")
        return {"status": "dry_run", "subreddit": subreddit_name}

    import praw

    reddit = praw.Reddit(
        client_id=os.environ["REDDIT_CLIENT_ID"],
        client_secret=os.environ["REDDIT_CLIENT_SECRET"],
        username=os.environ["REDDIT_USERNAME"],
        password=os.environ["REDDIT_PASSWORD"],
        user_agent="BenchEdgeSystems:RecommerceContentBot:v1.0 (by /u/" + os.environ["REDDIT_USERNAME"] + ")",
    )
    subreddit = reddit.subreddit(subreddit_name)
    submission = subreddit.submit(title=title, selftext=body_md)
    print(f"[Reddit] Posted to r/{subreddit_name}: https://reddit.com{submission.permalink}")
    time.sleep(2)  # Respect rate limits cleanly
    return {"id": submission.id, "url": submission.url}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="BenchEdge Multi-Channel Social Publisher")
    parser.add_argument("--channel", choices=["youtube", "tiktok", "reddit", "all"], default="all")
    parser.add_argument("--mp4", default="benchedge_short.mp4", help="Path to 9:16 MP4 for YouTube/TikTok")
    parser.add_argument("--publish", action="store_true", help="Actually publish (omit for safe --dry-run)")
    args = parser.parse_args()

    is_dry = not args.publish
    print(f"Running BenchEdge Channel Automator | Mode: {'DRY-RUN' if is_dry else 'LIVE PUBLISH'}")

    if args.channel in ("youtube", "all"):
        upload_youtube_video(
            mp4_path=args.mp4,
            title="8-Second MacBook Triage Test (Zero Screws) #shorts #palletflipping",
            description="Test customer-return laptops in 8 seconds using an FNIRSI FNB58 USB-C meter and Anker 100W GaN charger.",
            tags=["liquidation pallets", "electronics flipping", "usb-c tester", "microsoldering"],
            privacy="private",
            dry_run=is_dry,
        )

    if args.channel in ("tiktok", "all"):
        upload_tiktok_video(
            mp4_path=args.mp4,
            caption="How a $42 USB-C meter spots a dead MacBook motherboard in 8 seconds #electronicsrepair #palletflipping",
            mode="MEDIA_UPLOAD",
            dry_run=is_dry,
        )

    if args.channel in ("reddit", "all"):
        post_reddit_thread(
            subreddit_name="Flipping",
            title="Empirical Salvage Curves Across 8 Electronics Liquidation Tiers + Free Bid-Cap Calculator",
            body_md="Built an underwriting breakdown comparing Grade A/B working yields vs. 17%-25% brick/locked rates on untested customer-return pallets.",
            dry_run=is_dry,
        )