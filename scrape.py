#!/usr/bin/env python3
"""
scrape v1 - Personal SEO Rank Checker
Pure scraper — no API key needed. Just Python.

Requirements:
    pip install requests beautifulsoup4 colorama python-dotenv
"""

import argparse
import csv
import json
import os
import random
import sys
import time
from datetime import datetime
from urllib.parse import urlparse, urlencode

try:
    import requests
    from bs4 import BeautifulSoup
except ImportError:
    print("Missing: pip install requests beautifulsoup4"); sys.exit(1)

try:
    from colorama import init, Fore, Style
    init(autoreset=True)
    HAS_COLOR = True
except ImportError:
    HAS_COLOR = False
    class Fore:
        GREEN = RED = YELLOW = CYAN = MAGENTA = WHITE = RESET = ""
    class Style:
        BRIGHT = DIM = RESET_ALL = ""

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

HISTORY_FILE = "checkmyweb_history.json"

BANNER = r"""
  _____ _               _    __  __      __          __  _
 / ____| |             | |  |  \/  |     \ \        / / | |
| |    | |__   ___  ___| | _| \  / |_   _ \ \  /\  / /__| |__
| |    | '_ \ / _ \/ __| |/ / |\/| | | | | \ \/  \/ / _ \ '_ \
| |____| | | |  __/ (__|   <| |  | | |_| |  \  /\  /  __/ |_) |
 \_____|_| |_|\___|\___|_|\_\_|  |_|\__, |   \/  \/ \___|_.__/
                                     __/ |
  SEO Rank Checker                  |___/   v6.0 (no API key)
"""

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
]


# ── Helpers ───────────────────────────────────────────────────────────────────

def c(color, text):
    return f"{color}{text}{Style.RESET_ALL}" if HAS_COLOR else text

def normalize_domain(url):
    url = url.strip().lower()
    if not url.startswith("http"):
        url = "https://" + url
    parsed = urlparse(url)
    domain = parsed.netloc or parsed.path
    return domain.replace("www.", "").rstrip("/")

def domain_matches(result_url, target):
    try:
        d = normalize_domain(result_url)
        base = d.split("/")[0]
        return base == target or base.endswith("." + target) or target.endswith("." + base)
    except Exception:
        return False

def truncate(s, n):
    return s[:n] + "…" if len(s) > n else s

def load_keywords(path):
    if not os.path.exists(path):
        print(c(Fore.RED, f"  [!] File not found: {path}")); sys.exit(1)
    with open(path, encoding="utf-8") as f:
        return [l.strip() for l in f if l.strip() and not l.startswith("#")]

def trend_arrow(current, previous):
    if previous is None:
        return c(Fore.CYAN, "  (new)")
    if current is None and previous is not None:
        return c(Fore.RED, f"  ▼ dropped out (was #{previous})")
    diff = previous - current
    if diff > 0:
        return c(Fore.GREEN, f"  ▲ +{diff} from #{previous}")
    elif diff < 0:
        return c(Fore.RED, f"  ▼ {abs(diff)} from #{previous}")
    else:
        return c(Style.DIM, f"  — no change (#{previous})")

def spark(ranks):
    bars  = "▁▂▃▄▅▆▇█"
    valid = [r for r in ranks if r is not None]
    if not valid:
        return c(Style.DIM, "no data")
    if len(valid) == 1:
        return c(Style.DIM, f"#{valid[0]} (1 snapshot)")
    lo, hi = min(valid), max(valid)
    result = []
    for r in ranks:
        if r is None:
            result.append(c(Style.DIM, "·"))
        else:
            idx = 7 - int((r - lo) / (hi - lo) * 7) if hi != lo else 7
            result.append(c(Fore.GREEN if r == min(valid) else Fore.CYAN, bars[idx]))
    return "".join(result)


# ── History ───────────────────────────────────────────────────────────────────

def load_history():
    if not os.path.exists(HISTORY_FILE):
        return {}
    with open(HISTORY_FILE, encoding="utf-8") as f:
        try: return json.load(f)
        except: return {}

def save_history(history):
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(history, f, indent=2)

