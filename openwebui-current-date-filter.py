"""
title: Current Date Anchor
author: local
version: 1.1
description: Injects today's real date into every chat so local models (whose
    training cutoff predates the current date) don't default to stale
    assumptions about "current" or "latest" when reasoning over search
    results or answering directly. Enable as a GLOBAL filter so it applies
    to every model behind the router.

    v1.1: this app's web search has no recency/freshness filter on any
    backend (checked DuckDuckGo, Tavily, Brave, Serper, Kagi — none pass a
    date-range parameter), so old, well-ranked "best of" and buying-guide
    content routinely outranks current information. Knowing today's date
    doesn't stop a model from taking such a page at face value. Added an
    explicit instruction to treat "best/top/latest X" content as
    potentially superseded and to check for discontinuation before citing
    it as current, since that's the specific failure this was missing.
"""

from datetime import datetime


class Filter:
    def inlet(self, body: dict, __user__: dict = None) -> dict:
        now = datetime.now()
        note = (
            f"[System note: today's real-world date is {now.strftime('%A, %B %d, %Y')}. "
            f"Your training data has a cutoff before this date. Do not assume any "
            f"information, model, or event you know of is 'the latest' — newer things "
            f"exist that you have not seen. Trust web search results and the user over "
            f"your own training-era assumptions about what is current. "
            f"IMPORTANT: this app's web search has no way to filter by recency, so "
            f"top-ranked results are often old 'best of'/buying-guide pages that "
            f"describe a product line as current when it may since have been "
            f"discontinued or superseded. Before presenting a search result as the "
            f"current/best option — especially for products, rankings, versions, or "
            f"prices — actively check whether it has been superseded, and say so if "
            f"you're not sure, rather than presenting an old top result as today's answer.]"
        )

        messages = body.get("messages", [])
        if messages and messages[0].get("role") == "system":
            messages[0]["content"] = note + "\n\n" + messages[0]["content"]
        else:
            messages.insert(0, {"role": "system", "content": note})
        body["messages"] = messages
        return body
