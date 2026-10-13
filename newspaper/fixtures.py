"""Packaged Hungarian fixture used to prove the A4 template."""

from copy import deepcopy


def fixture_edition() -> dict:
    return {
        "nickname": "Győző",
        "motto": "",
        "dateline": "Vol. 1 · 2026. szeptember 21. · hétfő · Budapest · AS OF 06:30",
        "weekend": True,
        "show_sun": True,
        "greeting": "Yippie, weekend! You earned it!",
        "news": [
            {
                "kind": "hed",
                "headline": "Megszentségteleníthetetlenségeskedéseitekért",
            },
            {
                "headline": "A kutatók „sűrű ködnek” nevezték a jelenséget",
                "publisher": "Telex",
                "time": "05:12",
                "dek": "A jelentés űrt hagyott a korábbi magyarázatok helyén.",
            },
            {
                "headline": "Hídnyitás a pesti rakparton",
                "publisher": "444",
                "time": "21:40",
            },
        ],
        "today": [
            {
                "time": "09:00",
                "title": "Csapatmegbeszélés",
                "place": "Iroda",
            },
            {
                "time": "bármikor",
                "title": "Nyitott feladat: iratok rendezése",
            },
        ],
        "this_week": [
            {"day": "Kedd", "text": "Fogorvos 14:00"},
            {"day": "Szerda", "text": "Színház a Vígszínházban"},
        ],
        "weather": {
            "high": "22°",
            "low": "11°",
            "hl_label": "Max / Min",
            "summary": "Derült, élénk északnyugati szél. Estére felhősödik.",
            "outlook": [
                {"day": "Ke", "text": "Napos", "temps": "23 / 12"},
                {"day": "Sze", "text": "Felhős", "temps": "20 / 11"},
                {"day": "Cs", "text": "Zápor", "temps": "18 / 10"},
                {"day": "P", "text": "Szeles", "temps": "17 / 9"},
            ],
        },
        "prep": ["Holnap 07:40: vonat Szegedre, jegyet előre venni."],
        "due": ["Szerződés átnézése csütörtökig."],
        "overdue": ["3 napja lejárt: adóbevallás másolat."],
        "daily_item": "Könnyű sudoku a hátlapon, ma a napi tétel helyén.",
        "almanac": {
            "lines": [
                {"label": "Nap", "text": "Kel 06:28, nyugszik 18:41"},
                {"label": "Hold", "text": "Fogyó hold"},
                {"label": "Névnap", "text": "Máté, Ildikó"},
                {"label": "Árfolyam", "text": "EUR 395, USD 362, CHF 421"},
            ]
        },
    }


def edition_with(**overrides) -> dict:
    data = deepcopy(fixture_edition())
    data.update(overrides)
    return data