def record_snapshot(history, site, keyword, rank, results):
    key = f"{site}||{keyword}"
    if key not in history:
        history[key] = {"site": site, "keyword": keyword, "snapshots": []}
    history[key]["snapshots"].append({
        "date":  datetime.now().strftime("%Y-%m-%d %H:%M"),
        "rank":  rank,
        "top3":  [{"rank": r["rank"], "url": r["url"]} for r in results[:3]],
    })

def get_last_rank(history, site, keyword):
    key   = f"{site}||{keyword}"
    snaps = history.get(key, {}).get("snapshots", [])
    return snaps[-1]["rank"] if snaps else None


# ── Scraper ───────────────────────────────────────────────────────────────────

def make_session():
    session = requests.Session()
    ua = random.choice(USER_AGENTS)
    session.headers.update({
        "User-Agent":                ua,
        "Accept":                    "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language":           "en-US,en;q=0.9",
        "DNT":                       "1",
        "Connection":                "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Referer":                   "https://www.google.com/",
    })
    # Pre-set consent cookies — prevents Google consent redirect page
    for domain in [".google.com", ".google.com.ph"]:
        session.cookies.set("CONSENT", "YES+cb.20210720-07-p0.en+FX+410", domain=domain)
        session.cookies.set("SOCS",    "CAESEwgDEgk0OTc5NTk1OTIaAmVuIAEaBgiA7pinBg", domain=domain)
    return session

def is_blocked(html):
    indicators = ["our systems have detected unusual traffic", "captcha", "g-recaptcha", "sorry/index"]
    return any(i in html.lower() for i in indicators)

def parse_google_html(html):
    soup    = BeautifulSoup(html, "html.parser")
    results = []
    seen    = set()

    SKIP = ["google.", "youtube.com", "#", "javascript"]

    def is_valid(href):
        if not href or not href.startswith("http"): return False
        return not any(s in href for s in SKIP)

    # Pattern 1: <div class="g"> blocks — main organic results
    for div in soup.select("div.g"):
        a = div.select_one("a[href]")
        if not a: continue
        href = a.get("href", "")
        if not is_valid(href) or href in seen: continue
        title_el = div.select_one("h3")
        title    = title_el.get_text(strip=True) if title_el else ""
        disp_el  = div.select_one("cite")
        disp     = disp_el.get_text(strip=True) if disp_el else href
        seen.add(href)
        results.append({"url": href, "title": title, "displayed": disp})

    # Pattern 2: data-sokoban-container (newer Google layout)
    if len(results) < 3:
        for div in soup.select("div[data-sokoban-container], div.tF2Cxc, div.yuRUbf"):
            a = div.select_one("a[href]")
            if not a: continue
            href = a.get("href", "")
            if not is_valid(href) or href in seen: continue
            title_el = div.select_one("h3")
            title    = title_el.get_text(strip=True) if title_el else ""
            disp_el  = div.select_one("cite")
            disp     = disp_el.get_text(strip=True) if disp_el else href
            seen.add(href)
            results.append({"url": href, "title": title, "displayed": disp})

    # Pattern 3: /url?q= fallback (older Google format)
    if len(results) < 3:
        for a in soup.select("a[href]"):
            href = a.get("href", "")
            if href.startswith("/url?q="):
                url = href[7:].split("&")[0]
                if is_valid(url) and url not in seen:
                    seen.add(url)
                    title = a.get_text(strip=True)[:80]
                    results.append({"url": url, "title": title, "displayed": url})

    # Pattern 4: any plain http link with an h3 nearby (last resort)
    if len(results) < 3:
        for a in soup.select("a[href]"):
            href = a.get("href", "")
            if not is_valid(href) or href in seen: continue
            parent = a.parent
            h3 = parent.find("h3") if parent else None
            if h3:
                seen.add(href)
                disp = href.replace("https://","").replace("http://","").split("/")[0]
                results.append({"url": href, "title": h3.get_text(strip=True), "displayed": disp})

    return results

