"""Small, non-authoritative external-news safety check for football fixtures.

Headlines can flag a late lineup, injury, suspension or postponement. They are
never treated as confirmed facts and only pause a virtual decision for review.
"""

from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from urllib.parse import urlencode
from xml.etree import ElementTree

import requests


class ExternalNewsChecker:
    RSS_URL = "https://news.google.com/rss/search"
    KEYWORDS = {
        "form": ("form guide", "recent form", "last five", "last 5"),
        "injury": ("injur", "fitness", "doubt", "absence"),
        "lineup": ("lineup", "line-up", "starting xi", "team news"),
        "suspension": ("suspend", "banned", "ban "),
        "schedule": ("postpon", "cancel", "abandon"),
    }

    def __init__(self, session=None):
        self.session = session or requests.Session()

    def check(self, home, away, missing_data=None):
        """Search recent match information when the normal data is incomplete.

        Search results are evidence to review, not facts to feed straight into
        the model.  This prevents a headline or rumour from becoming a bet.
        """

        missing = set(missing_data or [])
        terms = ["football"]

        if {"recent_form", "home_away_form", "h2h"} & missing:
            terms.append("recent form")
        if {"injuries", "lineups"} & missing:
            terms.extend(["injury", "lineup", "suspension"])
        if "schedule_load" in missing:
            terms.append("schedule")
        if "odds" in missing:
            terms.append("match preview")

        # A wider query is useful even when the source data is complete: late
        # team news can invalidate a previously safe-looking recommendation.
        query = f'"{home}" "{away}" ' + " ".join(dict.fromkeys(terms))
        try:
            response = self.session.get(
                self.RSS_URL + "?" + urlencode({"q": query, "hl": "en"}),
                timeout=12,
            )
            response.raise_for_status()
            root = ElementTree.fromstring(response.content)
        except (requests.RequestException, ElementTree.ParseError):
            return {"status": "unavailable", "review_required": False, "signals": []}

        signals = []
        freshness_limit = datetime.now(timezone.utc) - timedelta(days=10)
        for item in root.findall("./channel/item")[:8]:
            title = (item.findtext("title") or "").strip()
            text = title.casefold()
            labels = [
                label for label, words in self.KEYWORDS.items()
                if any(word in text for word in words)
            ]
            if not labels:
                continue
            published_at = (item.findtext("pubDate") or "").strip()
            try:
                published = parsedate_to_datetime(published_at)
                if published.tzinfo is None:
                    published = published.replace(tzinfo=timezone.utc)
                if published.astimezone(timezone.utc) < freshness_limit:
                    continue
            except (TypeError, ValueError, IndexError):
                # An undated headline is useful to display, but cannot block
                # a virtual decision by itself.
                continue
            source = item.find("source")
            signals.append({
                "title": title[:300],
                "url": (item.findtext("link") or "").strip(),
                "publisher": (source.text or "Внешний источник").strip() if source is not None else "Внешний источник",
                "published_at": published_at,
                "topics": labels,
            })
        return {
            "status": "signals" if signals else "clear",
            "checked_at": datetime.now(timezone.utc).isoformat(),
            "searched_for": sorted(missing),
            "review_required": bool(signals),
            "signals": signals[:4],
        }
