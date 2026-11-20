# Photo Stamp Telegram Bot

Send a photo + time + location → get the photo back with a stamp in the top‑right
corner (white text, same style as an iPhone timestamp camera):

```
Network:Jul 22, 2025 at 11:14:23 AM EDT
Local:Jul 22, 2025 at 11:14:23 AM EDT
N 40° 50' 41.764", W 73° 55' 21.163"
Cross Bronx Expy
New York NY 10452
United States
```

* **Coordinates given** → address is looked up automatically (OpenStreetMap) and the
  coordinates are printed in degrees/minutes/seconds.
* **Address given** → coordinates are **not** printed, only the address.
* The **time zone** (EDT/EST, PDT, JST…) is detected from the location, including daylight saving.

## How to use (in Telegram)

1. Send a photo (send as *file* to keep full quality).
2. In the caption or the next message, send the time on the first line and the location on the next:

```
Jul 22, 2025 11:14:23 AM
40.844934, -73.922545
```
```
Jul 22, 2025 11:14:23 AM
Cross Bronx Expy, Bronx, NY 10452
```

Coordinates can be decimal (`40.844934, -73.922545`) or DMS (`N 40° 50' 41.764", W 73° 55' 21.163"`).
Use `now` as the time for the current local time.

## Run

1. Create a bot with [@BotFather](https://t.me/BotFather) and copy the token.
2. Install and start:

```bash
pip install -r requirements.txt
export TELEGRAM_BOT_TOKEN="123456:ABC..."
python bot.py
```

Optional: `GEOCODER_USER_AGENT` (name sent to OpenStreetMap Nominatim), `STAMP_FONT` (path to another font file).

Font: Inter (SIL Open Font License, see `fonts/LICENSE-Inter.txt`) — closest free match to Apple's SF font in the sample.