def scrape_google(keyword, top_n, session, country="ph"):
    all_results = []
    pages       = 1 if top_n <= 10 else 2

    # Always use google.com with gl= country param — more reliable than country TLDs
    for page in range(pages):
        params = {
            "q":     keyword,
            "start":  page * 10,
            "num":   10,
            "hl":    "en",
            "gl":    country,
            "pws":   "0",   # disable personalization
            "nfpr":  "1",   # disable auto-correction
        }
        url = f"https://www.google.com/search?{urlencode(params)}"

        try:
            resp = session.get(url, timeout=15, stream=False)
            resp.encoding = "utf-8"
        except requests.exceptions.Timeout:
            raise RuntimeError("Request timed out")
        except requests.exceptions.ConnectionError:
            raise RuntimeError("Connection failed — check your internet")

        if resp.status_code == 429:
            raise RuntimeError("Google rate-limited you (429) — increase --delay or wait a few minutes")
        if resp.status_code != 200:
            raise RuntimeError(f"HTTP {resp.status_code} from Google")
        if is_blocked(resp.text):
            raise RuntimeError("Google showed a CAPTCHA — slow down or wait a few minutes")

        # Debug: save raw HTML so user can inspect what Google returned
        debug_path = f"debug_page{page+1}.html"
        try:
            html_text = resp.content.decode("utf-8", errors="replace")
        except Exception:
            html_text = resp.text
        with open(debug_path, "w", encoding="utf-8") as df:
            df.write(html_text)

        page_results = parse_google_html(resp.text)
        for i, r in enumerate(page_results):
            all_results.append({
                "rank":          page * 10 + i + 1,
                "url":           r["url"],
                "title":         r["title"],
                "displayed_url": r["displayed"],
            })

        if page < pages - 1:
            time.sleep(random.uniform(2.0, 3.5))

    return all_results[:top_n]


# ── Feature 1: Alert ──────────────────────────────────────────────────────────

def check_alert(keyword, current, prev, threshold):
    if threshold is None or prev is None: return None
    if current is None:
        return c(Fore.RED + Style.BRIGHT, f"  🚨 ALERT: \"{keyword}\" dropped OUT of results (was #{prev})")
    drop = current - prev
    if drop >= threshold:
        return c(Fore.RED + Style.BRIGHT, f"  🚨 ALERT: \"{keyword}\" dropped {drop} positions (#{prev} → #{current})")
    return None


# ── Feature 2: Competitors ────────────────────────────────────────────────────

def find_competitors(results, competitors):
    found = {}
    for r in results:
        for comp in competitors:
            if domain_matches(r["url"], comp) and comp not in found:
                found[comp] = r["rank"]
    return found


# ── Feature 3: Trend report ───────────────────────────────────────────────────

def classify_trend(ranks):
    valid = [r for r in ranks if r is not None]
    if len(valid) < 2: return "insufficient"
    n      = len(valid)
    mean_x = (n - 1) / 2
    mean_y = sum(valid) / n
    num    = sum((i - mean_x) * (valid[i] - mean_y) for i in range(n))
    den    = sum((i - mean_x) ** 2 for i in range(n))
    slope  = num / den if den != 0 else 0
    swing  = max(valid) - min(valid)
    if swing >= 10:   return "volatile"
    if slope < -1.0:  return "rising"
    if slope > 1.0:   return "falling"
    return "stable"

