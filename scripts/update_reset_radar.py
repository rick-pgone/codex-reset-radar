#!/usr/bin/env python3.11
"""Update Codex Reset Radar data from X using a saved local browser session."""

from __future__ import annotations

import argparse
import asyncio
import html
import json
import os
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from playwright.async_api import async_playwright
from twikit import Client


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_COOKIE_FILE = Path("/Users/rick/登录态/x_cookies.json")
DEFAULT_OUTPUT = ROOT / "data" / "latest.json"
TZ = ZoneInfo("Asia/Shanghai")

OFFICIAL_ACCOUNTS = ["thsottiaux", "sama"]
SEARCH_QUERIES = [
    'codex "usage limits" reset',
    'codex "rate limits" reset',
    'codex limits drained',
    'codex limit out of sync',
    '@sama codex reset',
    '@thsottiaux codex reset',
]

SEED_RECORDS = [
    {
        "id": "2058280452851638313",
        "screen_name": "thsottiaux",
        "display_name": "Tibo",
        "created_at": "2026-05-23T20:14:00+00:00",
        "url": "https://x.com/thsottiaux/status/2058280452851638313",
        "text": "Some of you noticed limits drained faster in Codex, we root caused it to an optimization that we rolled back that had an impact on cache hit rates when compacting across long running sessions.\n\nWe fixed this and have now reset usage limits for all accounts. Enjoy the weekend.",
        "kind": "official",
    },
    {
        "id": "2057980213854921096",
        "screen_name": "thsottiaux",
        "display_name": "Tibo",
        "created_at": "2026-05-23T00:21:00+00:00",
        "url": "https://x.com/thsottiaux/status/2057980213854921096",
        "text": "OK",
        "context": "Hars asked @sama and @thsottiaux to reset Codex usage limits.",
        "kind": "official_reply",
    },
]


def load_playwright_cookies(path: Path) -> list[dict]:
    if not path.exists():
        return []
    cookies = json.loads(path.read_text(encoding="utf-8"))
    now = time.time()
    return [
        cookie
        for cookie in cookies
        if cookie.get("expires", -1) == -1 or cookie.get("expires", 0) > now
    ]


def cookie_dict(cookies: list[dict]) -> dict[str, str]:
    return {
        cookie["name"]: cookie["value"]
        for cookie in cookies
        if cookie.get("domain", "").endswith("x.com")
        or cookie.get("domain", "").endswith("twitter.com")
    }


def has_x_session(cookies: list[dict]) -> bool:
    values = cookie_dict(cookies)
    return bool(values.get("auth_token") and values.get("ct0"))


