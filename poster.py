#!/usr/bin/env python3
"""LESH autopost: publishes approved, due reels to Instagram and pulls their stats.

Modes:
  post        publish every approved post whose time has come (default)
  dry-run     do everything except the final publish (checks the token, the link and Instagram's processing)
  (schedule.json entries with "kind": "story" go out as stories: an image or a video, no caption)
  replies     post the comment replies Saif approved in replies.json
  comments    collect comments on our reels into comments/inbox.json (insights runs this too)
  insights    save the numbers for every posted reel into stats/YYYY-MM-DD.json
  refresh     extend the token's life (only Instagram login tokens; the business portfolio token never expires)
  check       print the account the token belongs to and the publishing limit

The token comes from the repo secret IG_TOKEN.
  Business portfolio token (starts with EAA, never expires): calls go to graph.facebook.com and the Instagram
  account id comes from IG_USER_ID, or is found through the Facebook Page the account is linked to.
  Instagram login token (starts with IG): calls go to graph.instagram.com; after the first refresh the newest
  token lives in token.enc, encrypted with IG_TOKEN as the key.
"""
import json, os, re, subprocess, sys, time, datetime as dt, urllib.parse, urllib.request, urllib.error

API = "https://graph.instagram.com/v24.0"
FB = False
REPO_RAW = os.environ.get("MEDIA_BASE", "https://revora-ae.github.io/lesh-autopost/media/")
HERE = os.path.dirname(os.path.abspath(__file__))
UTC = dt.timezone.utc


def now():
    return dt.datetime.now(UTC)


def log(*a):
    print(now().strftime("%H:%M:%S"), *a, flush=True)


def token():
    secret = os.environ.get("IG_TOKEN", "").strip()
    if not secret:
        print("IG_TOKEN is not set yet (repo Settings > Secrets and variables > Actions). Nothing to do.")
        sys.exit(0)
    enc = os.path.join(HERE, "token.enc")
    if os.path.exists(enc):
        try:
            out = subprocess.run(["openssl", "enc", "-d", "-aes-256-cbc", "-pbkdf2", "-a", "-A", "-in", enc, "-pass", "env:IG_TOKEN"],
                                 capture_output=True, text=True, check=True).stdout.strip()
            if out:
                return out
        except subprocess.CalledProcessError:
            log("token.enc could not be read, using IG_TOKEN")
    return secret


TOKEN = None


def call(method, path, params=None, timeout=60):
    params = dict(params or {})
    url = path if path.startswith("http") else API + path
    data = None
    headers = {"Authorization": "Bearer " + TOKEN}
    if method == "GET":
        if params:
            url += ("&" if "?" in url else "?") + urllib.parse.urlencode(params)
    else:
        data = urllib.parse.urlencode(params).encode()
    req = urllib.request.Request(url, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode() or "{}")
    except urllib.error.HTTPError as e:
        body = e.read().decode(errors="replace")
        raise RuntimeError("%s %s -> %s %s" % (method, path, e.code, body[:600]))


def load(name, default):
    p = os.path.join(HERE, name)
    return json.load(open(p)) if os.path.exists(p) else default


def save(name, obj):
    with open(os.path.join(HERE, name), "w") as f:
        json.dump(obj, f, indent=2, ensure_ascii=False)
        f.write("\n")


def parse_time(s):
    return dt.datetime.fromisoformat(s.replace("Z", "+00:00")).astimezone(UTC)


def me():
    if not FB:
        return call("GET", "/me", {"fields": "user_id,username,account_type"})
    uid = os.environ.get("IG_USER_ID", "").strip() or "17841441425903061"  # @leshexplained
    if not uid:
        pages = call("GET", "/me/accounts", {"fields": "name,instagram_business_account{id,username}"}).get("data", [])
        for pg in pages:
            ig = pg.get("instagram_business_account")
            if ig:
                uid = ig["id"]
                break
    if not uid:
        sys.exit("No Instagram account id. Set the repo variable IG_USER_ID.")
    info = call("GET", "/" + uid, {"fields": "id,username,followers_count,media_count"})
    return {"user_id": uid, "username": info.get("username"), "account_type": "business portfolio token"}