def print_trend_report(history, site):
    entries = {k: v for k, v in history.items() if v["site"] == site}
    if not entries:
        print(c(Fore.YELLOW, f"\n  No history for {site}. Run searches with --save first.\n"))
        return

    rising, falling, volatile, stable, new_kws = [], [], [], [], []
    for key, entry in entries.items():
        kw    = entry["keyword"]
        ranks = [s["rank"] for s in entry["snapshots"]]
        trend = classify_trend(ranks)
        last  = ranks[-1] if ranks else None
        best  = min(r for r in ranks if r) if any(r for r in ranks if r) else None
        rec   = (kw, last, best, ranks)
        {"rising": rising, "falling": falling, "volatile": volatile,
         "stable": stable, "insufficient": new_kws}[trend].append(rec)

    width = 62
    print(c(Style.BRIGHT, f"\n  {'═' * width}"))
    print(c(Style.BRIGHT, f"  TREND REPORT — {site}"))
    print(c(Style.BRIGHT, f"  {'═' * width}"))
    print(c(Style.DIM,    f"  Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n"))

    for group, color, label in [
        (rising,   Fore.GREEN,  "▲ RISING   — improving, keep doing what you're doing"),
        (stable,   Fore.CYAN,   "— STABLE   — consistent, focus elsewhere"),
        (volatile, Fore.YELLOW, "~ VOLATILE — unstable, monitor closely"),
        (falling,  Fore.RED,    "▼ FALLING  — dropping, needs attention"),
        (new_kws,  Style.DIM,   "· NEW      — not enough data yet"),
    ]:
        if not group: continue
        print(c(color + Style.BRIGHT, f"  {label}"))
        print(c(Style.DIM, f"  {'─' * width}"))
        for kw, last, best, ranks in sorted(group, key=lambda x: (x[1] or 999)):
            last_str = c(color, f"#{last}") if last else c(Fore.RED, "out")
            best_str = c(Fore.GREEN, f"#{best}") if best else c(Style.DIM, "—")
            print(f"  {last_str:<18} {spark(ranks[-8:])}  {kw}  (best: {best_str})")
        print()

    print(c(Style.BRIGHT, f"  {'─' * width}"))
    print(c(Style.BRIGHT,  "  ACTION ITEMS"))
    print(c(Style.BRIGHT, f"  {'─' * width}"))
    if falling:  print(c(Fore.RED,    f"  ⚠  {len(falling)} keyword(s) falling — review your content"))
    if volatile: print(c(Fore.YELLOW, f"  ⚡  {len(volatile)} keyword(s) volatile — monitor closely"))
    if rising:   print(c(Fore.GREEN,  f"  ✓  {len(rising)} keyword(s) rising — double down on this content"))
    if stable:   print(c(Fore.CYAN,   f"  →  {len(stable)} keyword(s) stable — maintain and focus elsewhere"))
    if not (falling or volatile or rising or stable):
        print(c(Style.DIM, "  Run more checks with --save to generate trends."))
    print()


# ── Display ───────────────────────────────────────────────────────────────────

def print_full_list(keyword, results, target, competitors, top_n, prev_rank, alert_threshold):
    width = 64
    print(c(Style.BRIGHT, f"\n  ┌{'─' * width}┐"))
    print(c(Style.BRIGHT, f"  │  Keyword: {keyword:<{width - 10}}│"))
    print(c(Style.BRIGHT, f"  └{'─' * width}┘"))

    if not results:
        print(c(Fore.YELLOW, "    No results found — Google may have blocked the request.\n"))
        return None, {}

    target_rank, competitor_ranks = None, {}

    for r in results:
        is_mine = domain_matches(r["url"], target)
        is_comp = [comp for comp in competitors if domain_matches(r["url"], comp)]
        rank_str = f"#{r['rank']:<3}"
        title    = truncate(r["title"], 46)
        domain   = truncate(r["displayed_url"], 42)

        if is_mine:
            target_rank = r["rank"]
            trend       = trend_arrow(target_rank, prev_rank)
            print(f"  {c(Fore.GREEN + Style.BRIGHT, '► ' + rank_str)}  {c(Fore.GREEN + Style.BRIGHT, title)}")
            print(f"           {c(Fore.GREEN, domain)}  {c(Fore.GREEN + Style.BRIGHT, '◄ YOUR SITE')}{trend}")
        elif is_comp:
            comp_label = is_comp[0]
            if comp_label not in competitor_ranks:
                competitor_ranks[comp_label] = r["rank"]
            print(f"  {c(Fore.YELLOW + Style.BRIGHT, '◆ ' + rank_str)}  {c(Fore.YELLOW, title)}")
            print(f"           {c(Fore.YELLOW, domain)}  {c(Fore.YELLOW + Style.BRIGHT, f'◆ COMPETITOR ({comp_label})')}")
        else:
            print(f"  {c(Style.DIM, '  ' + rank_str)}  {c(Style.DIM, title)}")
            print(f"           {c(Style.DIM, domain)}")

    if target_rank:
        print(c(Fore.GREEN, f"\n  ✓ Ranked #{target_rank} of top {top_n}"))
    else:
        msg = f"  ✗ Not found in top {top_n}"
        if prev_rank:
            msg += f"  {c(Fore.RED, f'▼ dropped out (was #{prev_rank})')}"
        print(c(Fore.RED, msg))

    if competitor_ranks:
        parts = [f"{comp} at #{rank}" for comp, rank in sorted(competitor_ranks.items(), key=lambda x: x[1])]
        print(c(Fore.YELLOW, f"  ◆ Competitors: {', '.join(parts)}"))

    alert = check_alert(keyword, target_rank, prev_rank, alert_threshold)
    if alert: print(f"\n{alert}")

    print()
    return target_rank, competitor_ranks

