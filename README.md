# LESH autopost

Posts the approved LESH? reels to Instagram (@leshexplained) at their scheduled times, then saves their numbers every morning.

- `schedule.json`: every reel, its caption, its cover frame and its time. Only posts with `"approved": true` go out.
- `media/`: the finished videos. Instagram fetches each one from its public link here.
- `posted.json`: what went out, with links. `stats/`: the daily numbers.
- `poster.py`: the poster. `.github/workflows/post.yml`: runs it every 15 minutes from 8 am to midnight UAE time, saves stats at 9:17 am, extends the token every Monday.
- Secret: `IG_TOKEN` (Settings > Secrets and variables > Actions). After the first Monday the newest token is kept in `token.enc`, encrypted with the secret.

Run it by hand: Actions > LESH autopost > Run workflow, mode `check` (is the token working) or `dry-run` (prepare the next reel without publishing).