def container(uid, post):
    if post.get("kind") == "story":   # a story: one image or one video, no caption, no stickers
        key = "video_url" if post["file"].endswith(".mp4") else "image_url"
        return call("POST", "/%s/media" % uid, {"media_type": "STORIES", key: REPO_RAW + post["file"]})["id"]
    p = {
        "media_type": "REELS",
        "video_url": REPO_RAW + post["file"],
        "caption": post["caption"],
        "share_to_feed": "true",
    }
    if post.get("cover"):   # designed cover for the profile grid (wins over thumb_offset)
        p["cover_url"] = REPO_RAW + post["cover"]
    elif post.get("thumb_offset_ms") is not None:
        p["thumb_offset"] = str(int(post["thumb_offset_ms"]))
    if post.get("ai_label", True):
        p["is_ai_generated"] = "true"
    if post.get("trial"):   # trial reel: shown to non followers first. "SS_PERFORMANCE" = Instagram shares it to followers if it does well, "MANUAL" = share it in the app
        p["trial_params"] = json.dumps({"graduation_strategy": post["trial"]})
    try:
        return call("POST", "/%s/media" % uid, p)["id"]
    except RuntimeError as e:
        if "is_ai_generated" in p and "is_ai_generated" in str(e):
            log("WARNING: Instagram refused is_ai_generated, retrying without it and saying so in the caption.", e)
            p.pop("is_ai_generated")
            p["caption"] = p["caption"].rstrip() + "\n\nAI voiceover."
            return call("POST", "/%s/media" % uid, p)["id"]
        raise


def wait_ready(cid, limit_s=900):
    t0 = time.time()
    while time.time() - t0 < limit_s:
        st = call("GET", "/" + cid, {"fields": "status_code,status"})
        code = st.get("status_code")
        log("container", cid, code, st.get("status", ""))
        if code == "FINISHED":
            return True
        if code in ("ERROR", "EXPIRED"):
            raise RuntimeError("container %s failed: %s" % (cid, st))
        time.sleep(15)
    raise RuntimeError("container %s still processing after %ds" % (cid, limit_s))


def already_live(uid, post):
    """Guard against a double post: is a reel with the same first caption line already on the account?"""
    first = post["caption"].strip().splitlines()[0].strip()
    media = call("GET", "/%s/media" % uid, {"fields": "id,caption,timestamp,permalink", "limit": 10}).get("data", [])
    for m in media:
        if (m.get("caption") or "").strip().splitlines()[:1] == [first]:
            return m
    return None


def git_pull():
    subprocess.run(["git", "pull", "--rebase", "--quiet"], cwd=HERE)