def print_history(history, site):
    entries = {k: v for k, v in history.items() if v["site"] == site}
    if not entries:
        print(c(Fore.YELLOW, f"\n  No history for {site}."))
        print(c(Style.DIM, "  Run searches with --save to start tracking.\n"))
        return

    print(c(Style.BRIGHT, f"\n  {'─' * 62}"))
    print(c(Style.BRIGHT, f"  Rank history — {site}"))
    print(c(Style.BRIGHT, f"  {'─' * 62}"))

    for key, entry in sorted(entries.items()):
        kw    = entry["keyword"]
        snaps = entry["snapshots"]
        ranks = [s["rank"] for s in snaps]
        curr  = ranks[-1] if ranks else None
        best  = min(r for r in ranks if r) if any(r for r in ranks if r) else None

        print(f"\n  {c(Style.BRIGHT, kw)}")
        print(f"  Trend : {spark(ranks)}  ({len(snaps)} snapshot{'s' if len(snaps)!=1 else ''})")
        curr_str = c(Fore.GREEN + Style.BRIGHT, f"#{curr}") if curr else c(Fore.RED, "not ranked")
        best_str = c(Fore.GREEN, f"#{best}") if best else c(Style.DIM, "—")
        print(f"  Now   : {curr_str}    Best ever: {best_str}")

        recent = list(zip([s["date"] for s in snaps], ranks))[-5:]
        print(c(Style.DIM, f"  {'Date':<20} Rank"))
        print(c(Style.DIM, f"  {'─' * 28}"))
        for i, (date, rank) in enumerate(recent):
            rank_str = f"#{rank}" if rank else "—"
            mv = ""
            if i > 0:
                prev = recent[i-1][1]
                if rank and prev:
                    diff = prev - rank
                    mv   = c(Fore.GREEN, f" ▲{diff}") if diff > 0 else c(Fore.RED, f" ▼{abs(diff)}") if diff < 0 else c(Style.DIM, "  —")
            print(f"  {c(Style.DIM, date):<20} {c(Fore.GREEN if rank else Style.DIM, rank_str)}{mv}")

    print(c(Style.BRIGHT, f"\n  {'─' * 62}\n"))

def print_summary(rank_map, prev_ranks, comp_data, target, top_n, elapsed, saved, competitors):
    found  = {kw: r for kw, r in rank_map.items() if r}
    missed = [kw for kw, r in rank_map.items() if not r]
    ranks  = list(found.values())

    print(c(Style.BRIGHT, "\n" + "═" * 64))
    print(c(Style.BRIGHT,   "  SUMMARY"))
    print(c(Style.BRIGHT,   "═" * 64))
    print(f"  Site        : {c(Fore.CYAN + Style.BRIGHT, target)}")
    if competitors:
        print(f"  Competitors : {c(Fore.YELLOW, ', '.join(competitors))}")
    print(f"  Keywords    : {len(rank_map)}")
    print(f"  Found       : {c(Fore.GREEN, str(len(found)))}")
    print(f"  Missed      : {c(Fore.RED, str(len(missed)))}")
    if ranks:
        print(f"  Best rank   : {c(Fore.GREEN + Style.BRIGHT, '#' + str(min(ranks)))}")
        print(f"  Avg rank    : #{sum(ranks)/len(ranks):.1f}")
    print(f"  Time        : {elapsed:.1f}s")
    if saved:
        print(f"  History     : {c(Fore.CYAN, 'snapshot saved → ' + HISTORY_FILE)}")
    print("═" * 64)

    if found:
        print(c(Style.BRIGHT, "\n  Your rankings:"))
        for kw, rank in sorted(found.items(), key=lambda x: x[1]):
            bar   = c(Fore.GREEN, "█" * max(1, top_n - rank + 1))
            trend = trend_arrow(rank, prev_ranks.get(kw))
            print(f"    #{rank:<3} {bar:<12} {kw}{trend}")

    if missed:
        print(c(Style.BRIGHT, "\n  Not ranked:"))
        for kw in missed:
            prev = prev_ranks.get(kw)
            note = c(Fore.RED, f"  ▼ dropped out (was #{prev})") if prev else ""
            print(c(Style.DIM, f"    —    {kw}") + note)

    if competitors and comp_data:
        print(c(Style.BRIGHT, "\n  Competitor appearances:"))
        comp_totals = {}
        for kw, cmap in comp_data.items():
            for comp, rank in cmap.items():
                comp_totals.setdefault(comp, []).append((kw, rank))
        for comp, appearances in sorted(comp_totals.items()):
            print(c(Fore.YELLOW, f"    {comp}:"))
            for kw, rank in sorted(appearances, key=lambda x: x[1]):
                print(c(Style.DIM, f"      #{rank:<3} {kw}"))
    print()