async def refresh_x_cookies(cookie_file: Path, timeout_sec: int) -> None:
    cookie_file.parent.mkdir(parents=True, exist_ok=True)
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False, args=["--start-maximized"])
        context = await browser.new_context(no_viewport=True)
        cookies = load_playwright_cookies(cookie_file)
        if cookies:
            await context.add_cookies(cookies)

        page = await context.new_page()
        await page.goto("https://x.com/thsottiaux", wait_until="domcontentloaded", timeout=60000)
        print("Complete X login in the opened browser window if needed.")

        deadline = time.time() + timeout_sec
        while time.time() < deadline:
            current_cookies = await context.cookies()
            if has_x_session(current_cookies):
                cookie_file.write_text(
                    json.dumps(current_cookies, ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )
                os.chmod(cookie_file, 0o600)
                await browser.close()
                return
            await page.wait_for_timeout(1500)

        await browser.close()
        raise TimeoutError("Timed out waiting for X login cookies.")


def parse_dt(value: str) -> datetime:
    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def to_local(value: str | datetime) -> datetime:
    dt = parse_dt(value) if isinstance(value, str) else value
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(TZ)


def clean_text(text: str) -> str:
    return " ".join((text or "").split())


def tweet_to_record(tweet, kind: str) -> dict:
    created = tweet.created_at_datetime
    if created.tzinfo is None:
        created = created.replace(tzinfo=timezone.utc)
    user = tweet.user
    screen_name = user.screen_name
    return {
        "id": str(tweet.id),
        "screen_name": screen_name,
        "display_name": getattr(user, "name", screen_name),
        "created_at": created.isoformat(),
        "url": f"https://x.com/{screen_name}/status/{tweet.id}",
        "text": tweet.text or "",
        "kind": kind,
    }


def classify(record: dict) -> str | None:
    text = clean_text(record.get("text", "")).lower()
    context = clean_text(record.get("context", "")).lower()
    combined = f"{text} {context}"
    official = record.get("screen_name", "").lower() in OFFICIAL_ACCOUNTS

    if "codex" not in combined and "usage limits" not in combined and "rate limits" not in combined:
        return None
    if official and "reset" in combined and any(word in combined for word in ["fixed", "all accounts", "back to normal", "usage limits"]):
        return "confirmed"
    if official and text.strip() in {"ok", "yes", "done"} and "reset" in combined:
        return "high"
    if official and any(word in combined for word in ["investigating", "looking", "fix", "drained", "out of sync", "reset"]):
        return "high"
    if "reset" in combined and any(word in combined for word in ["lol", "joke", "if this gets", "like"]):
        return "joke"
    if "reset" in combined and any(word in combined for word in ["codex", "usage limits", "rate limits"]):
        return "high"
    return None


def tag_score(tag: str) -> int:
    return {"confirmed": 3, "high": 2, "joke": 1}.get(tag, 0)


def month_name(dt: datetime) -> str:
    return dt.strftime("%b")


def local_labels(created_at: str) -> dict:
    dt = to_local(created_at)
    return {
        "date_short": {
            "zh": f"{dt.month} 月 {dt.day} 日",
            "en": f"{month_name(dt)} {dt.day}",
        },
        "full_time": {
            "zh": f"{dt.year} 年 {dt.month} 月 {dt.day} 日 · {dt:%H:%M} · UTC+8",
            "en": f"{month_name(dt)} {dt.day}, {dt.year} · {dt:%H:%M} · UTC+8",
        },
        "time": f"{dt:%H:%M}",
        "date": {
            "zh": f"{dt.month} 月 {dt.day} 日 · UTC+8",
            "en": f"{month_name(dt)} {dt.day} · UTC+8",
        },
    }


def tweet_html(record: dict) -> dict:
    text = html.escape(record.get("text", "")).replace("\n", "<br>")
    if record.get("context"):
        text = f"{html.escape(record['context'])}<br><br>{text}"
    text = text.replace("reset usage limits", "<strong>reset usage limits</strong>")
    text = text.replace("重置所有账号的使用额度", "<strong>重置所有账号的使用额度</strong>")
    return {"zh": text, "en": text}


def conclusion_for(tag: str) -> dict:
    if tag == "confirmed":
        return {"zh": "已重置额度", "en": "Usage limits reset"}
    if tag == "high":
        return {"zh": "未来几天可能会重置额度", "en": "Usage limits may reset in the next few days"}
    return {"zh": "弱信号，等待确认", "en": "Weak signal, awaiting confirmation"}


def summary_for(record: dict, tag: str) -> dict:
    if tag == "confirmed":
        return {
            "zh": "官方已确认修复，并重置所有账号的使用额度；当前不是预测信号，而是已发生的重置事件。",
            "en": "Official fix confirmed, with usage limits reset for all accounts. This is not a forecast signal; it is a completed reset event.",
        }
    if tag == "high":
        return {
            "zh": "已经出现官方回应或高密度用户反馈。这不是直接公告，但后续几天可能发生重置或修复说明。",
            "en": "Official response or clustered user complaints appeared. This is not a direct announcement, but a reset or fix note could follow in the next few days.",
        }
    return {
        "zh": "目前更像玩笑或弱信号，不能单独作为重置判断。",
        "en": "This looks like a joke or weak signal and should not be treated as reset evidence by itself.",
    }


def evidence_title(record: dict, tag: str) -> dict:
    name = record.get("display_name") or record.get("screen_name")
    if tag == "confirmed":
        return {"zh": f"{name} 确认重置或修复", "en": f"{name} confirms a reset or fix"}
    if tag == "high":
        return {"zh": f"{name} 给出高危回应", "en": f"{name} gives a high-risk response"}
    return {"zh": f"{name} 提到 reset", "en": f"{name} mentions reset"}


def evidence_text(record: dict, tag: str) -> dict:
    if tag == "confirmed":
        return {
            "zh": "官方明确提到 reset、fixed、back to normal 或 usage limits。",
            "en": "Officially mentions reset, fixed, back to normal, or usage limits.",
        }
    if tag == "high":
        return {
            "zh": "需要结合用户反馈和上下文理解，适合作为预警信号。",
            "en": "Needs context from user complaints and replies; useful as an early warning signal.",
        }
    return {
        "zh": "仅作为辅助信号，等待后续确认。",
        "en": "Auxiliary signal only; wait for follow-up confirmation.",
    }


def build_payload(records: list[dict], cadence_hours: int) -> dict:
    tagged = []
    for record in records:
        tag = classify(record)
        if not tag:
            continue
        item = {**record, "tag": tag}
        tagged.append(item)

    if not tagged:
        tagged = [{**SEED_RECORDS[0], "tag": "confirmed"}]

    tagged.sort(key=lambda r: (tag_score(r["tag"]), parse_dt(r["created_at"])), reverse=True)
    latest = tagged[0]
    latest_labels = local_labels(latest["created_at"])

    evidence = []
    for record in tagged[:8]:
        labels = local_labels(record["created_at"])
        evidence.append(
            {
                "tag": record["tag"],
                "time": labels["time"],
                "date": labels["date"],
                "title": evidence_title(record, record["tag"]),
                "text": evidence_text(record, record["tag"]),
                "quote": {
                    "zh": f"推文信息：{clean_text(record.get('context', '') + ' ' + record.get('text', '')).strip()}",
                    "en": f"Tweet info: {clean_text(record.get('context', '') + ' ' + record.get('text', '')).strip()}",
                },
                "links": [{"label": record["url"].replace("https://", ""), "url": record["url"]}],
            }
        )

    return {
        "generated_at": datetime.now(TZ).isoformat(timespec="seconds"),
        "cadence_hours": cadence_hours,
        "latest": {
            "tag": latest["tag"],
            "source_type": "official" if latest.get("screen_name", "").lower() in OFFICIAL_ACCOUNTS else "user",
            "date_short": latest_labels["date_short"],
            "full_time": latest_labels["full_time"],
            "conclusion": conclusion_for(latest["tag"]),
            "summary": summary_for(latest, latest["tag"]),
            "source_title": {
                "zh": f"推特来源 · {latest.get('display_name') or latest.get('screen_name')}",
                "en": f"Tweet source · {latest.get('display_name') or latest.get('screen_name')}",
            },
            "url": latest["url"],
            "tweet_html": tweet_html(latest),
        },
        "analysis": {
            "confidence": latest["tag"],
            "text": {
                "zh": "系统会优先关注官方确认、官方回复和用户集中反馈。最强模式通常是 Codex 额度异常消耗、使用额度不同步，或官方承认正在调查/已修复。",
                "en": "The monitor prioritizes official confirmations, official replies, and clustered user complaints. The strongest pattern is abnormal Codex limit drain, out-of-sync limits, or official acknowledgement of investigation/fix.",
            },
            "metrics": [
                {
                    "title": {"zh": "触发原因", "en": "Trigger"},
                    "text": {"zh": "用户集中反馈 Codex limit/reset 异常。", "en": "Clustered user reports around Codex limit/reset anomalies."},
                },
                {
                    "title": {"zh": "官方回应", "en": "Official response"},
                    "text": {"zh": "优先追踪 Tibo 与 Sama 的推文和回复。", "en": "Prioritizes posts and replies from Tibo and Sama."},
                },
                {
                    "title": {"zh": "结果", "en": "Outcome"},
                    "text": {"zh": "根据措辞标记为确信、高危或玩笑。", "en": "Labels each signal as confirmed, high-risk, or joke based on wording."},
                },
            ],
        },
        "evidence": evidence,
    }


async def fetch_records(cookie_file: Path, hours: int, count: int) -> list[dict]:
    cookies = load_playwright_cookies(cookie_file)
    values = cookie_dict(cookies)
    if not values.get("auth_token") or not values.get("ct0"):
        raise RuntimeError(f"Missing X auth cookies in {cookie_file}")

    client = Client("en-US")
    client.set_cookies(values, clear_cookies=True)
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    records: dict[str, dict] = {}

    for screen_name in OFFICIAL_ACCOUNTS:
        user = await client.get_user_by_screen_name(screen_name)
        for tweet_type in ["Tweets", "Replies"]:
            tweets = await client.get_user_tweets(user.id, tweet_type, count=count)
            for tweet in tweets:
                created = tweet.created_at_datetime
                if created.tzinfo is None:
                    created = created.replace(tzinfo=timezone.utc)
                if created >= cutoff:
                    records[str(tweet.id)] = tweet_to_record(tweet, "official" if tweet_type == "Tweets" else "official_reply")

    for query in SEARCH_QUERIES:
        tweets = await client.search_tweet(query, "Latest", count=min(count, 20))
        for tweet in tweets:
            created = tweet.created_at_datetime
            if created.tzinfo is None:
                created = created.replace(tzinfo=timezone.utc)
            if created >= cutoff:
                records[str(tweet.id)] = tweet_to_record(tweet, "search")

    return list(records.values())


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cookie-file", type=Path, default=DEFAULT_COOKIE_FILE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--hours", type=int, default=24 * 7)
    parser.add_argument("--count", type=int, default=40)
    parser.add_argument("--cadence-hours", type=int, default=12)
    parser.add_argument("--refresh-login", action="store_true")
    parser.add_argument("--login-timeout-sec", type=int, default=300)
    parser.add_argument("--seed-only", action="store_true")
    args = parser.parse_args()

    if args.refresh_login:
        await refresh_x_cookies(args.cookie_file.expanduser(), args.login_timeout_sec)

    records = SEED_RECORDS if args.seed_only else await fetch_records(args.cookie_file.expanduser(), args.hours, args.count)
    payload = build_payload(records, args.cadence_hours)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {args.output} with {len(payload['evidence'])} evidence items.")


if __name__ == "__main__":
    asyncio.run(main())