def do_post(dry=False):
    git_pull()
    sched = load("schedule.json", {"posts": []})["posts"]
    posted = load("posted.json", {})
    info = me()
    uid = info["user_id"]
    log("account @%s (%s)" % (info.get("username"), info.get("account_type")))
    lead = dt.timedelta(minutes=150)   # a run that starts up to 2.5 hours early gets the post ready, then waits for the exact minute
    changed = False
    tested = set()
    for post in sorted(sched, key=lambda p: p["publish_at"]):
        if post["id"] in posted or (not post.get("approved") and not dry):   # a dry run never publishes, so it may test unapproved posts
            continue
        if dry and post.get("kind", "reel") in tested:
            continue
        when = parse_time(post["publish_at"])
        if not dry and now() < when - lead:
            continue
        if not dry and now() > when + dt.timedelta(hours=12):
            log("SKIP", post["id"], "is more than 12 hours late; it needs a new time")
            continue
        live = already_live(uid, post) if post.get("kind") != "story" else None
        if live and not dry:
            log("already on Instagram:", post["id"], live.get("permalink"))
            posted[post["id"]] = {"media_id": live["id"], "permalink": live.get("permalink"), "published_at": live.get("timestamp"), "note": "found live"}
            changed = True
            continue
        log("preparing", post["id"], "for", when.isoformat())
        cid = container(uid, post)
        wait_ready(cid)
        if dry:
            log("DRY RUN ok:", post["id"], "is ready to publish (container", cid, "will expire unused)")
            tested.add(post.get("kind", "reel"))   # one reel and one story are enough to prove the whole path
            continue
        while now() < when:
            time.sleep(min(30, max(1, (when - now()).total_seconds())))
        res = call("POST", "/%s/media_publish" % uid, {"creation_id": cid})
        mid = res["id"]
        info2 = call("GET", "/" + mid, {"fields": "permalink,timestamp"})
        posted[post["id"]] = {"media_id": mid, "permalink": info2.get("permalink"), "published_at": info2.get("timestamp"), "trial": post.get("trial"), "topic": post.get("topic", post["id"]), "variant": post.get("variant")}
        log("PUBLISHED", post["id"], info2.get("permalink"))
        save("posted.json", posted)
        changed = True
    if changed:
        save("posted.json", posted)
    return changed


METRICS = ["views", "reach", "likes", "comments", "shares", "saved", "total_interactions", "ig_reels_avg_watch_time", "ig_reels_video_view_total_time"]
STORY_METRICS = ["reach", "views", "replies", "shares", "total_interactions"]


def ratio(a, b):
    return round(a / b, 4) if isinstance(a, (int, float)) and isinstance(b, (int, float)) and b else None


def do_insights():
    posted = load("posted.json", {})
    sched = {p["id"]: p for p in load("schedule.json", {"posts": []})["posts"]}
    day = now().strftime("%Y-%m-%d")
    out = {"taken_at": now().isoformat(), "reels": {}, "stories": {}}
    for pid, p in posted.items():
        story = sched.get(pid, {}).get("kind") == "story"
        row = {"media_id": p["media_id"], "permalink": p.get("permalink")}
        for m in (STORY_METRICS if story else METRICS):
            try:
                r = call("GET", "/%s/insights" % p["media_id"], {"metric": m})
                row[m] = r["data"][0]["values"][0]["value"] if "values" in r["data"][0] else r["data"][0].get("total_value", {}).get("value")
            except Exception:  # a metric can be unavailable for a fresh reel, and story numbers vanish after 24 hours
                row[m] = None
        if story:
            if any(row.get(m) is not None for m in STORY_METRICS):
                out["stories"][pid] = row
            continue
        try:
            row.update(call("GET", "/" + p["media_id"], {"fields": "like_count,comments_count"}))
        except Exception:
            pass
        # the three signals Instagram ranks reels on, as ratios we can compare between reels
        dur = sched.get(pid, {}).get("duration_s")
        row["sends_per_reach"] = ratio(row.get("shares"), row.get("reach"))
        row["likes_per_reach"] = ratio(row.get("likes"), row.get("reach"))
        row["saves_per_reach"] = ratio(row.get("saved"), row.get("reach"))
        aw = row.get("ig_reels_avg_watch_time")
        row["avg_watch_s"] = round(aw / 1000, 2) if isinstance(aw, (int, float)) else None
        row["watch_pct"] = ratio(row["avg_watch_s"], dur)
        out["reels"][pid] = row
    try:
        out["account"] = call("GET", "/" + me()["user_id"], {"fields": "followers_count,follows_count,media_count"})
    except Exception as e:
        out["account"] = {"error": str(e)[:200]}
    os.makedirs(os.path.join(HERE, "stats"), exist_ok=True)
    save("stats/%s.json" % day, out)
    log("stats saved for", len(out["reels"]), "reels and", len(out["stories"]), "stories")