# ── Export ────────────────────────────────────────────────────────────────────

def export_history_csv(history, site, path):
    entries = {k: v for k, v in history.items() if v["site"] == site}
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["Site", "Keyword", "Date", "Rank", "Top1", "Top2", "Top3"])
        for key, entry in sorted(entries.items()):
            for snap in entry["snapshots"]:
                top = snap.get("top3", [])
                w.writerow([entry["site"], entry["keyword"], snap["date"], snap["rank"] or "",
                    top[0]["url"] if len(top) > 0 else "",
                    top[1]["url"] if len(top) > 1 else "",
                    top[2]["url"] if len(top) > 2 else ""])
    print(c(Fore.CYAN, f"  [✓] History exported to {path}"))

def export_results_csv(keyword_data, path):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["Keyword", "Rank", "Title", "URL", "Displayed URL", "Is Target"])
        for kw, data in keyword_data.items():
            for r in data["results"]:
                is_t = domain_matches(r["url"], data["target"])
                w.writerow([kw, r["rank"], r["title"], r["url"], r["displayed_url"], "YES" if is_t else ""])
    print(c(Fore.CYAN, f"  [✓] Results exported to {path}"))


# ── CLI ───────────────────────────────────────────────────────────────────────

def parse_args():
    p = argparse.ArgumentParser(
        description="CheckMyWeb v6 — personal SEO rank checker, no API key needed",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  QUICK START — try these to verify the tool is working:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  Wikipedia ranks for informational keywords — great first test:
  python checkmyweb.py --site wikipedia.org --keywords "facebook" "python programming" --save

  GitHub ranks for dev keywords:
  python checkmyweb.py --site github.com --keywords "open source projects" "free code hosting"

  Local business search (Philippines):
  python checkmyweb.py --site transienthouse.com --keywords "transient house" "where to stay" --country ph --save

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  WHY DOESN'T facebook.com SHOW FOR "facebook"?
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  This tool searches as an anonymous user (no cookies, no login).
  For mega-brands, Google shows app stores and Wikipedia instead
  of the homepage. Your browser shows it #1 because you are
  already logged in and Google personalizes your results.

  This is Google behavior — not a tool limitation.
  This tool is built for real SEO use cases:
    * "transient house"     -> does transienthouse.com rank?
    * "best pizza delivery"      -> does yourpizzaplace.com rank?
    * "affordable web hosting"   -> does yourhostingsite.com rank?

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  TIPS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  - Use --save every run to build history and track movement
  - Use --delay 8 or higher if Google blocks you (CAPTCHA)
  - Use --country ph for Philippine Google results
  - Use --report after several --save runs to see trends
  - Use --competitors to see rival sites in the same results

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  ALL EXAMPLES
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  python checkmyweb.py --site yoursite.com --keywords "your keyword" --save
  python checkmyweb.py --site yoursite.com --file keywords.txt --country ph --save
  python checkmyweb.py --site yoursite.com --keywords "keyword" --competitors rival.com --save
  python checkmyweb.py --site yoursite.com --keywords "keyword" --alert 5 --save
  python checkmyweb.py --site yoursite.com --history
  python checkmyweb.py --site yoursite.com --report
  python checkmyweb.py --site yoursite.com --history --export history.csv
        """
    )
    p.add_argument("--site",        required=True,         help="Your domain, e.g. yoursite.com")
    p.add_argument("--keywords",    nargs="+",             help="Keywords to check")
    p.add_argument("--file",                               help="Text file with keywords (one per line)")
    p.add_argument("--competitors", nargs="+", default=[], help="Competitor domains to highlight in results")
    p.add_argument("--top",         type=int,  default=10, help="Results to show per keyword (default 10, max 20)")
    p.add_argument("--country",     default="ph",          help="Country code for Google results e.g. ph, us, gb (default: ph)")
    p.add_argument("--delay",       type=float,default=5,  help="Seconds between searches (default 5, increase if blocked)")
    p.add_argument("--alert",       type=int,              help="Alert if rank drops by N or more positions")
    p.add_argument("--save",        action="store_true",   help="Save this run as a history snapshot")
    p.add_argument("--history",     action="store_true",   help="Show rank history for this site")
    p.add_argument("--report",      action="store_true",   help="Show trend report (rising/falling/volatile)")
    p.add_argument("--export",                             help="Export results or history to .csv")
    p.add_argument("--no-banner",   action="store_true",   help="Skip the ASCII banner")
    return p.parse_args()


def main():
    args    = parse_args()
    history = load_history()
    target  = normalize_domain(args.site)
    competitors = [normalize_domain(c_) for c_ in args.competitors]

    if not args.no_banner:
        print(c(Fore.CYAN, BANNER))

    if args.report:
        print_trend_report(history, target); return

    if args.history:
        print_history(history, target)
        if args.export:
            export_history_csv(history, target, args.export)
        return

    keywords = []
    if args.keywords: keywords += args.keywords
    if args.file:     keywords += load_keywords(args.file)
    keywords = list(dict.fromkeys(keywords))

    if not keywords:
        print(c(Fore.RED, "  [!] No keywords. Use --keywords or --file.")); sys.exit(1)

    top_n = min(max(args.top, 1), 20)
    delay = max(args.delay, 2)

    print(f"  Target      : {c(Fore.CYAN + Style.BRIGHT, target)}")
    if competitors:
        print(f"  Competitors : {c(Fore.YELLOW, ', '.join(competitors))}")
    print(f"  Keywords    : {c(Style.BRIGHT, str(len(keywords)))}")
    print(f"  Showing     : top {top_n} results per keyword")
    print(f"  Country     : {args.country.upper()} (Google .{('com.ph' if args.country=='ph' else 'com')})")
    print(f"  Delay       : {delay}s between searches")
    if args.alert:
        print(f"  Alerts      : {c(Fore.RED, f'ON — fire if rank drops ≥{args.alert} positions')}")
    print(f"  Tracking    : {c(Fore.CYAN, 'ON — saving snapshot') if args.save else c(Style.DIM, 'OFF — use --save to track history')}")
    print(f"  Mode        : {c(Fore.YELLOW, 'Direct scrape — no API key needed')}")

    session      = make_session()
    rank_map     = {}
    prev_ranks   = {}
    comp_data    = {}
    keyword_data = {}
    start        = time.time()

    for i, kw in enumerate(keywords, 1):
        # rotate user agent every 3 searches
        if i % 3 == 0:
            session = make_session()

        prev           = get_last_rank(history, target, kw)
        prev_ranks[kw] = prev

        print(c(Style.DIM, f"\n  [{i}/{len(keywords)}] Searching: {kw} ..."), end="", flush=True)

        try:
            results = scrape_google(kw, top_n, session, args.country)
            print("\r" + " " * 70 + "\r", end="")
            target_rank, comp_ranks = print_full_list(kw, results, target, competitors, top_n, prev, args.alert)
            rank_map[kw]     = target_rank
            comp_data[kw]    = comp_ranks
            keyword_data[kw] = {"results": results, "target": target}
            if args.save:
                record_snapshot(history, target, kw, target_rank, results)
        except RuntimeError as e:
            print(f"\n  {c(Fore.RED, '[!]')} {kw}: {e}\n")
            rank_map[kw]     = None
            comp_data[kw]    = {}
            keyword_data[kw] = {"results": [], "target": target}

        if i < len(keywords):
            for s in range(int(delay), 0, -1):
                print(c(Style.DIM, f"  Waiting {s}s...  "), end="\r", flush=True)
                time.sleep(1)
            time.sleep(random.uniform(0, 2))
            print(" " * 20 + "\r", end="")

    if args.save:
        save_history(history)

    elapsed = time.time() - start
    print_summary(rank_map, prev_ranks, comp_data, target, top_n, elapsed, args.save, competitors)

    if args.export:
        export_results_csv(keyword_data, args.export)

    sys.exit(0 if any(v for v in rank_map.values()) else 1)


if __name__ == "__main__":
    main()
