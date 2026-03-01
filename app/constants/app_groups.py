APP_GROUPS: dict[str, list[tuple[str, str]]] = {
    "Horoscope & Astrology": [
        ("Nebula: Horoscope & Astrology", "1459969523"),
        ("Co-Star Personalized Astrology", "1264782561"),
        ("The Pattern", "1071085727"),
        ("CHANI: Your Astrology Guide", "1532791252"),
    ],
    "Video Streaming": [
        ("YouTube", "544007664"),
        ("TikTok", "835599320"),
        ("Vimeo", "425194759"),
    ],
    "Social Media": [
        ("Instagram", "389801252"),
        ("Snapchat", "447188370"),
        ("Pinterest", "429047995"),
    ],
    "Messaging": [
        ("WhatsApp Messenger", "310633997"),
        ("Telegram Messenger", "686449807"),
        ("Messenger", "454638411"),
    ],
    "Music Streaming": [
        ("Spotify", "324684580"),
        ("Apple Music", "1108187390"),
        ("YouTube Music", "1017492454"),
    ],
    "Fitness": [
        ("Strava", "426826309"),
        ("Nike Run Club", "387771637"),
    ],
    "Meditation & Wellness": [
        ("Headspace", "493145008"),
        ("Calm", "571800810"),
        ("Insight Timer", "337472899"),
    ],
    "Food Delivery": [
        ("DoorDash", "719972451"),
        ("Uber Eats", "1058959277"),
        ("Grubhub", "302920553"),
    ],
    "Ride Sharing": [
        ("Uber", "368677368"),
        ("Lyft", "529379082"),
    ],
    "Language Learning": [
        ("Duolingo", "570060128"),
        ("Babbel", "829587759"),
    ],
}

APP_NAMES: dict[str, str] = {
    app_id: name for group in APP_GROUPS.values() for name, app_id in group
}