QWORDS = re.compile(r"\?|؟|\b(why|how|what|who|when|where|which|lesh|explain|do|make|next|part 2|cover)\b|ليش|ليه|كيف|وش|شو|ايش|إيش|متى|وين|مين|اشرح|سوو|الجزء", re.I)


def do_comments():
    """Every comment on our reels goes into comments/inbox.json (no usernames: the repo is public).
    Questions are flagged; Claude turns the best ones into reply drafts and new reel ideas."""
    posted = load("posted.json", {})
    sched = {p["id"]: p for p in load("schedule.json", {"posts": []})["posts"]}
    inbox = load("comments/inbox.json", {})
    new = 0
    for pid, p in posted.items():
        if sched.get(pid, {}).get("kind") == "story":
            continue
        try:
            data = call("GET", "/%s/comments" % p["media_id"], {"fields": "id,text,timestamp,like_count", "limit": 100}).get("data", [])
        except Exception as e:
            log("comments unavailable for", pid, str(e)[:160])
            continue
        for c in data:
            if c["id"] in inbox:
                inbox[c["id"]]["like_count"] = c.get("like_count", 0)
                continue
            inbox[c["id"]] = {"reel": pid, "text": c.get("text", ""), "timestamp": c.get("timestamp"), "like_count": c.get("like_count", 0),
                              "question": bool(QWORDS.search(c.get("text", ""))), "status": "new"}
            new += 1
    os.makedirs(os.path.join(HERE, "comments"), exist_ok=True)
    save("comments/inbox.json", inbox)
    log("comments: %d new, %d in the inbox, %d open questions" % (new, len(inbox), sum(1 for c in inbox.values() if c["question"] and c["status"] == "new")))


def do_replies():
    """Post the comment replies Saif approved: replies.json entries with approved true and no sent_at.
    Claude drafts them with approved false; only Saif's yes flips them."""
    replies = load("replies.json", {"replies": []})
    n = 0
    for r in replies["replies"]:
        if not r.get("approved") or r.get("sent_at"):
            continue
        try:
            res = call("POST", "/%s/replies" % r["comment_id"], {"message": r["message"]})
            r["sent_at"] = now().isoformat(); r["reply_id"] = res.get("id")
            n += 1
            log("replied to", r["comment_id"])
        except Exception as e:
            r["error"] = str(e)[:200]
            log("reply failed for", r["comment_id"], str(e)[:200])
    save("replies.json", replies)
    log("replies sent:", n)


def do_refresh():
    if FB:
        log("business portfolio token never expires; nothing to refresh")
        return
    r = call("GET", "https://graph.instagram.com/refresh_access_token", {"grant_type": "ig_refresh_token", "access_token": TOKEN})
    new = r["access_token"]
    p = subprocess.run(["openssl", "enc", "-aes-256-cbc", "-pbkdf2", "-a", "-A", "-salt", "-pass", "env:IG_TOKEN"],
                       input=new, capture_output=True, text=True, check=True)
    with open(os.path.join(HERE, "token.enc"), "w") as f:
        f.write(p.stdout.strip() + "\n")
    log("token refreshed, valid for about", int(r.get("expires_in", 0)) // 86400, "days")


def main():
    global TOKEN
    mode = sys.argv[1] if len(sys.argv) > 1 else "post"
    TOKEN = token()
    global API, FB
    if TOKEN.startswith("EA"):
        FB = True
        API = "https://graph.facebook.com/v24.0"
    if mode == "check":
        print(json.dumps(me(), indent=2))
        info = me()
        print(json.dumps(call("GET", "/%s/content_publishing_limit" % info["user_id"], {"fields": "quota_usage,config"}), indent=2))
    elif mode == "dry-run":
        do_post(dry=True)
    elif mode == "post":
        do_post()
    elif mode == "insights":
        do_insights()
        do_comments()
    elif mode == "comments":
        do_comments()
    elif mode == "replies":
        do_replies()
    elif mode == "refresh":
        do_refresh()
    else:
        sys.exit("unknown mode " + mode)


if __name__ == "__main__":
    main()
