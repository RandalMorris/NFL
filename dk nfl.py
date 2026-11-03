#!/usr/bin/env python3
"""DraftKings Predictions NFL analyzer, single-file build (v0.5.0).

NFL tools for DraftKings Predictions: pre-game and live, singles, props and combos.

  python3 dk_nfl.py board                        games this week (and live ones): fair win %, spread, total
  python3 dk_nfl.py check bills win --yes 58     is a price good? (no price: shows the most to pay)
  python3 dk_nfl.py check titans +7.5 --yes 52   spreads are written the way the app shows them
  python3 dk_nfl.py check bills total 54.5 --yes 50
  python3 dk_nfl.py prop "Jahmyr Gibbs" "anytime td" --game DET --yes 45
  python3 dk_nfl.py prop "Jared Goff" "pass yds" 249.5 --game DET --yes 48
  python3 dk_nfl.py parlay "TEN +7.5" "Jahmyr Gibbs | anytime td | MIN @ DET" --price 22
                                             fair price of a combo, and whether the app's quote is good
  python3 dk_nfl.py template                     write dk_data/dk_prices.csv to fill in from the app
  python3 dk_nfl.py scan                         rank every price in dk_data/dk_prices.csv; always names a top pick
  python3 dk_nfl.py parlays                      best 2-3 leg combos from the prices in dk_data/dk_prices.csv
  python3 dk_nfl.py log titans spread +7.5 --side yes --price 52 --contracts 18
  python3 dk_nfl.py log-combo "LEG" "LEG" --price 22 --contracts 10
  python3 dk_nfl.py settle                       fill in results for finished games
  python3 dk_nfl.py result 7 won                 settle a prop or combo by hand (won, lost or void)
  python3 dk_nfl.py report                       profit, closing edge and calibration

Prices can be typed in cents (58) or dollars (0.58). Live games, player props and
alternate lines need an Odds API key. Change any setting for one run with --set,
e.g. --set bankroll=300.

Files it writes go in ./dk_data (the folder you run it from). Built from the
dk-predictions-analyzer project; edit the project and rebuild, not this file.
"""

from __future__ import annotations

__version__ = '0.5.0'
__single_file__ = True


# ==================== teams ===================================================

import re

# (abbreviation, full name, location, nickname) for the 2026 season, from nflverse teams.csv.
TEAMS = [
    ("ARI", "Arizona Cardinals", "Arizona", "Cardinals"),
    ("ATL", "Atlanta Falcons", "Atlanta", "Falcons"),
    ("BAL", "Baltimore Ravens", "Baltimore", "Ravens"),
    ("BUF", "Buffalo Bills", "Buffalo", "Bills"),
    ("CAR", "Carolina Panthers", "Carolina", "Panthers"),
    ("CHI", "Chicago Bears", "Chicago", "Bears"),
    ("CIN", "Cincinnati Bengals", "Cincinnati", "Bengals"),
    ("CLE", "Cleveland Browns", "Cleveland", "Browns"),
    ("DAL", "Dallas Cowboys", "Dallas", "Cowboys"),
    ("DEN", "Denver Broncos", "Denver", "Broncos"),
    ("DET", "Detroit Lions", "Detroit", "Lions"),
    ("GB", "Green Bay Packers", "Green Bay", "Packers"),
    ("HOU", "Houston Texans", "Houston", "Texans"),
    ("IND", "Indianapolis Colts", "Indianapolis", "Colts"),
    ("JAX", "Jacksonville Jaguars", "Jacksonville", "Jaguars"),
    ("KC", "Kansas City Chiefs", "Kansas City", "Chiefs"),
    ("LAC", "Los Angeles Chargers", "Los Angeles", "Chargers"),
    ("LA", "Los Angeles Rams", "Los Angeles", "Rams"),
    ("LV", "Las Vegas Raiders", "Las Vegas", "Raiders"),
    ("MIA", "Miami Dolphins", "Miami", "Dolphins"),
    ("MIN", "Minnesota Vikings", "Minnesota", "Vikings"),
    ("NE", "New England Patriots", "New England", "Patriots"),
    ("NO", "New Orleans Saints", "New Orleans", "Saints"),
    ("NYG", "New York Giants", "New York", "Giants"),
    ("NYJ", "New York Jets", "New York", "Jets"),
    ("PHI", "Philadelphia Eagles", "Philadelphia", "Eagles"),
    ("PIT", "Pittsburgh Steelers", "Pittsburgh", "Steelers"),
    ("SEA", "Seattle Seahawks", "Seattle", "Seahawks"),
    ("SF", "San Francisco 49ers", "San Francisco", "49ers"),
    ("TB", "Tampa Bay Buccaneers", "Tampa Bay", "Buccaneers"),
    ("TEN", "Tennessee Titans", "Tennessee", "Titans"),
    ("WAS", "Washington Commanders", "Washington", "Commanders"),
]

ALIASES = {
    "LAR": "LA", "RAMS": "LA", "WSH": "WAS", "JAC": "JAX", "LVR": "LV", "OAK": "LV",
    "NINERS": "SF", "PATS": "NE", "BUCS": "TB", "JAGS": "JAX", "PHILLY": "PHI",
    "GNB": "GB", "KAN": "KC", "NWE": "NE", "NOR": "NO", "SFO": "SF", "TAM": "TB",
}

_FULL = {abbr: full for abbr, full, _, _ in TEAMS}
_BY_FULL = {full.lower(): abbr for abbr, full, _, _ in TEAMS}


def _norm(text: str) -> str:
    return re.sub(r"[^a-z0-9 ]", "", str(text).lower()).strip()


def full_name(abbr: str) -> str | None:
    return _FULL.get(str(abbr).upper())


def abbr_for_name(name: str) -> str | None:
    """Exact match on a full team name as data feeds write it ("Kansas City Chiefs")."""
    if not name:
        return None
    return _BY_FULL.get(str(name).strip().lower()) or (str(name).upper() if str(name).upper() in _FULL else None)


def lookup_team(text: str) -> str:
    """Turn "chiefs", "KC", "Kansas City" or "kansas city chiefs" into "KC"."""
    raw = str(text).strip()
    if not raw:
        raise ValueError("team is blank")
    upper = re.sub(r"[^A-Z0-9]", "", raw.upper())
    if upper in _FULL:
        return upper
    if upper in ALIASES:
        return ALIASES[upper]
    q = _norm(raw)
    for abbr, full, loc, nick in TEAMS:
        if q in (_norm(full), _norm(nick)):
            return abbr
    words = q.split()
    if len(words) > 1:  # the app's style: "TEN Titans", "LA Chargers", "NO Saints"
        nick_hits = {abbr for abbr, _, _, nick in TEAMS if _norm(nick) in words}
        if len(nick_hits) == 1:
            return nick_hits.pop()
        code_hits = {w.upper() for w in words if w.upper() in _FULL} | {ALIASES[w.upper()] for w in words
                                                                         if w.upper() in ALIASES}
        if len(code_hits) == 1 and not nick_hits:
            return code_hits.pop()
    loc_hits = [abbr for abbr, _, loc, _ in TEAMS if _norm(loc) == q]
    if len(loc_hits) == 1:
        return loc_hits[0]
    hits = [abbr for abbr, full, _, _ in TEAMS if q and q in _norm(full)]
    if len(hits) == 1:
        return hits[0]
    if len(hits) > 1 or len(loc_hits) > 1:
        options = ", ".join(f"{a} ({_FULL[a]})" for a in (hits or loc_hits))
        raise ValueError(f"{text!r} could be {options}; use the nickname or abbreviation")
    raise ValueError(f"unknown team {text!r}")


# ==================== timeutil ================================================

from datetime import date, datetime, time, timedelta, timezone


def _nth_sunday(year: int, month: int, n: int) -> date:
    first = date(year, month, 1)
    offset = (6 - first.weekday()) % 7  # days until the first Sunday
    return first + timedelta(days=offset + 7 * (n - 1))


def _eastern_is_dst(local: datetime) -> bool:
    """DST runs from 2 AM on the 2nd Sunday of March to 2 AM on the 1st Sunday of November."""
    start = datetime.combine(_nth_sunday(local.year, 3, 2), time(2, 0))
    end = datetime.combine(_nth_sunday(local.year, 11, 1), time(2, 0))
    return start <= local.replace(tzinfo=None) < end


def eastern_to_utc(local: datetime) -> datetime:
    offset = 4 if _eastern_is_dst(local) else 5
    return (local.replace(tzinfo=None) + timedelta(hours=offset)).replace(tzinfo=timezone.utc)


def utc_to_eastern(moment: datetime) -> datetime:
    """Naive US Eastern local time for an aware datetime."""
    utc = moment.astimezone(timezone.utc).replace(tzinfo=None)
    standard = utc - timedelta(hours=5)
    # In standard-time terms, DST covers 2 AM (2nd Sunday of March) to 1 AM (1st Sunday of November).
    start = datetime.combine(_nth_sunday(standard.year, 3, 2), time(2, 0))
    end = datetime.combine(_nth_sunday(standard.year, 11, 1), time(1, 0))
    if start <= standard < end:
        return utc - timedelta(hours=4)
    return standard


def parse_iso_utc(text: str) -> datetime:
    t = str(text).strip().replace("Z", "+00:00")
    moment = datetime.fromisoformat(t)
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    return moment.astimezone(timezone.utc)


def week_window_end(now: datetime) -> datetime:
    """End of the current NFL week (Thursday to Monday): the next Tuesday 6 AM Eastern."""
    local = utc_to_eastern(now)
    days_until_tuesday = (1 - local.weekday()) % 7
    end_local = datetime.combine(local.date() + timedelta(days=days_until_tuesday), time(6, 0))
    if end_local <= local:
        end_local += timedelta(days=7)
    return eastern_to_utc(end_local)


def fmt_local(moment: datetime) -> str:
    """Kickoff in this computer's time zone, e.g. 'Sun 11/01 12:00 PM'."""
    return moment.astimezone().strftime("%a %m/%d %I:%M %p")


# ==================== odds_math ===============================================

def american_to_prob(american) -> float:
    """-150 -> 0.600, +130 -> 0.435 (raw, still includes the vig)."""
    a = float(american)
    if -100 < a < 100:
        raise ValueError(f"{american!r} is not a valid American price")
    if a > 0:
        return 100.0 / (a + 100.0)
    return -a / (-a + 100.0)


def decimal_to_prob(decimal_odds) -> float:
    """2.50 -> 0.400 (raw, still includes the vig)."""
    d = float(decimal_odds)
    if d <= 1.0:
        raise ValueError(f"{decimal_odds!r} is not a valid decimal price")
    return 1.0 / d


def price_to_prob(price) -> float:
    """Accept either format: negative or >= 100 is American, otherwise decimal."""
    p = float(price)
    if p < 0 or p >= 100:
        return american_to_prob(p)
    return decimal_to_prob(p)


def devig_two_way(p_a: float, p_b: float, method: str = "power") -> float:
    """Fair probability of outcome A from the raw implied probabilities of A and B.

    "proportional" scales both so they sum to 1. "power" finds k with
    p_a**k + p_b**k = 1, which shifts a little more of the margin onto the
    underdog. On 2012-2026 NFL closing moneylines the power method scored
    slightly better (log loss 0.6104 vs 0.6106), so it is the default.
    """
    if p_a <= 0 or p_b <= 0:
        raise ValueError("implied probabilities must be positive")
    total = p_a + p_b
    if method == "proportional" or total <= 1.0:
        return p_a / total
    if method != "power":
        raise ValueError(f"unknown devig method {method!r}; use 'power' or 'proportional'")
    lo, hi = 1.0, 50.0
    for _ in range(100):
        k = (lo + hi) / 2
        if p_a ** k + p_b ** k > 1.0:
            lo = k
        else:
            hi = k
    k = (lo + hi) / 2
    fa, fb = p_a ** k, p_b ** k
    return fa / (fa + fb)


# ==================== edge ====================================================

from dataclasses import dataclass

# DraftKings Predictions per-contract fee tiers for its DKeX / Crypto.com exchange
# markets, as reported by third-party reviews in 2026: $0.01 when the price is
# below $0.20, $0.02 from $0.20 to $0.96, and $0.03 from $0.97. Each entry is
# (price upper bound, exclusive; fee). Verify in the app and override
# "fee_schedule" in config.json if yours differs.
DEFAULT_FEE_SCHEDULE = ((0.20, 0.01), (0.97, 0.02), (1.00, 0.03))


def fee_for_price(price: float, schedule=DEFAULT_FEE_SCHEDULE) -> float:
    """Per-contract fee for buying at `price`, from a list of (upper bound, fee) tiers.

    An empty schedule means no fee.
    """
    if not schedule:
        return 0.0
    for upper, fee in schedule:
        if price < float(upper) - 1e-9:
            return float(fee)
    return float(schedule[-1][1])


def parse_price(value) -> float | None:
    """Read a contract price typed as dollars or cents.

    "0.55", ".55", "$0.55", "55", "55c" all mean $0.55. Blank means no price.
    Whole numbers from 1 to 99 are read as cents.
    """
    if value is None:
        return None
    text = str(value).strip().lower().replace("$", "").replace("¢", "").rstrip("c").strip()
    if not text:
        return None
    try:
        number = float(text)
    except ValueError:
        raise ValueError(f"can't read price {value!r}; use dollars like 0.55 or cents like 55")
    if number >= 1:
        number = number / 100.0
    number = round(number, 4)
    if not 0.01 <= number <= 0.99:
        raise ValueError(f"price {value!r} must be between 1 and 99 cents")
    return number


@dataclass
class TradeEvaluation:
    side: str                 # "YES" or "NO"
    price: float              # price paid per contract, e.g. 0.42
    fee: float                # fee per contract, in dollars (your estimate)
    my_prob: float            # your probability that the side wins
    cost: float               # price + fee: what you actually pay
    expected_value: float     # expected profit per contract, after costs
    edge: float               # my_prob - cost (value per $1 of payout)
    roi: float                # expected_value / cost
    kelly_fraction: float     # full Kelly fraction of bankroll
    suggested_fraction: float # fractional Kelly, capped


def implied_probability(price: float) -> float:
    """A contract priced at 0.40 implies a 40% chance of the event."""
    _check_price(price)
    return price


def no_price(yes_price: float) -> float:
    """The NO side of a market costs the complement of the YES price."""
    _check_price(yes_price)
    return round(1.0 - yes_price, 2)


def expected_value(my_prob: float, cost: float) -> float:
    """Expected profit per contract. Win pays $1 minus cost; loss forfeits cost."""
    return my_prob * (1.0 - cost) - (1.0 - my_prob) * cost


def kelly_fraction(my_prob: float, cost: float) -> float:
    """Full Kelly fraction of bankroll for a binary bet bought at `cost`.

    Net odds b = (1 - cost) / cost. Kelly f* = (b*p - q) / b.
    Returns 0 when there is no edge (never negative: we don't short by default).
    """
    if not 0 < cost < 1:
        return 0.0
    b = (1.0 - cost) / cost
    q = 1.0 - my_prob
    f = (b * my_prob - q) / b
    return max(0.0, f)


def evaluate_trade(
    side: str,
    price: float,
    my_prob: float,
    fee: float = 0.0,
    kelly_multiplier: float = 0.25,
    max_bankroll_fraction: float = 0.05,
    min_edge: float = 0.03,
) -> TradeEvaluation:
    """Evaluate buying one contract.

    Args:
        side: "YES" or "NO".
        price: the price you would pay for that side (use no_price() for NO).
        my_prob: your probability that this side wins, between 0 and 1.
        fee: estimated per-contract fee plus half the bid/ask spread, in dollars.
        kelly_multiplier: fraction of full Kelly to use (0.25 = quarter Kelly).
        max_bankroll_fraction: hard cap on any single position as a share of bankroll.
        min_edge: below this edge, suggested size is 0 (estimates are noisy).
    """
    side = side.upper()
    if side not in {"YES", "NO"}:
        raise ValueError("side must be 'YES' or 'NO'")
    _check_price(price)
    if not 0 <= my_prob <= 1:
        raise ValueError("my_prob must be between 0 and 1")
    if fee < 0:
        raise ValueError("fee cannot be negative")

    cost = round(price + fee, 4)
    if cost >= 1:
        raise ValueError("price plus fee must be below $1")

    ev = expected_value(my_prob, cost)
    edge = my_prob - cost
    full_kelly = kelly_fraction(my_prob, cost)
    suggested = min(full_kelly * kelly_multiplier, max_bankroll_fraction)
    if edge < min_edge:
        suggested = 0.0

    return TradeEvaluation(
        side=side,
        price=price,
        fee=fee,
        my_prob=my_prob,
        cost=cost,
        expected_value=round(ev, 4),
        edge=round(edge, 4),
        roi=round(ev / cost, 4),
        kelly_fraction=round(full_kelly, 4),
        suggested_fraction=round(suggested, 4),
    )


def brier_score(forecasts: list[float], outcomes: list[int]) -> float:
    """Mean squared error of probability forecasts. Lower is better.

    outcomes are 1 if the event happened, 0 if not. A coin-flip forecaster
    scores 0.25; consistently scoring above 0.25 means your estimates are
    worse than guessing 50/50.
    """
    if len(forecasts) != len(outcomes) or not forecasts:
        raise ValueError("forecasts and outcomes must be non-empty and the same length")
    return sum((f - o) ** 2 for f, o in zip(forecasts, outcomes)) / len(forecasts)


def _check_price(price: float) -> None:
    if not 0.01 <= price <= 0.99:
        raise ValueError("price must be between $0.01 and $0.99")


# ==================== nfl_model ===============================================

import json
import math
from dataclasses import dataclass, field
from pathlib import Path

DEFAULT_MODEL_PATH = Path(__file__).resolve().parent.parent / "data" / "nfl_model.json"
EMBEDDED_MODEL = json.loads("{\"meta\":{\"fitted\":\"2026-11-01\",\"source\":\"nflverse games.csv (github.com/nflverse/nfldata)\",\"seasons\":\"2015-2026\",\"games\":3136,\"holdout\":{\"seasons\":\"2024-2026\",\"games\":678,\"spread_strike_brier_plain_bell_curve\":0.22788,\"spread_strike_brier_key_numbers\":0.22703,\"total_strike_brier\":0.23163}},\"margin\":{\"lo\":-80,\"hi\":80,\"sigma\":12.7,\"weights\":{\"-80\":1.0049,\"-79\":1.0049,\"-78\":1.0049,\"-77\":1.0049,\"-76\":1.0049,\"-75\":1.0049,\"-74\":1.0049,\"-73\":1.0049,\"-72\":1.0049,\"-71\":1.0049,\"-70\":1.0049,\"-69\":1.0049,\"-68\":1.0049,\"-67\":1.0049,\"-66\":1.0049,\"-65\":1.0049,\"-64\":1.0049,\"-63\":1.0049,\"-62\":1.0049,\"-61\":1.0049,\"-60\":1.0049,\"-59\":1.0049,\"-58\":1.0049,\"-57\":1.0049,\"-56\":1.0049,\"-55\":1.0049,\"-54\":1.0049,\"-53\":1.0049,\"-52\":1.0049,\"-51\":1.0049,\"-50\":1.0049,\"-49\":1.0049,\"-48\":1.0049,\"-47\":1.0049,\"-46\":1.0049,\"-45\":1.0049,\"-44\":1.0049,\"-43\":1.0049,\"-42\":1.0049,\"-41\":1.0049,\"-40\":1.0049,\"-39\":1.0049,\"-38\":1.0049,\"-37\":1.0049,\"-36\":1.0049,\"-35\":1.0049,\"-34\":1.0049,\"-33\":1.0049,\"-32\":1.0049,\"-31\":1.0049,\"-30\":0.7353,\"-29\":0.6824,\"-28\":1.7019,\"-27\":0.7515,\"-26\":0.8649,\"-25\":0.8958,\"-24\":1.4367,\"-23\":0.8603,\"-22\":0.6284,\"-21\":1.1526,\"-20\":0.9733,\"-19\":0.4877,\"-18\":0.8944,\"-17\":1.3085,\"-16\":0.7988,\"-15\":0.5104,\"-14\":1.5356,\"-13\":0.566,\"-12\":0.5095,\"-11\":0.532,\"-10\":1.1363,\"-9\":0.3832,\"-8\":0.963,\"-7\":1.8748,\"-6\":1.4755,\"-5\":0.8952,\"-4\":0.9217,\"-3\":2.9267,\"-2\":0.8911,\"-1\":0.8483,\"0\":0.1358,\"1\":0.8483,\"2\":0.8911,\"3\":2.9267,\"4\":0.9217,\"5\":0.8952,\"6\":1.4755,\"7\":1.8748,\"8\":0.963,\"9\":0.3832,\"10\":1.1363,\"11\":0.532,\"12\":0.5095,\"13\":0.566,\"14\":1.5356,\"15\":0.5104,\"16\":0.7988,\"17\":1.3085,\"18\":0.8944,\"19\":0.4877,\"20\":0.9733,\"21\":1.1526,\"22\":0.6284,\"23\":0.8603,\"24\":1.4367,\"25\":0.8958,\"26\":0.8649,\"27\":0.7515,\"28\":1.7019,\"29\":0.6824,\"30\":0.7353,\"31\":1.0049,\"32\":1.0049,\"33\":1.0049,\"34\":1.0049,\"35\":1.0049,\"36\":1.0049,\"37\":1.0049,\"38\":1.0049,\"39\":1.0049,\"40\":1.0049,\"41\":1.0049,\"42\":1.0049,\"43\":1.0049,\"44\":1.0049,\"45\":1.0049,\"46\":1.0049,\"47\":1.0049,\"48\":1.0049,\"49\":1.0049,\"50\":1.0049,\"51\":1.0049,\"52\":1.0049,\"53\":1.0049,\"54\":1.0049,\"55\":1.0049,\"56\":1.0049,\"57\":1.0049,\"58\":1.0049,\"59\":1.0049,\"60\":1.0049,\"61\":1.0049,\"62\":1.0049,\"63\":1.0049,\"64\":1.0049,\"65\":1.0049,\"66\":1.0049,\"67\":1.0049,\"68\":1.0049,\"69\":1.0049,\"70\":1.0049,\"71\":1.0049,\"72\":1.0049,\"73\":1.0049,\"74\":1.0049,\"75\":1.0049,\"76\":1.0049,\"77\":1.0049,\"78\":1.0049,\"79\":1.0049,\"80\":1.0049}},\"total\":{\"lo\":0,\"hi\":130,\"sigma\":13.3,\"weights\":{}}}")  # the single-file build stores the fitted model here


class DiscreteScoreModel:
    def __init__(self, lo: int, hi: int, sigma: float, weights: dict | None = None):
        if hi <= lo:
            raise ValueError("hi must be greater than lo")
        if sigma <= 0:
            raise ValueError("sigma must be positive")
        self.lo, self.hi, self.sigma = int(lo), int(hi), float(sigma)
        self.ks = list(range(self.lo, self.hi + 1))
        weights = weights or {}
        self.weights = [float(weights.get(k, 1.0)) for k in self.ks]
        self._cache: dict = {}

    def pmf(self, mu: float) -> list:
        key = round(float(mu), 9)
        cached = self._cache.get(key)
        if cached is not None:
            return cached
        inv = 1.0 / self.sigma
        raw = [math.exp(-0.5 * ((k - mu) * inv) ** 2) * w for k, w in zip(self.ks, self.weights)]
        total = sum(raw)
        probs = [p / total for p in raw]
        if len(self._cache) > 5000:
            self._cache.clear()
        self._cache[key] = probs
        return probs

    def prob_greater(self, mu: float, x: float) -> float:
        """P(X > x)."""
        return sum(p for k, p in zip(self.ks, self.pmf(mu)) if k > x + 1e-9)

    def prob_less(self, mu: float, x: float) -> float:
        """P(X < x)."""
        return sum(p for k, p in zip(self.ks, self.pmf(mu)) if k < x - 1e-9)

    def prob_equal(self, mu: float, x: float) -> float:
        """P(X == x); zero for half-point lines."""
        if abs(x - round(x)) > 1e-9:
            return 0.0
        k = int(round(x))
        if k < self.lo or k > self.hi:
            return 0.0
        return self.pmf(mu)[k - self.lo]

    def prob_over_no_push(self, mu: float, line: float) -> float:
        """P(X > line | X != line): how sportsbooks price a line, with pushes refunded."""
        push = self.prob_equal(mu, line)
        if push >= 1.0:
            return 0.5
        return self.prob_greater(mu, line) / (1.0 - push)

    def mean(self, mu: float) -> float:
        return sum(k * p for k, p in zip(self.ks, self.pmf(mu)))

    def solve_mu(self, line: float, p_over: float) -> float:
        """Find mu so that P(X > line | no push) equals the market's fair p_over."""
        p = min(max(float(p_over), 1e-4), 1 - 1e-4)

        def f(mu):
            return self.prob_over_no_push(mu, line) - p

        a, b = line - 40.0, line + 40.0
        fa, fb = f(a), f(b)
        if fa > 0:
            return a
        if fb < 0:
            return b
        c = (a + b) / 2
        # Illinois (modified regula falsi): f is increasing in mu.
        for _ in range(100):
            c = b - fb * (b - a) / (fb - fa)
            fc = f(c)
            if abs(fc) < 1e-9 or abs(b - a) < 1e-7:
                return c
            if (fc > 0) == (fb > 0):
                fa /= 2.0
            else:
                a, fa = b, fb
            b, fb = c, fc
        return c


@dataclass
class NFLModels:
    margin: DiscreteScoreModel
    total: DiscreteScoreModel
    meta: dict = field(default_factory=dict)


def _model_from_dict(d: dict) -> DiscreteScoreModel:
    weights = {int(k): float(v) for k, v in (d.get("weights") or {}).items()}
    return DiscreteScoreModel(d["lo"], d["hi"], d["sigma"], weights)


def load_models(path: Path | str = DEFAULT_MODEL_PATH) -> NFLModels:
    if Path(path).exists():
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    elif EMBEDDED_MODEL is not None:
        data = EMBEDDED_MODEL
    else:
        raise FileNotFoundError(f"score model not found at {path}; run tools/calibrate.py")
    return NFLModels(_model_from_dict(data["margin"]), _model_from_dict(data["total"]), data.get("meta", {}))


def plain_models(margin_sigma: float = 12.7, total_sigma: float = 13.1) -> NFLModels:
    """Bell-curve models without key-number weights (used by tests and as a fallback)."""
    return NFLModels(
        DiscreteScoreModel(-80, 80, margin_sigma),
        DiscreteScoreModel(0, 130, total_sigma),
        {"description": "plain discrete normal"},
    )


# ==================== textfmt =================================================

def table(headers: list, rows: list, right: tuple = ()) -> str:
    cells = [[str(h) for h in headers]] + [["" if c is None else str(c) for c in row] for row in rows]
    widths = [max(len(r[i]) for r in cells) for i in range(len(headers))]

    def fmt(row):
        parts = []
        for i, cell in enumerate(row):
            parts.append(cell.rjust(widths[i]) if i in right else cell.ljust(widths[i]))
        return "  ".join(parts).rstrip()

    lines = [fmt(cells[0]), "  ".join("-" * w for w in widths)]
    lines += [fmt(r) for r in cells[1:]]
    return "\n".join(lines)


def pct(p: float | None, digits: int = 1) -> str:
    return "-" if p is None else f"{p * 100:.{digits}f}%"


def money(x: float) -> str:
    return f"-${-x:,.2f}" if x < 0 else f"${x:,.2f}"


def num(x: float | None) -> str:
    return "" if x is None else f"{x:g}"


# ==================== config ==================================================

import json
import os
from pathlib import Path

CONFIG_PATH = Path(__file__).resolve().parent.parent / "config.json"

DEFAULTS = {
    "odds_api_key": "",
    "odds_source": "auto",          # auto = The Odds API if a key is set, otherwise nflverse
    "regions": "us",
    "bookmakers": "",               # e.g. "pinnacle,draftkings,fanduel" (overrides regions)
    "sharp_books": "pinnacle",      # pre-game fair odds come from these books when they quote the line
    "devig_method": "power",
    "odds_cache_minutes": 10,
    "nflverse_cache_minutes": 60,
    "bankroll": 500.0,
    "kelly_multiplier": 0.25,
    "max_bet_fraction": 0.05,
    "min_edge": 0.03,
    "model_extra_edge": 0.02,
    "parlay_min_roi": 0.10,
    "parlay_model_extra_roi": 0.05,
    "parlay_max_bet_fraction": 0.01,
    "prop_one_way_margin": 0.08,    # assumed bookmaker margin on Yes-only prop prices
    "live_cache_seconds": 20,       # how long live prices are reused before downloading again
    "live_stale_seconds": 90,       # warn when the newest live price is older than this
    "fee_schedule": [[0.20, 0.01], [0.97, 0.02], [1.00, 0.03]],
}

# Ten books cost the same Odds API credits as one region, and this set adds Pinnacle (an EU book)
# to the main US books. Used when "bookmakers" is blank and "regions" is the default "us".
DEFAULT_BOOKMAKERS = ("pinnacle,draftkings,fanduel,betmgm,williamhill_us,fanatics,betrivers,"
                      "betonlineag,lowvig,bovada")

NUMBERS = ("odds_cache_minutes", "nflverse_cache_minutes", "bankroll", "kelly_multiplier",
           "max_bet_fraction", "min_edge", "model_extra_edge", "parlay_min_roi", "parlay_model_extra_roi",
           "parlay_max_bet_fraction", "prop_one_way_margin", "live_cache_seconds", "live_stale_seconds")


def parse_overrides(items) -> dict:
    """Turn ["bankroll=300", "fee_schedule=[]"] into a dict, checking the names."""
    out = {}
    for item in items or []:
        if "=" not in item:
            raise SystemExit(f"--set needs KEY=VALUE, got {item!r}")
        key, raw = (part.strip() for part in item.split("=", 1))
        if key not in DEFAULTS:
            raise SystemExit(f"unknown setting {key!r}; choose from: {', '.join(sorted(DEFAULTS))}")
        try:
            out[key] = json.loads(raw)
        except json.JSONDecodeError:
            out[key] = raw
        if key in ("odds_api_key", "bookmakers", "regions", "odds_source", "devig_method", "sharp_books"):
            out[key] = str(raw)
    return out


def load_config(path: Path | str | None = None, overrides: dict | None = None) -> dict:
    cfg = dict(DEFAULTS)
    path = Path(path) if path else CONFIG_PATH
    if path.exists():
        try:
            user = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as err:
            raise SystemExit(f"{path.name} is not valid JSON: {err}") from None
        cfg.update({k: v for k, v in user.items() if not k.startswith("_")})
    if os.environ.get("ODDS_API_KEY"):
        cfg["odds_api_key"] = os.environ["ODDS_API_KEY"].strip()
    cfg.update(overrides or {})
    for key in NUMBERS:
        try:
            cfg[key] = float(cfg[key])
        except (TypeError, ValueError):
            raise SystemExit(f"config value {key} must be a number, got {cfg[key]!r}") from None
    cfg["fee_schedule"] = [(float(upper), float(fee)) for upper, fee in (cfg.get("fee_schedule") or [])]
    cfg["sharp_books"] = tuple(b.strip().lower() for b in str(cfg.get("sharp_books") or "").split(",") if b.strip())
    if not str(cfg.get("bookmakers") or "").strip() and str(cfg.get("regions")).strip() == "us" and cfg["sharp_books"]:
        cfg["bookmakers"] = DEFAULT_BOOKMAKERS
    if cfg["odds_source"] not in ("auto", "nflverse", "odds-api"):
        raise SystemExit("odds_source must be auto, nflverse or odds-api")
    return cfg


# ==================== board ===================================================

import math
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from statistics import median


CONTRACT_TYPES = ("win", "spread", "total")
CONTRACT_ALIASES = {
    "win": "win", "winner": "win", "moneyline": "win", "ml": "win", "game": "win",
    "spread": "spread", "spreads": "spread", "margin": "spread", "handicap": "spread",
    "total": "total", "totals": "total", "over": "total", "points": "total", "ou": "total",
}
DEFAULT_TIE_PROB = 0.003
LIVE_WINDOW = timedelta(hours=5)       # a game that kicked off less than this long ago may still be on
MAX_INTERPOLATION_GAP = 3.0            # points between the two live lines we interpolate across


class NoMarketData(Exception):
    """No odds are available to price this contract."""


def normalize_contract(text: str) -> str:
    key = str(text).strip().lower().replace("/", "").replace("-", "").replace(" ", "")
    if key not in CONTRACT_ALIASES:
        raise ValueError(f"unknown contract type {text!r}; use win, spread or total")
    return CONTRACT_ALIASES[key]


def parse_spread_line(text) -> float:
    """'+7.5' / '-7.5' / 'PK' as the app shows them. An unsigned number is refused as ambiguous."""
    t = str(text).strip().lower().replace(" ", "")
    if t in ("pk", "pick", "pickem", "pick'em", "0", "+0", "-0", "0.0", "+0.0", "-0.0"):
        return 0.0
    if not t or t[0] not in "+-":
        raise ValueError(f"spread line {text!r} needs a sign, as the app shows it: TEN +7.5 or CIN -7.5")
    try:
        return float(t)
    except ValueError:
        raise ValueError(f"can't read spread line {text!r}") from None


def format_handicap(h: float) -> str:
    return "PK" if abs(h) < 1e-9 else f"{h:+g}"


@dataclass
class Game:
    home: str
    away: str
    kickoff: datetime  # timezone-aware, UTC
    source: str
    source_id: str = ""
    ml: list = field(default_factory=list)       # (book, fair P(home wins | no tie))
    spreads: list = field(default_factory=list)  # (book, s, fair P(home margin > s | no push)); s > 0 = home favored
    totals: list = field(default_factory=list)   # (book, line, fair P(total > line | no push))
    live: bool = False          # kicked off and not final
    live_priced: bool = False   # the prices are in-game prices
    updated: datetime | None = None  # newest sportsbook update seen for this game
    sharp_books: tuple = ()     # before kickoff, price from these books when they quote the line

    def pick(self, quotes: list) -> tuple:
        """(quotes to price from, note). Sharp books win before kickoff; live, every book counts."""
        if not quotes:
            return quotes, ""
        if self.sharp_books and not self.live:
            sharp = [q for q in quotes if q[0].replace(" alt", "") in self.sharp_books]
            if sharp:
                names = sorted({q[0].replace(" alt", "") for q in sharp})
                rest = len(quotes) - len(sharp)
                return sharp, f"sharp book {', '.join(names)}" + (f"; {rest} other quotes ignored" if rest else "")
            return quotes, f"{_books_note(len(quotes))}, no sharp-book price"
        return quotes, _books_note(len(quotes))

    @property
    def home_abbr(self) -> str:
        return abbr_for_name(self.home) or self.home

    @property
    def away_abbr(self) -> str:
        return abbr_for_name(self.away) or self.away

    @property
    def label(self) -> str:
        return f"{self.away_abbr} @ {self.home_abbr}"

    @property
    def key(self) -> str:
        """Stable id shared by every data source, e.g. '2026-11-01 BAL@BUF' (Eastern date)."""
        return f"{utc_to_eastern(self.kickoff).date().isoformat()} {self.away_abbr}@{self.home_abbr}"

    @property
    def books(self) -> list:
        names = {q[0] for q in self.ml} | {q[0] for q in self.spreads} | {q[0] for q in self.totals}
        return sorted({n.replace(" alt", "") for n in names})

    def side_of(self, abbr: str) -> str | None:
        if abbr == self.home_abbr:
            return "home"
        if abbr == self.away_abbr:
            return "away"
        return None


@dataclass
class Fair:
    prob: float  # probability that YES wins
    basis: str   # "market": straight from sportsbook prices; "model": score model; "interpolated": between two live lines
    note: str = ""


def _main_quotes(quotes: list) -> list:
    main = [q for q in quotes if not q[0].endswith(" alt")]
    return main or quotes


def margin_mu(game: Game, models: NFLModels) -> float | None:
    mus = [models.margin.solve_mu(s, p) for _, s, p in game.pick(_main_quotes(game.spreads))[0]]
    if mus:
        return median(mus)
    if game.ml:
        return models.margin.solve_mu(0.0, median(p for _, p in game.pick(game.ml)[0]))
    return None


def total_mu(game: Game, models: NFLModels) -> float | None:
    mus = [models.total.solve_mu(line, p) for _, line, p in game.pick(_main_quotes(game.totals))[0]]
    return median(mus) if mus else None


def _books_note(n: int) -> str:
    return f"{n} book quote{'s' if n != 1 else ''}"


def _gap_note(target: float, lines: list) -> str:
    if not lines:
        return "model only"
    gap = min(abs(target - x) for x in lines)
    return f"{gap:g} pts from nearest book line"


def _check_live(game: Game) -> None:
    if game.live and not game.live_priced:
        raise NoMarketData(f"{game.label} is in progress and these are pre-game lines. Live prices need an "
                           "Odds API key (odds_api_key in your settings).")


def _prob_at_least(game: Game, models: NFLModels, kind: str, k: int) -> Fair:
    """P(home margin >= k) or P(total >= k), from book quotes, the model, or nearby live lines."""
    quotes = game.spreads if kind == "margin" else game.totals
    model = models.margin if kind == "margin" else models.total
    half, note = game.pick([q for q in quotes if abs(q[1] - (k - 0.5)) < 1e-9])
    if half:
        return Fair(median(q[2] for q in half), "market", note)
    mu = None
    if not game.live:
        mu = margin_mu(game, models) if kind == "margin" else total_mu(game, models)
    whole, note = game.pick([q for q in quotes if abs(q[1] - (k - 1)) < 1e-9])
    if whole and mu is not None:  # a whole-number book line refunds pushes; take the push chance out
        return Fair(median(q[2] for q in whole) * (1.0 - model.prob_equal(mu, k - 1)), "market", note)
    if not game.live:
        if mu is None:
            raise NoMarketData(f"no {'spread or moneyline' if kind == 'margin' else 'total'} odds for {game.label}")
        return Fair(model.prob_greater(mu, k - 0.5), "model", _gap_note(k - 0.5, [s for _, s, _ in quotes]))
    points: dict = {}
    for _, s, p in quotes:
        if abs(s - round(s)) > 1e-9:
            points.setdefault(s, []).append(p)
    target = k - 0.5
    below = max((s for s in points if s < target), default=None)
    above = min((s for s in points if s > target), default=None)
    if below is not None and above is not None and above - below <= MAX_INTERPOLATION_GAP:
        p_below, p_above = median(points[below]), median(points[above])
        p = p_below + (p_above - p_below) * (target - below) / (above - below)
        return Fair(p, "interpolated", f"between live lines {below:g} and {above:g}")
    raise NoMarketData(f"no live sportsbook line near this one for {game.label} right now")


def fair_probability(game: Game, models: NFLModels, contract: str, team: str | None = None,
                     line: float | None = None) -> Fair:
    contract = normalize_contract(contract)
    _check_live(game)
    side = None
    if contract in ("win", "spread"):
        side = game.side_of(team or "")
        if side is None:
            raise ValueError(f"{team} is not playing in {game.label}")
    if contract in ("spread", "total") and line is None:
        raise ValueError(f"a {contract} contract needs a line")

    if contract == "win":
        if game.live:
            if not game.ml:
                raise NoMarketData(f"no live moneyline for {game.label} right now")
            p_home, p_tie = median(p for _, p in game.ml), DEFAULT_TIE_PROB
            basis, note = "market", _books_note(len(game.ml))
        else:
            mu = margin_mu(game, models)
            p_tie = models.margin.prob_equal(mu, 0) if mu is not None else DEFAULT_TIE_PROB
            if game.ml:
                ml, note = game.pick(game.ml)
                p_home = median(p for _, p in ml)
                basis = "market"
            elif mu is not None:
                p_home = models.margin.prob_over_no_push(mu, 0)
                basis, note = "model", "from the spread; no moneyline quoted"
            else:
                raise NoMarketData(f"no odds for {game.label}")
        p_side = p_home if side == "home" else 1.0 - p_home
        return Fair(p_side * (1.0 - p_tie), basis, note)

    if contract == "spread":
        h = float(line)
        if side == "home":   # YES when home margin > -h
            return _prob_at_least(game, models, "margin", math.floor(-h) + 1)
        at_least = _prob_at_least(game, models, "margin", math.ceil(h))  # YES when home margin < h
        return Fair(1.0 - at_least.prob, at_least.basis, at_least.note)

    return _prob_at_least(game, models, "total", math.floor(float(line)) + 1)


def prob_at_least(game: Game, models: NFLModels, kind: str, k: int) -> Fair:
    """P(home margin >= k) or P(total >= k). Margins of 1 and 0 come from the moneyline when it's quoted."""
    _check_live(game)
    if kind == "margin" and k in (0, 1) and game.ml:
        if k == 1:
            return fair_probability(game, models, "win", game.home_abbr)
        away = fair_probability(game, models, "win", game.away_abbr)
        return Fair(1.0 - away.prob, away.basis, away.note)
    return _prob_at_least(game, models, kind, k)


@dataclass
class Consensus:
    p_home: float | None
    p_away: float | None
    favorite: str | None   # abbreviation of the spread favorite, None for a pick'em
    spread: float | None   # points the favorite gives
    total: float | None
    books: int


def consensus(game: Game, models: NFLModels) -> Consensus:
    try:
        p_home = fair_probability(game, models, "win", game.home_abbr).prob
        p_away = fair_probability(game, models, "win", game.away_abbr).prob
    except NoMarketData:
        p_home = p_away = None
    favorite = spread = None
    main_spreads = game.pick(_main_quotes(game.spreads))[0]
    if main_spreads:
        s = math.floor(median(q[1] for q in main_spreads) * 2 + 0.5) / 2  # nearest half point
        if s > 0:
            favorite, spread = game.home_abbr, s
        elif s < 0:
            favorite, spread = game.away_abbr, -s
        else:
            spread = 0.0
    main_totals = game.pick(_main_quotes(game.totals))[0]
    total = math.floor(median(q[1] for q in main_totals) * 2 + 0.5) / 2 if main_totals else None
    return Consensus(p_home, p_away, favorite, spread, total, len(game.books))


def describe_contract(contract: str, team: str | None, line: float | None) -> str:
    contract = normalize_contract(contract)
    if contract == "win":
        return f"{team} win"
    if contract == "spread":
        return f"{team} {format_handicap(line)}"
    return f"Over {line:g}"


def describe_side(contract: str, team: str | None, line: float | None, side: str) -> str:
    """'YES TEN +7.5', 'NO BUF win', 'Over 47.5' / 'Under 47.5'."""
    if normalize_contract(contract) == "total":
        return f"{'Over' if side == 'YES' else 'Under'} {line:g}"
    return f"{side} {describe_contract(contract, team, line)}"


# ---------------------------------------------------------------- data sources

def _is_blank(value) -> bool:
    return value is None or str(value).strip() in ("", "NA", "NaN", "nan", "None")


def _team_code(text: str) -> str:
    """nflverse codes pass through; hand-entered names like 'Rams' or 'LAR' become 'LA'."""
    code = str(text).strip()
    if full_name(code):
        return code.upper()
    try:
        return lookup_team(code)
    except ValueError:
        return code


def game_from_nflverse_row(row: dict, devig: str = "power") -> Game | None:
    """One row of nflverse games.csv, or a hand-made file in the same format."""
    try:
        home_code, away_code = _team_code(row["home_team"]), _team_code(row["away_team"])
        home = full_name(home_code) or home_code
        away = full_name(away_code) or away_code
        clock = row.get("gametime") or "13:00"
        if _is_blank(clock):
            clock = "13:00"
        kickoff = eastern_to_utc(datetime.strptime(f"{row['gameday']} {clock}", "%Y-%m-%d %H:%M"))
    except (KeyError, ValueError):
        return None
    game = Game(home, away, kickoff, "nflverse", row.get("game_id", ""))

    def odds(value, default=-110):
        return american_to_prob(default if _is_blank(value) else value)

    try:
        if not _is_blank(row.get("home_moneyline")) and not _is_blank(row.get("away_moneyline")):
            game.ml.append(("nflverse", devig_two_way(odds(row["home_moneyline"]), odds(row["away_moneyline"]), devig)))
    except ValueError:
        pass
    try:
        if not _is_blank(row.get("spread_line")):
            s = float(row["spread_line"])
            p = devig_two_way(odds(row.get("home_spread_odds")), odds(row.get("away_spread_odds")), devig)
            game.spreads.append(("nflverse", s, p))
    except ValueError:
        pass
    try:
        if not _is_blank(row.get("total_line")):
            t = float(row["total_line"])
            p = devig_two_way(odds(row.get("over_odds")), odds(row.get("under_odds")), devig)
            game.totals.append(("nflverse", t, p))
    except ValueError:
        pass
    return game


def games_from_nflverse(rows: list, devig: str = "power", now: datetime | None = None,
                        until: datetime | None = None) -> list:
    """Upcoming games, plus games in progress (flagged live; their pre-game lines can't price them)."""
    games = []
    for row in rows:
        if not _is_blank(row.get("result")):
            continue  # already played
        game = game_from_nflverse_row(row, devig)
        if game is None or not game.books:
            continue
        if now is not None and game.kickoff <= now:
            if game.kickoff <= now - LIVE_WINDOW:
                continue
            game.live = True
        if until is not None and game.kickoff > until:
            continue
        games.append(game)
    return sorted(games, key=lambda g: (g.kickoff, g.label))


def _find_outcome(outcomes: list, name: str) -> dict | None:
    for o in outcomes:
        if str(o.get("name", "")).strip().lower() == name.strip().lower():
            return o
    return None


def add_bookmaker_markets(game: Game, bookmakers: list, devig: str = "power") -> None:
    """Add moneyline, spread and total quotes (main and alternate lines) from Odds API bookmakers."""
    for bookmaker in bookmakers or []:
        book = bookmaker.get("key") or bookmaker.get("title") or "book"
        for market in bookmaker.get("markets", []) or []:
            outs = market.get("outcomes", []) or []
            key = market.get("key")
            tag = f"{book} alt" if str(key).startswith("alternate_") else book
            try:
                if market.get("last_update"):
                    seen = parse_iso_utc(market["last_update"])
                    game.updated = seen if game.updated is None or seen > game.updated else game.updated
                if key == "h2h" and len(outs) == 2:
                    h, a = _find_outcome(outs, game.home), _find_outcome(outs, game.away)
                    if h and a:
                        game.ml.append((book, devig_two_way(price_to_prob(h["price"]), price_to_prob(a["price"]), devig)))
                elif key in ("spreads", "alternate_spreads"):
                    homes = [o for o in outs if str(o.get("name", "")).lower() == game.home.lower()]
                    aways = [o for o in outs if str(o.get("name", "")).lower() == game.away.lower()]
                    for h in homes:
                        a = next((o for o in aways if abs(float(o["point"]) + float(h["point"])) < 1e-9), None)
                        if a:
                            p = devig_two_way(price_to_prob(h["price"]), price_to_prob(a["price"]), devig)
                            game.spreads.append((tag, -float(h["point"]), p))
                elif key in ("totals", "alternate_totals"):
                    overs = [o for o in outs if str(o.get("name", "")).lower() == "over"]
                    unders = [o for o in outs if str(o.get("name", "")).lower() == "under"]
                    for o in overs:
                        u = next((x for x in unders if abs(float(x["point"]) - float(o["point"])) < 1e-9), None)
                        if u:
                            p = devig_two_way(price_to_prob(o["price"]), price_to_prob(u["price"]), devig)
                            game.totals.append((tag, float(o["point"]), p))
            except (KeyError, TypeError, ValueError):
                continue


def games_from_odds_api(events: list, devig: str = "power", now: datetime | None = None,
                        until: datetime | None = None) -> list:
    """Events from The Odds API v4 /sports/americanfootball_nfl/odds: upcoming games and games in progress."""
    games = []
    for ev in events:
        try:
            kickoff = parse_iso_utc(ev["commence_time"])
            game = Game(ev["home_team"], ev["away_team"], kickoff, "odds-api", ev.get("id", ""))
        except (KeyError, ValueError, TypeError):
            continue
        if now is not None and kickoff <= now:
            if kickoff <= now - LIVE_WINDOW:
                continue
            game.live = game.live_priced = True
        if until is not None and kickoff > until:
            continue
        add_bookmaker_markets(game, ev.get("bookmakers", []), devig)
        if game.books:
            games.append(game)
    return sorted(games, key=lambda g: (g.kickoff, g.label))


# ==================== sources =================================================

import csv
import json
import ssl
import time as _time
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlsplit
from urllib.request import Request, urlopen


NFLVERSE_GAMES_URL = "https://raw.githubusercontent.com/nflverse/nfldata/master/data/games.csv"
ODDS_API_NFL_URL = "https://api.the-odds-api.com/v4/sports/americanfootball_nfl/odds"


class SourceError(Exception):
    """A data source could not be reached or returned something unusable."""


def http_get(url: str, params: dict | None = None, timeout: float = 30.0) -> tuple:
    full = url + ("?" + urlencode(params) if params else "")
    host = urlsplit(url).netloc
    request = Request(full, headers={"User-Agent": f"dk-predictions-analyzer/{__version__}"})
    try:
        with urlopen(request, timeout=timeout) as response:
            return response.read(), {k.lower(): v for k, v in response.headers.items()}
    except HTTPError as err:
        detail = err.read()[:300].decode("utf-8", "replace")
        if host.endswith("the-odds-api.com"):
            if err.code == 401:
                raise SourceError("The Odds API rejected the key. Check odds_api_key in config.json.") from None
            if err.code == 429:
                raise SourceError("The Odds API says you're out of credits or sending requests too fast.") from None
        raise SourceError(f"{host} answered HTTP {err.code}: {detail}") from None
    except URLError as err:
        reason = err.reason
        if isinstance(reason, ssl.SSLCertVerificationError) or "CERTIFICATE_VERIFY_FAILED" in str(reason):
            raise SourceError(
                f"Could not verify {host}'s security certificate. On a Mac, open your Python folder in "
                "Applications and run 'Install Certificates.command', then try again."
            ) from None
        raise SourceError(f"Could not reach {host}: {reason}") from None
    except (TimeoutError, OSError) as err:
        raise SourceError(f"Could not reach {host}: {err}") from None


def _age_minutes(path: Path) -> float:
    return (_time.time() - path.stat().st_mtime) / 60.0


def _stamp(path: Path) -> str:
    return datetime.fromtimestamp(path.stat().st_mtime).strftime("%I:%M %p").lstrip("0")


def load_nflverse_rows(cache_dir: Path, max_age_minutes: float = 60, refresh: bool = False,
                       local_file: Path | None = None) -> tuple:
    """Rows of nflverse games.csv and a short description of where they came from."""
    if local_file:
        path = Path(local_file)
        desc = f"lines file {path.name}"
    else:
        cache_dir.mkdir(parents=True, exist_ok=True)
        path = cache_dir / "nflverse_games.csv"
        if refresh or not path.exists() or _age_minutes(path) > max_age_minutes:
            try:
                body, _ = http_get(NFLVERSE_GAMES_URL, timeout=60)
                if not body.startswith(b"game_id"):
                    raise SourceError("nflverse returned an unexpected file")
                path.write_bytes(body)
            except SourceError:
                if not path.exists():
                    raise
                # Fall back to the cached copy; say how old it is.
        desc = f"nflverse consensus lines (downloaded {_stamp(path)})"
    with open(path, newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    return rows, desc


def _has_live(events: list, now: datetime) -> bool:
    for ev in events:
        try:
            if datetime.fromisoformat(str(ev["commence_time"]).replace("Z", "+00:00")) <= now:
                return True
        except (KeyError, ValueError):
            continue
    return False


def _odds_api_get(url: str, params: dict) -> tuple:
    body, headers = http_get(url, params)
    try:
        data = json.loads(body)
    except json.JSONDecodeError:
        raise SourceError("The Odds API returned something that isn't JSON") from None
    credits = f"{headers.get('x-requests-remaining', '?')} credits left, this call used {headers.get('x-requests-last', '?')}"
    return data, credits


def _scope(params: dict, regions: str, bookmakers: str) -> dict:
    if bookmakers:
        params["bookmakers"] = bookmakers
    else:
        params["regions"] = regions
    return params


def fetch_odds_api_events(api_key: str, cache_dir: Path, regions: str = "us", bookmakers: str = "",
                          max_age_minutes: float = 10, refresh: bool = False,
                          local_file: Path | None = None, live_max_age_seconds: float = 20) -> tuple:
    """Upcoming and in-progress NFL games with moneyline, spread and total prices from The Odds API.

    The cache is kept for max_age_minutes, but only live_max_age_seconds while any game is in progress.
    """
    if local_file:
        return json.loads(Path(local_file).read_text(encoding="utf-8")), f"Odds API file {Path(local_file).name}"
    if not api_key:
        raise SourceError("No Odds API key. Add odds_api_key to your settings or use --source nflverse.")
    cache_dir.mkdir(parents=True, exist_ok=True)
    tag = (bookmakers or regions).replace(",", "-")
    path = cache_dir / f"odds_api_nfl_{tag}.json"
    now = datetime.now(timezone.utc)
    if not refresh and path.exists():
        cached = json.loads(path.read_text(encoding="utf-8"))
        limit = live_max_age_seconds / 60.0 if _has_live(cached["events"], now) else max_age_minutes
        if _age_minutes(path) <= limit:
            return cached["events"], f"The Odds API ({_stamp(path)}, cached; {cached.get('credits', '')})"
    params = _scope({"apiKey": api_key, "markets": "h2h,spreads,totals", "oddsFormat": "decimal",
                     "dateFormat": "iso"}, regions, bookmakers)
    events, credits = _odds_api_get(ODDS_API_NFL_URL, params)
    if not isinstance(events, list):
        raise SourceError(f"The Odds API returned an error: {str(events)[:200]}")
    path.write_text(json.dumps({"fetched_at": now.isoformat(), "credits": credits, "events": events}),
                    encoding="utf-8")
    return events, f"The Odds API ({_stamp(path)}; {credits})"


def fetch_event_odds(api_key: str, cache_dir: Path, event_id: str, markets: list, regions: str = "us",
                     bookmakers: str = "", max_age_seconds: float = 60, refresh: bool = False,
                     local_file: Path | None = None) -> tuple:
    """One game's extra markets (alternate lines, player props). Costs one credit per market returned.

    Returns (event JSON, credits note). local_file is a JSON list of event responses, for tests.
    """
    if local_file:
        saved = json.loads(Path(local_file).read_text(encoding="utf-8"))
        event = next((e for e in (saved if isinstance(saved, list) else [saved]) if e.get("id") == event_id), None)
        if event is None:
            return {"id": event_id, "bookmakers": []}, "saved file"
        wanted = set(markets)
        event = dict(event)
        event["bookmakers"] = [dict(b, markets=[m for m in b.get("markets", []) if m.get("key") in wanted])
                               for b in event.get("bookmakers", [])]
        return event, "saved file"
    if not api_key:
        raise SourceError("Player props and alternate lines need an Odds API key (odds_api_key in your settings).")
    cache_dir.mkdir(parents=True, exist_ok=True)
    tag = "-".join(sorted(markets)) + "_" + (bookmakers or regions).replace(",", "-")
    path = cache_dir / f"event_{event_id}_{tag}.json"
    if not refresh and path.exists() and _age_minutes(path) * 60.0 <= max_age_seconds:
        cached = json.loads(path.read_text(encoding="utf-8"))
        return cached["event"], "cached"
    params = _scope({"apiKey": api_key, "markets": ",".join(markets), "oddsFormat": "decimal",
                     "dateFormat": "iso"}, regions, bookmakers)
    url = f"{ODDS_API_NFL_URL.rsplit('/odds', 1)[0]}/events/{event_id}/odds"
    event, credits = _odds_api_get(url, params)
    if not isinstance(event, dict):
        raise SourceError(f"The Odds API returned an error: {str(event)[:200]}")
    path.write_text(json.dumps({"fetched_at": datetime.now(timezone.utc).isoformat(), "event": event}),
                    encoding="utf-8")
    return event, credits


# ==================== props ===================================================

import re
from dataclasses import dataclass
from statistics import median


PROP_MARKETS = {
    "anytime td": "player_anytime_td", "anytime touchdown": "player_anytime_td", "atd": "player_anytime_td",
    "anytime td scorer": "player_anytime_td", "td scorer": "player_anytime_td", "td": "player_anytime_td",
    "touchdown": "player_anytime_td", "anytime": "player_anytime_td",
    "first td": "player_1st_td", "1st td": "player_1st_td", "first td scorer": "player_1st_td",
    "first touchdown": "player_1st_td", "ftd": "player_1st_td",
    "last td": "player_last_td", "last td scorer": "player_last_td", "last touchdown": "player_last_td",
    "pass yds": "player_pass_yds", "pass yards": "player_pass_yds", "passing yards": "player_pass_yds",
    "passing yds": "player_pass_yds",
    "pass tds": "player_pass_tds", "passing tds": "player_pass_tds", "passing touchdowns": "player_pass_tds",
    "pass touchdowns": "player_pass_tds",
    "pass completions": "player_pass_completions", "completions": "player_pass_completions",
    "pass attempts": "player_pass_attempts", "passing attempts": "player_pass_attempts",
    "interceptions": "player_pass_interceptions", "pass interceptions": "player_pass_interceptions",
    "ints": "player_pass_interceptions", "interceptions thrown": "player_pass_interceptions",
    "rush yds": "player_rush_yds", "rush yards": "player_rush_yds", "rushing yards": "player_rush_yds",
    "rushing yds": "player_rush_yds",
    "rush attempts": "player_rush_attempts", "rushing attempts": "player_rush_attempts", "carries": "player_rush_attempts",
    "receptions": "player_receptions", "catches": "player_receptions",
    "rec yds": "player_reception_yds", "receiving yards": "player_reception_yds", "receiving yds": "player_reception_yds",
    "reception yards": "player_reception_yds", "rec yards": "player_reception_yds",
    "rush rec yds": "player_rush_reception_yds", "rush rec yards": "player_rush_reception_yds",
    "rushing receiving yards": "player_rush_reception_yds", "scrimmage yards": "player_rush_reception_yds",
    "rush and rec yds": "player_rush_reception_yds", "rushing and receiving yards": "player_rush_reception_yds",
}
YES_NO_MARKETS = {"player_anytime_td", "player_1st_td", "player_last_td"}
LABELS = {
    "player_anytime_td": "anytime TD", "player_1st_td": "first TD", "player_last_td": "last TD",
    "player_pass_yds": "pass yds", "player_pass_tds": "pass TDs", "player_pass_completions": "completions",
    "player_pass_attempts": "pass attempts", "player_pass_interceptions": "interceptions",
    "player_rush_yds": "rush yds", "player_rush_attempts": "rush attempts", "player_receptions": "receptions",
    "player_reception_yds": "rec yds", "player_rush_reception_yds": "rush+rec yds",
}


def normalize_market(text: str) -> str:
    key = re.sub(r"[^a-z0-9 ]", " ", str(text).lower().replace("+", " "))
    key = re.sub(r"\s+", " ", key).strip()
    if key in PROP_MARKETS:
        return PROP_MARKETS[key]
    if key.startswith("player_") and key in LABELS:
        return key
    raise ValueError(f"unknown prop {text!r}; try: anytime td, first td, pass yds, pass tds, rush yds, "
                     "receptions, rec yds, rush rec yds, completions, interceptions")


def alternate_key(market: str) -> str | None:
    return None if market in YES_NO_MARKETS else f"{market}_alternate"


def describe_prop(player: str, market: str, line: float | None, side: str = "YES") -> str:
    label = LABELS.get(market, market)
    if market in YES_NO_MARKETS:
        return f"{side} {player} {label}"
    return f"{player} {label} {'over' if side == 'YES' else 'under'} {line:g}"


@dataclass
class PropQuote:
    book: str
    player: str
    point: float | None
    p_yes: float      # fair chance of Yes / Over at this point
    two_way: bool     # both sides quoted, so the margin was removed exactly


def prop_quotes(event: dict, market: str, devig: str = "power", one_way_margin: float = 0.08) -> list:
    """Quotes for one prop market (and its alternate lines) from an Odds API event-odds response."""
    yes_name, no_name = ("yes", "no") if market in YES_NO_MARKETS else ("over", "under")
    quotes = []
    for bookmaker in event.get("bookmakers", []) or []:
        book = bookmaker.get("key") or bookmaker.get("title") or "book"
        for mk in bookmaker.get("markets", []) or []:
            key = str(mk.get("key", ""))
            if key not in (market, f"{market}_alternate"):
                continue
            groups: dict = {}
            for o in mk.get("outcomes", []) or []:
                try:
                    point = float(o["point"]) if o.get("point") is not None else None
                    groups.setdefault((str(o.get("description") or "").strip(), point), {})[
                        str(o.get("name", "")).strip().lower()] = price_to_prob(o["price"])
                except (KeyError, TypeError, ValueError):
                    continue
            for (player, point), sides in groups.items():
                if not player:
                    continue
                if yes_name in sides and no_name in sides:
                    quotes.append(PropQuote(book, player, point, devig_two_way(sides[yes_name], sides[no_name], devig), True))
                elif yes_name in sides:
                    quotes.append(PropQuote(book, player, point, min(sides[yes_name] / (1.0 + one_way_margin), 0.99), False))
    return quotes


def _norm_name(name: str) -> str:
    words = re.sub(r"[^a-z ]", " ", str(name).lower().replace("'", "").replace(".", " ")).split()
    return " ".join(w for w in words if w not in ("jr", "sr", "ii", "iii", "iv", "v"))


def match_player(query: str, names: set) -> str:
    q = _norm_name(query)
    if not q:
        raise ValueError("player name is blank")
    qw = q.split()
    norm = {n: _norm_name(n) for n in names}

    def last(v: str) -> str:
        return v.split()[-1] if v else ""

    tests = (
        lambda v: v == q,                                                     # full name
        lambda v: len(qw) == 1 and last(v) == qw[0],                          # last name only
        lambda v: len(qw) == 2 and len(qw[0]) == 1 and v.startswith(qw[0]) and last(v) == qw[1],  # "J Gibbs"
        lambda v: q in v,                                                     # part of the name
    )
    for test in tests:
        hits = sorted(n for n, v in norm.items() if v and test(v))
        if len(hits) == 1:
            return hits[0]
        if len(hits) > 1:
            raise ValueError(f"{query!r} could be {', '.join(hits)}; use the full name")
    raise LookupError(f"no prices for a player called {query!r}")


def fair_prop(quotes: list, player: str, market: str, line: float | None, sharp: tuple = ()) -> tuple:
    """(Fair for the YES/Over side, the player's name as the books write it)."""
    label = LABELS.get(market, market)
    if not quotes:
        raise NoMarketData(f"no {label} prices for this game right now")
    name = match_player(player, {q.player for q in quotes})
    mine = [q for q in quotes if q.player == name]
    if market in YES_NO_MARKETS:
        return _pick(mine, f"{label} prices", sharp), name
    if line is None:
        raise ValueError(f"{label} needs a line, e.g. 249.5 or 250+")
    # Stats are whole numbers, so "more than 249" and "more than 249.5" are the same bet.
    target = (line // 1) + 0.5
    exact = [q for q in mine if q.point is not None and abs(q.point - target) < 1e-9]
    if exact:
        return _pick(exact, "prices at this line", sharp), name
    by_point: dict = {}
    for q in mine:
        if q.point is not None and abs(q.point - round(q.point)) > 1e-9:
            by_point.setdefault(q.point, []).append(q)
    below = max((p for p in by_point if p < target), default=None)
    above = min((p for p in by_point if p > target), default=None)
    if below is None or above is None:
        quoted = ", ".join(f"{p:g}" for p in sorted(by_point)) or "none"
        raise NoMarketData(f"no book quotes {name} {label} near {line:g} (quoted lines: {quoted})")
    f_below, f_above = _pick(by_point[below], "", sharp), _pick(by_point[above], "", sharp)
    p = f_below.prob + (f_above.prob - f_below.prob) * (target - below) / (above - below)
    return Fair(p, "interpolated", f"between book lines {below:g} and {above:g}"), name


def _pick(quotes: list, what: str, sharp: tuple = ()) -> Fair:
    sharp_two = [q.p_yes for q in quotes if q.two_way and q.book in sharp]
    if sharp_two:
        return Fair(median(sharp_two), "market", f"sharp book {', '.join(sorted({q.book for q in quotes if q.two_way and q.book in sharp}))}")
    two = [q.p_yes for q in quotes if q.two_way]
    if two:
        return Fair(median(two), "market", f"{len(two)} two-sided {what}".strip())
    one = [q.p_yes for q in quotes]
    return Fair(median(one), "one-way", f"{len(one)} one-sided {what}; bookmaker margin estimated".replace("  ", " "))


# ==================== extras ==================================================

from pathlib import Path



class OddsExtras:
    def __init__(self, cfg: dict, cache_dir: Path, refresh: bool = False, local_file: Path | None = None):
        self.cfg = cfg
        self.cache_dir = cache_dir
        self.refresh = refresh
        self.local_file = local_file
        self.notes: list = []
        self._alternates_loaded: set = set()
        self._props: dict = {}

    @property
    def available(self) -> bool:
        return bool(self.cfg.get("odds_api_key") or self.local_file)

    def _event(self, game: Game, markets: list) -> dict:
        if game.source != "odds-api" or not game.source_id:
            raise NoMarketData("alternate lines and player props need games from The Odds API "
                               "(set odds_api_key in your settings)")
        max_age = self.cfg["live_cache_seconds"] if game.live else self.cfg["odds_cache_minutes"] * 60
        event, credits = fetch_event_odds(self.cfg["odds_api_key"], self.cache_dir, game.source_id, markets,
                                          self.cfg["regions"], self.cfg["bookmakers"], max_age, self.refresh,
                                          self.local_file)
        if credits not in ("cached", "saved file"):
            self.notes.append(f"Odds API {game.label} {', '.join(markets)}: {credits}")
        return event

    def load_alternates(self, game: Game) -> bool:
        """Add every alternate spread and total the books list for this game. True if any were added."""
        if not self.available or game.source != "odds-api" or game.key in self._alternates_loaded:
            return False
        self._alternates_loaded.add(game.key)
        before = len(game.spreads) + len(game.totals)
        event = self._event(game, ["alternate_spreads", "alternate_totals"])
        add_bookmaker_markets(game, event.get("bookmakers", []), self.cfg["devig_method"])
        return len(game.spreads) + len(game.totals) > before

    def prop_quotes(self, game: Game, market: str) -> list:
        key = (game.key, market)
        if key not in self._props:
            if not self.available:
                raise NoMarketData("player props need an Odds API key (odds_api_key in your settings)")
            markets = [market] + ([alternate_key(market)] if alternate_key(market) else [])
            event = self._event(game, markets)
            self._props[key] = prop_quotes(event, market, self.cfg["devig_method"], self.cfg["prop_one_way_margin"])
        return self._props[key]

    def prop_fair(self, game: Game, player: str, market: str, line: float | None) -> tuple:
        if game.live and not game.live_priced:
            raise NoMarketData(f"{game.label} is in progress; live props need an Odds API key")
        sharp = () if game.live else game.sharp_books
        return fair_prop(self.prop_quotes(game, market), player, market, line, sharp)


def game_fair(game: Game, models: NFLModels, contract: str, team: str | None, line: float | None,
              extras: OddsExtras | None) -> Fair:
    """fair_probability, fetching the game's alternate lines when the main lines don't cover this one."""
    contract = normalize_contract(contract)
    try:
        fair = fair_probability(game, models, contract, team, line)
        if fair.basis == "market" or contract == "win":
            return fair
    except NoMarketData:
        if extras is None or contract == "win" or not extras.load_alternates(game):
            raise
        return fair_probability(game, models, contract, team, line)
    if extras is not None and extras.load_alternates(game):
        return fair_probability(game, models, contract, team, line)
    return fair


# ==================== scan ====================================================

import csv
import re
from dataclasses import dataclass
from pathlib import Path


PRICE_COLUMNS = ["kickoff", "game", "contract", "team", "player", "market", "line", "yes_price", "no_price", "notes"]
PROP_WORDS = ("prop", "props", "player", "player prop")


@dataclass
class Opportunity:
    game: Game
    contract: str            # win, spread, total or prop
    team: str | None
    line: float | None
    fair: Fair
    evaluation: TradeEvaluation
    threshold: float
    stake: float
    contracts: int
    player: str | None = None
    market: str | None = None

    @property
    def description(self) -> str:
        if self.contract == "prop":
            return describe_prop(self.player, self.market, self.line)
        return describe_contract(self.contract, self.team, self.line)

    @property
    def trade(self) -> str:
        """The side being bought, e.g. 'YES TEN +7.5', 'Under 47.5', 'YES Jahmyr Gibbs anytime TD'."""
        side = self.evaluation.side
        if self.contract == "prop":
            return describe_prop(self.player, self.market, self.line, side)
        return describe_side(self.contract, self.team, self.line, side)


def contract_kind(text: str) -> str:
    return "prop" if str(text).strip().lower() in PROP_WORDS else normalize_contract(text)


def parse_line(contract: str, value) -> float | None:
    """Spread lines keep their sign (+7.5 / -7.5 / PK); '250+' on a prop means more than 249.5."""
    text = str(value if value is not None else "").strip()
    if not text:
        return None
    if contract == "spread":
        return parse_spread_line(text)
    if contract == "prop" and text.endswith("+"):
        return float(text[:-1]) - 0.5
    return float(text.replace("+", ""))


def find_game(games: list, game_text: str | None = None, team: str | None = None) -> Game:
    """Match 'BAL @ BUF', 'Ravens at Bills', or a team (its game in progress, else its next game)."""
    if game_text and str(game_text).strip():
        parts = [p for p in re.split(r"\s*(?:@|\bat\b|\bvs\.?\b|\bv\b)\s*", str(game_text).strip(), flags=re.I) if p]
        if len(parts) == 2:
            a, b = lookup_team(parts[0]), lookup_team(parts[1])
            for g in games:
                if {g.away_abbr, g.home_abbr} == {a, b}:
                    return g
            raise LookupError(f"no game {a} vs {b} in progress or upcoming in the odds data")
        if len(parts) == 1 and not team:
            team = parts[0]
    if team:
        abbr = lookup_team(team)
        for g in games:  # sorted by kickoff, so a game in progress comes first
            if abbr in (g.home_abbr, g.away_abbr):
                return g
        raise LookupError(f"no game for {abbr} in progress or upcoming in the odds data")
    raise LookupError("say which game: e.g. 'BAL @ BUF' or a team name")


def max_price(prob: float, threshold: float, schedule) -> float | None:
    """Highest price (to the cent) that still leaves `threshold` edge after the fee."""
    for cents in range(99, 0, -1):
        price = cents / 100.0
        if prob - price - fee_for_price(price, schedule) >= threshold - 1e-9:
            return price
    return None


def edge_threshold(fair: Fair, cfg: dict) -> float:
    """Model-priced, interpolated and one-way prices are less certain, so they need more edge."""
    return cfg["min_edge"] + (cfg["model_extra_edge"] if fair.basis != "market" else 0.0)


def contract_fair(game: Game, models: NFLModels, contract: str, team: str | None, line: float | None,
                  extras: OddsExtras | None = None, player: str | None = None, market: str | None = None) -> tuple:
    """(Fair, player name as the books write it) for any contract."""
    if contract == "prop":
        if extras is None:
            raise NoMarketData("player props need an Odds API key (odds_api_key in your settings)")
        return extras.prop_fair(game, player, market, line)
    return game_fair(game, models, contract, team, line, extras), None


def evaluate_contract(game: Game, models: NFLModels, cfg: dict, contract: str, team: str | None,
                      line: float | None, yes_price: float | None, no_price: float | None,
                      extras: OddsExtras | None = None, player: str | None = None, market: str | None = None) -> list:
    contract = contract_kind(contract)
    fair, name = contract_fair(game, models, contract, team, line, extras, player, market)
    threshold = edge_threshold(fair, cfg)
    results = []
    for side, price, prob in (("YES", yes_price, fair.prob), ("NO", no_price, 1.0 - fair.prob)):
        if price is None:
            continue
        fee = fee_for_price(price, cfg["fee_schedule"])
        if price + fee >= 1.0:
            continue
        ev = evaluate_trade(side, price, prob, fee=fee, kelly_multiplier=cfg["kelly_multiplier"],
                            max_bankroll_fraction=cfg["max_bet_fraction"], min_edge=threshold)
        stake = ev.suggested_fraction * cfg["bankroll"]
        contracts = int(stake // ev.cost) if ev.cost > 0 else 0
        results.append(Opportunity(game, contract, team, line, fair, ev, threshold, stake, contracts,
                                   name or player, market))
    return results


def read_price_rows(path: Path) -> list:
    try:
        text = Path(path).read_text(encoding="utf-8-sig")
    except UnicodeDecodeError:  # saved by Excel on Windows
        text = Path(path).read_text(encoding="cp1252")
    rows = []
    for i, row in enumerate(csv.DictReader(text.splitlines()), start=2):
        clean = {str(k).strip().lower(): (v or "").strip() for k, v in row.items() if k is not None}
        clean["_line_no"] = i
        rows.append(clean)
    return rows


def evaluate_rows(rows: list, games: list, models: NFLModels, cfg: dict, extras: OddsExtras | None = None) -> tuple:
    """Evaluate every row that has a YES or NO price. Returns (opportunities, problems)."""
    opportunities, problems = [], []
    for row in rows:
        if not row.get("yes_price") and not row.get("no_price"):
            continue
        where = f"row {row['_line_no']}"
        try:
            contract = contract_kind(row.get("contract", ""))
            player = market = None
            if contract == "prop":
                if not row.get("player") or not row.get("market"):
                    raise ValueError("a prop row needs player and market columns")
                player, market, team = row["player"], normalize_market(row["market"]), None
            elif contract in ("win", "spread"):
                if not row.get("team"):
                    raise ValueError(f"{contract} needs a team")
                team = lookup_team(row["team"])
            else:
                team = None
            line = parse_line(contract, row.get("line"))
            if contract in ("spread", "total") and line is None:
                raise ValueError(f"{contract} needs a line")
            game = find_game(games, row.get("game"), row.get("team"))
            yes_price, no_price = parse_price(row.get("yes_price")), parse_price(row.get("no_price"))
            opportunities += evaluate_contract(game, models, cfg, contract, team, line, yes_price, no_price,
                                               extras, player, market)
        except (ValueError, LookupError, NoMarketData) as err:
            problems.append(f"{where}: {err}")
    opportunities.sort(key=lambda o: (o.evaluation.edge - o.threshold), reverse=True)
    return opportunities, problems


def template_rows(games: list, models: NFLModels) -> list:
    rows = []
    for g in games:
        if g.live and not g.live_priced:
            continue
        c = consensus(g, models)
        kickoff = "LIVE" if g.live else fmt_local(g.kickoff)
        rows.append([kickoff, g.label, "win", g.away_abbr, "", "", "", "", "", ""])
        rows.append([kickoff, g.label, "win", g.home_abbr, "", "", "", "", "", ""])
        if c.favorite:
            dog = g.away_abbr if c.favorite == g.home_abbr else g.home_abbr
            rows.append([kickoff, g.label, "spread", c.favorite, "", "", format_handicap(-c.spread), "", "", ""])
            rows.append([kickoff, g.label, "spread", dog, "", "", format_handicap(c.spread), "", "", ""])
        if c.total is not None:
            rows.append([kickoff, g.label, "total", "", "", "", num(c.total), "", "", ""])
    return rows


def write_template(path: Path, games: list, models: NFLModels, force: bool = False) -> int:
    path = Path(path)
    if path.exists() and not force:
        if any(r.get("yes_price") or r.get("no_price") for r in read_price_rows(path)):
            raise FileExistsError(f"{path.name} already has prices in it")
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = template_rows(games, models)
    with open(path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(PRICE_COLUMNS)
        writer.writerows(rows)
    return len(rows)


# ==================== journal =================================================

import csv
from datetime import datetime, timezone
from pathlib import Path


TRADE_COLUMNS = ["id", "logged_at", "game", "kickoff_utc", "live", "contract", "team", "player", "market", "line",
                 "side", "price", "fee", "contracts", "fair_prob", "basis", "status", "final_score", "pnl",
                 "close_fair", "closing_edge", "notes"]
AUTO_SETTLED = ("win", "spread", "total")


def read_trades(path: Path) -> list:
    path = Path(path)
    if not path.exists() or path.stat().st_size == 0:
        return []
    with open(path, newline="", encoding="utf-8") as fh:
        return [dict(r) for r in csv.DictReader(fh)]


def write_trades(path: Path, trades: list) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    with open(tmp, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=TRADE_COLUMNS, extrasaction="ignore")
        writer.writeheader()
        for t in trades:
            writer.writerow({k: t.get(k, "") for k in TRADE_COLUMNS})
    tmp.replace(path)


def _line_text(contract: str, line: float | None) -> str:
    if line is None:
        return ""
    return format_handicap(line) if contract == "spread" else f"{line:g}"


def log_trade(path: Path, game: Game | None, contract: str, team: str | None, line: float | None, side: str,
              price: float, fee: float, contracts: int, fair: Fair | None, notes: str = "",
              player: str | None = None, market: str | None = None) -> dict:
    """Record a trade. For a combo pass game=None and the legs in notes; fair is then the combo's fair chance."""
    trades = read_trades(path)
    next_id = max([int(t["id"]) for t in trades if str(t.get("id", "")).isdigit()] + [0]) + 1
    side = side.upper()
    fair_side = None
    if fair is not None:
        fair_side = fair.prob if side == "YES" else 1.0 - fair.prob
    trade = {
        "id": next_id,
        "logged_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M"),
        "game": game.key if game else "combo",
        "kickoff_utc": game.kickoff.strftime("%Y-%m-%d %H:%M") if game else "",
        "live": "yes" if game is not None and game.live else "",
        "contract": contract,
        "team": team or "",
        "player": player or "",
        "market": market or "",
        "line": _line_text(contract, line),
        "side": side,
        "price": f"{price:.2f}",
        "fee": f"{fee:.2f}",
        "contracts": int(contracts),
        "fair_prob": "" if fair_side is None else f"{fair_side:.4f}",
        "basis": "" if fair is None else fair.basis,
        "status": "open",
        "notes": notes,
    }
    trades.append(trade)
    write_trades(path, trades)
    return trade


def yes_wins(contract: str, team: str, line: float | None, home: str, away: str,
             home_score: int, away_score: int) -> bool:
    if contract == "total":
        return home_score + away_score > float(line)
    margin = home_score - away_score if team == home else away_score - home_score
    if contract == "win":
        return margin > 0
    return margin + float(line) > 0  # spread: the team's margin plus its handicap


def _game_index(nflverse_rows: list) -> dict:
    return {f"{r.get('gameday')} {r.get('away_team')}@{r.get('home_team')}": r for r in nflverse_rows}


def _pnl(t: dict, won: bool) -> float:
    price, fee, n = float(t["price"]), float(t["fee"] or 0), int(float(t["contracts"]))
    return n * (1.0 - price - fee) if won else -n * (price + fee)


def settle_trades(path: Path, nflverse_rows: list, models: NFLModels, devig: str = "power") -> tuple:
    """Fill in results for open win/spread/total trades whose games are final.

    Returns (newly settled, still open, open props/combos that need `result`)."""
    trades = read_trades(path)
    index = _game_index(nflverse_rows)
    settled, still_open, manual = [], 0, 0
    for t in trades:
        if t.get("status") != "open":
            continue
        if t.get("contract") not in AUTO_SETTLED:
            manual += 1
            continue
        row = index.get(t["game"])
        if row is None or str(row.get("result", "")).strip() in ("", "NA"):
            still_open += 1
            continue
        home_score, away_score = int(float(row["home_score"])), int(float(row["away_score"]))
        line = float(t["line"]) if t.get("line") not in (None, "") else None
        won_yes = yes_wins(t["contract"], t["team"], line, row["home_team"], row["away_team"], home_score, away_score)
        won = won_yes if t["side"] == "YES" else not won_yes
        t["status"] = "won" if won else "lost"
        t["final_score"] = f"{row['away_team']} {away_score} - {row['home_team']} {home_score}"
        t["pnl"] = f"{_pnl(t, won):.2f}"
        closing = game_from_nflverse_row(row, devig)
        if closing is not None and t.get("live") != "yes":
            try:
                p_yes = fair_probability(closing, models, t["contract"], t["team"] or None, line).prob
                close_side = p_yes if t["side"] == "YES" else 1.0 - p_yes
                t["close_fair"] = f"{close_side:.4f}"
                t["closing_edge"] = f"{close_side - float(t['price']) - float(t['fee'] or 0):.4f}"
            except (NoMarketData, ValueError):
                pass
        settled.append(t)
    write_trades(path, trades)
    return settled, still_open, manual


def set_result(path: Path, trade_id: str, outcome: str) -> dict:
    """Settle one trade by hand: won, lost, or void (refunded)."""
    outcome = outcome.lower()
    if outcome not in ("won", "lost", "void"):
        raise ValueError("result must be won, lost or void")
    trades = read_trades(path)
    for t in trades:
        if str(t.get("id")) == str(trade_id):
            t["status"] = outcome
            t["pnl"] = "0.00" if outcome == "void" else f"{_pnl(t, outcome == 'won'):.2f}"
            write_trades(path, trades)
            return t
    raise LookupError(f"no trade #{trade_id} in the journal")


def _f(t: dict, key: str) -> float | None:
    try:
        return float(t[key]) if str(t.get(key, "")).strip() else None
    except ValueError:
        return None


def _count(n: int) -> str:
    return f"{n} trade" if n == 1 else f"{n} trades"


def describe_trade(t: dict) -> str:
    line = float(t["line"]) if t.get("line") not in (None, "") else None
    if t.get("contract") == "combo":
        return f"Combo: {t.get('notes', '')}"
    if t.get("contract") == "prop":
        return describe_prop(t.get("player", ""), t.get("market", ""), line, t["side"])
    return describe_side(t["contract"], t.get("team") or None, line, t["side"])


def _cost(t: dict) -> float:
    return int(float(t["contracts"])) * (float(t["price"]) + float(t["fee"] or 0))


def report(trades: list) -> str:
    if not trades:
        return "No trades logged yet. Use the log command after you place one."
    out = []
    open_t = [t for t in trades if t.get("status") == "open"]
    done = [t for t in trades if t.get("status") in ("won", "lost")]
    if open_t:
        out.append(f"Open: {_count(len(open_t))}, {money(sum(_cost(t) for t in open_t))} at risk")
    if not done:
        out.append("No settled trades yet. Run the settle command after games finish "
                   "(props and combos: the result command).")
        return "\n".join(out)

    staked = sum(_cost(t) for t in done)
    pnl = sum(float(t["pnl"]) for t in done)
    wins = sum(1 for t in done if t["status"] == "won")
    out.append(f"Settled: {_count(len(done))}, {wins}-{len(done) - wins}, staked {money(staked)}, "
               f"profit {money(pnl)}, ROI {pct(pnl / staked if staked else 0)}")

    entry_edges = [(_f(t, "fair_prob") - float(t["price"]) - float(t["fee"] or 0)) for t in done
                   if _f(t, "fair_prob") is not None]
    if entry_edges:
        out.append(f"Average edge when you traded: {pct(sum(entry_edges) / len(entry_edges))}")
    closing = [_f(t, "closing_edge") for t in done if _f(t, "closing_edge") is not None]
    if closing:
        beat = sum(1 for c in closing if c > 0)
        out.append(f"Average closing edge (pre-game game lines): {pct(sum(closing) / len(closing))} "
                   f"(beat the closing line on {beat} of {len(closing)})")

    scored = [t for t in done if _f(t, "fair_prob") is not None]
    if scored:
        outcomes = [1 if t["status"] == "won" else 0 for t in scored]
        b_fair = brier_score([_f(t, "fair_prob") for t in scored], outcomes)
        b_price = brier_score([float(t["price"]) for t in scored], outcomes)
        out.append(f"Brier score (lower is better): fair odds {b_fair:.3f} vs DK price {b_price:.3f}")
    if len(done) < 100:
        out.append(f"Only {len(done)} settled trades: results this small are mostly luck. Watch closing edge.")

    by_type = {}
    for t in done:
        kind = t["contract"] + (" (live)" if t.get("live") == "yes" else "")
        s = by_type.setdefault(kind, [0, 0.0, 0.0])
        s[0] += 1
        s[1] += float(t["pnl"])
        s[2] += _cost(t)
    rows = [[k, v[0], money(v[1]), pct(v[1] / v[2] if v[2] else 0)] for k, v in sorted(by_type.items())]
    out.append("")
    out.append(table(["Contract", "Trades", "Profit", "ROI"], rows, right=(1, 2, 3)))
    return "\n".join(out)


# ==================== parlay ==================================================

import itertools
import math
import re
from dataclasses import dataclass, field


SIDE_WORDS = {"yes": "YES", "no": "NO", "over": "YES", "under": "NO"}


@dataclass
class Leg:
    game: Game
    contract: str               # win, spread, total or prop
    team: str | None
    line: float | None
    side: str = "YES"
    price: float | None = None  # the single contract's price in the app, when known
    player: str | None = None
    market: str | None = None
    fair: Fair | None = None    # this leg's own fair chance (YES side), once computed

    @property
    def description(self) -> str:
        if self.contract == "prop":
            return describe_prop(self.player, self.market, self.line, self.side)
        return describe_side(self.contract, self.team, self.line, self.side)

    @property
    def identity(self) -> tuple:
        return (self.game.key, self.contract, self.team, self.line, self.player, self.market)


@dataclass
class ParlayResult:
    legs: list
    prob: float
    leg_probs: list
    notes: list = field(default_factory=list)
    uses_model: bool = False


@dataclass
class ParlayPrice:
    price: float
    fee: float
    cost: float
    edge: float
    roi: float
    kelly: float
    stake: float
    contracts: int
    buy: bool


def _parse_prop_leg(text: str, games: list) -> Leg:
    parts = [p.strip() for p in text.split("|")]
    if len(parts) != 3 or not all(parts):
        raise ValueError(f"prop leg {text!r} should look like 'Jahmyr Gibbs | anytime td | MIN @ DET'")
    player, spec, where = parts
    side, line, words = "YES", None, []
    for word in spec.split():
        low = word.lower()
        if low in SIDE_WORDS:
            side = SIDE_WORDS[low]
        elif re.fullmatch(r"\d+(\.\d+)?\+", low):        # "250+" = more than 249.5
            line = float(low[:-1]) - 0.5
        elif re.fullmatch(r"\d+(\.\d+)?", low):
            line = float(low)
        else:
            words.append(word)
    market = normalize_market(" ".join(words))
    if market not in YES_NO_MARKETS and line is None:
        raise ValueError(f"prop leg {text!r} needs a line, e.g. 'pass yds 249.5 over' or '250+'")
    game = find_game(games, game_text=where) if re.search(r"@|\bat\b|\bvs\b", where, re.I) else find_game(games, team=where)
    return Leg(game, "prop", None, line if market not in YES_NO_MARKETS else None, side, player=player, market=market)


def parse_leg(text: str, games: list) -> Leg:
    """Legs like 'bills win', 'TEN Titans +7.5', 'no chiefs -3.5', 'KC @ DEN under 41.5',
    or props as 'Jahmyr Gibbs | anytime td | MIN @ DET'."""
    if "|" in text:
        return _parse_prop_leg(text, games)
    side, contract, raw_line, rest, implied_total = "YES", None, None, [], False
    words = [w for w in re.split(r"[\s,]+", str(text).strip()) if w]
    for i, word in enumerate(words):
        low = word.lower()
        if low == "no" and i + 1 < len(words) and words[i + 1].lower() == "saints":
            rest.append(word)  # "NO Saints" is New Orleans, not the NO side
            continue
        if low in SIDE_WORDS:
            side = SIDE_WORDS[low]
            implied_total = implied_total or low in ("over", "under")
            continue
        if low in ("pk", "pick", "pickem") or re.fullmatch(r"[+-]?\d+(\.\d+)?", low):
            raw_line = word
            continue
        key = low.replace("/", "").replace("-", "")
        if contract is None and key in CONTRACT_ALIASES:
            contract = CONTRACT_ALIASES[key]
            continue
        rest.append(word)
    if contract is None:
        contract = "total" if implied_total else ("spread" if raw_line is not None else "win")
    team_text = " ".join(rest).strip()
    if not team_text:
        raise ValueError(f"leg {text!r} doesn't name a team or game")
    if re.search(r"@|\bat\b|\bvs\.?\b", team_text, re.I):
        if contract != "total":
            raise ValueError(f"leg {text!r}: name the team for win/spread legs, e.g. 'TEN +7.5'")
        game, team = find_game(games, game_text=team_text), None
    else:
        team = lookup_team(team_text)
        game = find_game(games, team=team)
    if contract in ("spread", "total") and raw_line is None:
        raise ValueError(f"leg {text!r} needs a line")
    line = None
    if contract == "spread":
        line = parse_spread_line(raw_line)
    elif contract == "total":
        line = float(raw_line.replace("+", ""))
    return Leg(game, contract, team if contract != "total" else None, line, side)


def _bounds(leg: Leg) -> tuple:
    """The leg as a condition lo <= X < hi on home margin or total points (None = open)."""
    if leg.contract == "total":
        lo, hi = math.floor(leg.line) + 1, None
        kind = "total"
    else:
        kind = "margin"
        home = leg.game.side_of(leg.team) == "home"
        if leg.contract == "win":
            lo, hi = (1, None) if home else (None, 0)
        elif home:   # home margin > -h
            lo, hi = math.floor(-leg.line) + 1, None
        else:        # home margin < h
            lo, hi = None, math.ceil(leg.line)
    if leg.side == "NO":
        lo, hi = (None, lo) if lo is not None else (hi, None)
    return kind, lo, hi


def leg_fair(leg: Leg, models: NFLModels, extras: OddsExtras | None) -> Fair:
    if leg.fair is None:
        fair, name = contract_fair(leg.game, models, leg.contract, leg.team, leg.line, extras, leg.player, leg.market)
        leg.fair = fair
        if name:
            leg.player = name
    return leg.fair


def _at_least(game: Game, models: NFLModels, kind: str, k: int, extras: OddsExtras | None) -> Fair:
    try:
        fair = prob_at_least(game, models, kind, k)
        if fair.basis == "market" or extras is None:
            return fair
    except NoMarketData:
        if extras is None or not extras.load_alternates(game):
            raise
        return prob_at_least(game, models, kind, k)
    if extras.load_alternates(game):
        return prob_at_least(game, models, kind, k)
    return fair


def parlay_probability(legs: list, models: NFLModels, extras: OddsExtras | None = None) -> ParlayResult:
    if not legs:
        raise ValueError("a parlay needs at least one leg")
    leg_probs, uses_model, prob_of = [], False, {}
    for leg in legs:
        fair = leg_fair(leg, models, extras)
        leg_probs.append(fair.prob if leg.side == "YES" else 1.0 - fair.prob)
        prob_of[id(leg)] = leg_probs[-1]
        uses_model = uses_model or fair.basis != "market"
    by_game: dict = {}
    for leg in legs:
        by_game.setdefault(leg.game.key, []).append(leg)
    prob, notes = 1.0, []
    for group in by_game.values():
        game = group[0].game
        props = [l for l in group if l.contract == "prop"]
        lines = [l for l in group if l.contract != "prop"]
        for leg in props:
            prob *= prob_of[id(leg)]
        kinds = {}
        for leg in lines:
            kind, lo, hi = _bounds(leg)
            kinds.setdefault(kind, []).append((leg, lo, hi))
        for kind, items in kinds.items():
            if len(items) == 1:
                prob *= prob_of[id(items[0][0])]
                continue
            los = [lo for _, lo, _ in items if lo is not None]
            his = [hi for _, _, hi in items if hi is not None]
            lo, hi = (max(los) if los else None), (min(his) if his else None)
            if lo is not None and hi is not None and lo >= hi:
                prob = 0.0
                continue
            top = _at_least(game, models, kind, lo, extras) if lo is not None else None
            bottom = _at_least(game, models, kind, hi, extras) if hi is not None else None
            p = (top.prob if top else 1.0) - (bottom.prob if bottom else 0.0)
            prob *= max(p, 0.0)
            uses_model = uses_model or any(f is not None and f.basis != "market" for f in (top, bottom))
            what = "win/spread" if kind == "margin" else "total"
            notes.append(f"{game.label}: the {len(items)} {what} legs overlap, so they are priced together")
        if len(kinds) == 2:
            notes.append(f"{game.label}: win/spread and total legs treated as independent "
                         "(NFL results since 2015 show almost no link)")
        if props and len(group) > 1:
            uses_model = True
            notes.append(f"{game.label}: a player prop and another leg from the same game are treated as "
                         "independent; they usually aren't, so this needs extra return")
    return ParlayResult(list(legs), prob, leg_probs, notes, uses_model)


def required_roi(result: ParlayResult, cfg: dict) -> float:
    """Return needed before buying: more when any leg's price is model-based, estimated or same-game."""
    return cfg["parlay_min_roi"] + (cfg["parlay_model_extra_roi"] if result.uses_model else 0.0)


def max_parlay_price(prob: float, min_roi: float, schedule) -> float | None:
    """Most to pay (to the cent) and still expect `min_roi` return after the fee."""
    for cents in range(99, 0, -1):
        price = cents / 100.0
        cost = price + fee_for_price(price, schedule)
        if cost < 1.0 and prob / cost - 1.0 >= min_roi - 1e-9:
            return price
    return None


def price_parlay(prob: float, price: float, cfg: dict, min_roi: float | None = None) -> ParlayPrice:
    fee = fee_for_price(price, cfg["fee_schedule"])
    cost = price + fee
    if cost >= 1.0:
        raise ValueError("price plus fee must be below $1")
    edge = prob - cost
    roi = edge / cost
    kelly = kelly_fraction(prob, cost)
    min_roi = cfg["parlay_min_roi"] if min_roi is None else min_roi
    buy = edge > 0 and roi >= min_roi - 1e-9
    fraction = min(kelly * cfg["kelly_multiplier"], cfg["parlay_max_bet_fraction"]) if buy else 0.0
    stake = fraction * cfg["bankroll"]
    return ParlayPrice(price, fee, cost, edge, roi, kelly, stake, int(stake // cost) if cost else 0, buy)


@dataclass
class FoundParlay:
    result: ParlayResult
    implied: float      # combo price in line with the legs' own app prices
    value: float        # product of (fair chance / app price) over the legs
    max_price: float | None


def find_parlays(opportunities: list, models: NFLModels, cfg: dict, min_legs: int = 2, max_legs: int = 3,
                 same_game: bool = False, top: int = 10, extras: OddsExtras | None = None) -> list:
    """Best combos built from priced legs whose fair chance beats their own app price."""
    candidates, seen = [], set()
    for o in opportunities:
        ev = o.evaluation
        if ev.my_prob <= ev.price:
            continue
        leg = Leg(o.game, o.contract, o.team, o.line, ev.side, ev.price, o.player, o.market, o.fair)
        if (leg.identity, leg.side) in seen:
            continue
        seen.add((leg.identity, leg.side))
        candidates.append((leg, ev.my_prob, o.fair.basis != "market"))
    candidates.sort(key=lambda c: c[1] / c[0].price, reverse=True)
    found = []
    for k in range(min_legs, max_legs + 1):
        pool = candidates if k <= 3 else candidates[:12]
        for combo in itertools.combinations(pool, k):
            legs = [c[0] for c in combo]
            if len({l.identity for l in legs}) < len(legs):
                continue  # both sides of one contract
            games = [l.game.key for l in legs]
            if len(set(games)) < len(games):
                if not same_game:
                    continue
                result = parlay_probability(legs, models, extras)
            else:
                prob = 1.0
                for _, p, _ in combo:
                    prob *= p
                result = ParlayResult(legs, prob, [p for _, p, _ in combo], uses_model=any(m for _, _, m in combo))
            if result.prob <= 0:
                continue
            value = 1.0
            for (leg, p, _) in combo:
                value *= p / leg.price
            found.append(FoundParlay(result, result.prob / value, value,
                                     max_parlay_price(result.prob, required_roi(result, cfg), cfg["fee_schedule"])))
    found.sort(key=lambda f: f.value, reverse=True)
    return found[:top]


# ==================== command line ============================================

#!/usr/bin/env python3


import argparse
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PROG = f"python3 {Path(__file__).name}"
sys.path.insert(0, str(ROOT))



def _data_dir() -> Path:
    """data/ next to this script (./dk_data for the single-file build, or when data/ is read-only)."""
    if os.environ.get("DKPRED_DATA_DIR"):
        return Path(os.environ["DKPRED_DATA_DIR"])
    if globals().get("__single_file__"):
        return Path.cwd() / "dk_data"
    for candidate in (ROOT / "data", Path.cwd() / "dk_data"):
        try:
            candidate.mkdir(parents=True, exist_ok=True)
            probe = candidate / ".write_test"
            probe.write_text("ok", encoding="utf-8")
            probe.unlink()
            return candidate
        except OSError:
            continue
    return Path.cwd() / "dk_data"


DATA = _data_dir()
CACHE = DATA / "cache"
PRICES = DATA / "dk_prices.csv"
TRADES = DATA / "trades.csv"


def load_games(args, cfg, whole_season: bool = False) -> tuple:
    now = datetime.now(timezone.utc)
    if whole_season:
        until = None
    elif args.days:
        until = now + timedelta(days=args.days)
    else:
        until = week_window_end(now)
    lines_file = args.lines_file or args.nflverse_file
    source = "nflverse" if lines_file else (args.source or cfg["odds_source"])
    if source == "auto":
        source = "odds-api" if (cfg["odds_api_key"] or args.odds_file) else "nflverse"
    if source == "odds-api":
        events, desc = fetch_odds_api_events(cfg["odds_api_key"], CACHE, cfg["regions"], cfg["bookmakers"],
                                             cfg["odds_cache_minutes"], args.refresh, args.odds_file,
                                             cfg["live_cache_seconds"])
        games = games_from_odds_api(events, cfg["devig_method"], now, until)
        for g in games:
            g.sharp_books = cfg["sharp_books"]
    else:
        rows, desc = load_nflverse_rows(CACHE, cfg["nflverse_cache_minutes"], args.refresh, lines_file)
        games = games_from_nflverse(rows, cfg["devig_method"], now, until)
    return games, desc


def make_extras(args, cfg) -> OddsExtras:
    return OddsExtras(cfg, CACHE, args.refresh, args.event_odds_file)


def live_status(game, cfg) -> str:
    """'' before kickoff; for a live game, how old its newest sportsbook price is."""
    if not game.live:
        return ""
    if not game.live_priced:
        return "LIVE: only pre-game lines available, so it can't be priced (needs an Odds API key)"
    if game.updated is None:
        return "LIVE: age of these prices unknown"
    age = (datetime.now(timezone.utc) - game.updated).total_seconds()
    text = f"LIVE: newest sportsbook price is {max(age, 0):.0f}s old"
    if age > cfg["live_stale_seconds"]:
        text += (f". WARNING: older than {cfg['live_stale_seconds']:.0f}s, so something may have happened since. "
                 "Run again with --refresh before trading")
    return text


def _when(game) -> str:
    return "LIVE" if game.live else fmt_local(game.kickoff)


def cmd_board(args, cfg, models):
    games, desc = load_games(args, cfg)
    print(f"Fair odds from {desc}\n")
    if not games:
        print("No live or upcoming games with odds in this window. Try --days 10.")
        return
    rows = []
    for g in games:
        if g.live and not g.live_priced:
            rows.append([_when(g), g.label, "live: needs Odds API key", "-", "-", "-"])
            continue
        c = consensus(g, models)
        spread = "PK" if c.spread == 0 else (f"{c.favorite} -{num(c.spread)}" if c.favorite else "-")
        rows.append([_when(g), g.label, f"{pct(c.p_away)} / {pct(c.p_home)}", spread, num(c.total) or "-", c.books])
    print(table(["Kickoff", "Game", "Win % away / home", "Spread", "Total", "Books"], rows, right=(5,)))
    print("\nWin % already removes the bookmaker's margin and the small chance of a tie.")
    stale = [g.label for g in games if g.live and g.live_priced and "WARNING" in live_status(g, cfg)]
    if stale:
        print(f"Live prices older than {cfg['live_stale_seconds']:.0f}s: {', '.join(stale)}. Use --refresh.")


def _contract_args(args):
    contract = contract_kind(args.contract)
    raw_line = args.line
    if contract == "prop":
        raise SystemExit(f"for player props use: {PROG} prop \"Player Name\" \"anytime td\" --game DET")
    team = lookup_team(args.team)
    line = parse_line(contract, raw_line)
    if contract in ("spread", "total") and line is None:
        raise SystemExit(f"{contract} needs a line, e.g. `{PROG} check {args.team} spread +7.5 --yes 52`")
    return contract, team, line


def _normalize_check_args(args):
    """Allow the app's style without the word 'spread': `check titans +7.5`."""
    if args.contract and args.line is None and (args.contract[:1] in "+-" or args.contract.lower() in ("pk", "pick")):
        args.line, args.contract = args.contract, "spread"


def _print_verdicts(game, fair, threshold, cfg, describe_yes, describe_no):
    for side, prob, label in (("YES", fair.prob, describe_yes), ("NO", 1 - fair.prob, describe_no)):
        cap = max_price(prob, threshold, cfg["fee_schedule"])
        cap_text = f"${cap:.2f}" if cap else "no price works"
        print(f"  {label}: buy only at {cap_text} or less (needs {pct(threshold, 0)} edge after fees)")


BASIS_TEXT = {
    "market": "straight from sportsbook prices",
    "model": "from the score model; no book quotes this line",
    "interpolated": "between two nearby sportsbook lines",
    "one-way": "books quote only this side, so their margin is estimated",
}


def cmd_check(args, cfg, models):
    _normalize_check_args(args)
    contract, team, line = _contract_args(args)
    games, desc = load_games(args, cfg, whole_season=True)
    game = find_game(games, team=team)
    extras = make_extras(args, cfg)
    contract_team = team if contract != "total" else None
    print(f"{game.label}, {_when(game)}  ({desc})")
    status = live_status(game, cfg)
    if status:
        print(status)
    fair, _ = contract_fair(game, models, contract, contract_team, line, extras)
    print(f"Contract: {describe_side(contract, contract_team, line, 'YES')}")
    print(f"Fair chance YES wins: {pct(fair.prob)}  ({BASIS_TEXT.get(fair.basis, fair.basis)}; {fair.note})")
    _print_verdicts(game, fair, edge_threshold(fair, cfg), cfg,
                    describe_side(contract, contract_team, line, "YES"),
                    describe_side(contract, contract_team, line, "NO"))
    yes, no = parse_price(args.yes), parse_price(args.no)
    if yes is not None or no is not None:
        print()
        results = evaluate_contract(game, models, cfg, contract, contract_team, line, yes, no, extras)
        _print_opportunities(results, show_all=True, cfg=cfg, top=1)
    _print_notes(extras)


def cmd_prop(args, cfg, models):
    market = normalize_market(args.market)
    line = parse_line("prop", args.line) if args.line is not None else None
    games, desc = load_games(args, cfg, whole_season=True)
    game = find_game(games, game_text=args.game)
    extras = make_extras(args, cfg)
    print(f"{game.label}, {_when(game)}  ({desc})")
    status = live_status(game, cfg)
    if status:
        print(status)
    fair, name = extras.prop_fair(game, args.player, market, line)
    print(f"Contract: {describe_prop(name, market, line, 'YES')}")
    print(f"Fair chance YES wins: {pct(fair.prob)}  ({BASIS_TEXT.get(fair.basis, fair.basis)}; {fair.note})")
    _print_verdicts(game, fair, edge_threshold(fair, cfg), cfg, describe_prop(name, market, line, "YES"),
                    describe_prop(name, market, line, "NO"))
    yes, no = parse_price(args.yes), parse_price(args.no)
    if yes is not None or no is not None:
        print()
        results = evaluate_contract(game, models, cfg, "prop", None, line, yes, no, extras, name, market)
        _print_opportunities(results, show_all=True, cfg=cfg, top=1)
    _print_notes(extras)


def _print_notes(extras):
    for note in extras.notes:
        print(f"({note})")


def _signed_money(x: float) -> str:
    return ("+" if x >= 0 else "-") + money(abs(x))


def _print_opportunities(opps, show_all: bool, cfg=None, top: int = 3):
    rows = []
    for o in opps:
        ev = o.evaluation
        if not show_all and ev.suggested_fraction <= 0:
            continue
        verdict = "BUY" if ev.suggested_fraction > 0 else ("small edge" if ev.edge > 0 else "pass")
        rows.append([o.game.label + (" LIVE" if o.game.live else ""), o.trade, f"${ev.price:.2f}", f"${ev.fee:.2f}",
                     pct(ev.my_prob), pct(ev.edge), pct(ev.roi), money(o.stake) if o.stake else "-",
                     o.contracts or "-", o.fair.basis, verdict])
    if rows:
        print(table(["Game", "Trade", "Price", "Fee", "Fair", "Edge", "ROI", "Stake", "Qty", "Basis", ""],
                    rows, right=(2, 3, 4, 5, 6, 7, 8)))
    buys = [o for o in opps if o.evaluation.suggested_fraction > 0]
    games_with_buys = [o.game.key for o in buys]
    if len(games_with_buys) != len(set(games_with_buys)):
        print("\nNote: more than one buy in the same game. Those bets win or lose together, so size them as one.")
    if cfg is not None and opps:
        _print_picks(opps, cfg, top, gap=bool(rows))
    elif not rows:
        print("Nothing clears your edge threshold right now. Use --all to see every price.")


def _print_picks(opps, cfg, top: int, gap: bool = True):
    """BUYs ranked, or, when there are none, the closest prices as LEANs with what they'd need to become a BUY."""
    buys = sorted((o for o in opps if o.evaluation.suggested_fraction > 0),
                  key=lambda o: o.evaluation.edge - o.threshold, reverse=True)
    if buys:
        best = buys[0]
        print(f"{chr(10) if gap else ''}Top pick: BUY {best.trade} at ${best.evaluation.price:.2f} "
              f"({money(best.stake)}, {best.contracts} contracts; {_signed_money(best.evaluation.roi * 10)} "
              f"expected per $10)")
        return
    leans = sorted(opps, key=lambda o: o.evaluation.roi, reverse=True)[:max(top, 1)]
    print(f"{chr(10) if gap else ''}Nothing clears your {pct(cfg['min_edge'], 0)} edge bar. "
          f"Closest {'price' if len(leans) == 1 else str(len(leans)) + ' prices'} (LEAN):")
    rows = []
    for o in leans:
        ev = o.evaluation
        cap = max_price(ev.my_prob, o.threshold, cfg["fee_schedule"])
        rows.append([o.game.label + (" LIVE" if o.game.live else ""), o.trade, f"${ev.price:.2f}", pct(ev.my_prob),
                     _signed_money(ev.roi * 10), f"${cap:.2f}" if cap else "none", o.fair.basis])
    print(table(["Game", "Trade", "Price", "Fair", "Per $10", "BUY at", "Basis"], rows, right=(2, 3, 4, 5)))
    best = leans[0].evaluation
    if best.edge > 0:
        print("LEAN = closest to a BUY. A positive 'Per $10' is a small edge under your bar; a negative one is an "
              "expected loss. The bankroll math sizes LEANs at $0, so any stake is your call. "
              "'BUY at' is the price that would make it a BUY.")
    else:
        print(f"LEAN = the smallest expected loss, not a winning bet: about {money(-best.roi * 10)} lost per $10 "
              "on average. The bankroll math sizes it at $0, so any stake is your call. "
              "'BUY at' is the price that would make it a BUY.")


def cmd_template(args, cfg, models):
    games, desc = load_games(args, cfg)
    path = Path(args.file) if args.file else PRICES
    try:
        n = write_template(path, games, models, force=args.force)
    except FileExistsError as err:
        raise SystemExit(f"{err}. Run with --force to start a fresh sheet.")
    print(f"Wrote {n} rows for {len(games)} games to {path}")
    print("Type the YES and/or NO price you see in DraftKings Predictions, change spread and total lines to")
    print("match the app (spreads keep their sign: TEN +7.5), add prop rows if you like, delete rows you don't")
    print(f"need, save, then run: {PROG} scan")


def _price_sheet(args) -> Path:
    path = Path(args.file) if args.file else PRICES
    if not path.exists():
        raise SystemExit(f"{path} doesn't exist yet. Run `{PROG} template` first.")
    return path


def cmd_scan(args, cfg, models):
    path = _price_sheet(args)
    games, desc = load_games(args, cfg, whole_season=True)
    extras = make_extras(args, cfg)
    opps, problems = evaluate_rows(read_price_rows(path), games, models, cfg, extras)
    print(f"Fair odds from {desc}. Bankroll {money(cfg['bankroll'])}, "
          f"{cfg['kelly_multiplier']:g}x Kelly, max {pct(cfg['max_bet_fraction'], 0)} per trade.\n")
    if not opps and not problems:
        print(f"No prices filled in yet in {path.name}.")
        return
    _print_opportunities(opps, show_all=args.all, cfg=cfg, top=args.top)
    _print_live_warnings({o.game.key: o.game for o in opps}.values(), cfg)
    _print_problems(problems)
    _print_notes(extras)


def _print_live_warnings(games, cfg):
    for g in games:
        status = live_status(g, cfg)
        if status:
            print(f"{g.label}: {status}")


def _print_problems(problems):
    if problems:
        print("\nSkipped:")
        for p in problems:
            print("  " + p)


def cmd_parlay(args, cfg, models):
    games, desc = load_games(args, cfg, whole_season=True)
    extras = make_extras(args, cfg)
    legs = [parse_leg(text, games) for text in args.legs]
    result = parlay_probability(legs, models, extras)
    print(f"Fair odds from {desc}\n")
    rows = [[i, leg.description, leg.game.label, _when(leg.game), pct(p), leg.fair.basis if leg.fair else ""]
            for i, (leg, p) in enumerate(zip(legs, result.leg_probs), start=1)]
    print(table(["#", "Leg", "Game", "Kickoff", "Fair", "Basis"], rows, right=(4,)))
    print()
    _print_live_warnings({l.game.key: l.game for l in legs}.values(), cfg)
    if result.prob <= 0:
        print("These legs can't all win together.")
        return
    min_roi = required_roi(result, cfg)
    print(f"Fair chance every leg wins: {pct(result.prob)} (a fair combo price is ${result.prob:.2f})")
    cap = max_parlay_price(result.prob, min_roi, cfg["fee_schedule"])
    if cap:
        print(f"Pay at most ${cap:.2f} for this combo (leaves a {pct(min_roi, 0)} expected return after the fee)")
    else:
        print(f"No price leaves the {pct(min_roi, 0)} expected return you require.")
    if args.price:
        quote = price_parlay(result.prob, parse_price(args.price), cfg, min_roi)
        verdict = "BUY" if quote.buy else ("small edge" if quote.edge > 0 else "pass")
        print()
        print(table(["Combo price", "Fee", "Fair", "Edge", "Return", "Stake", "Qty", ""],
                    [[f"${quote.price:.2f}", f"${quote.fee:.2f}", pct(result.prob), pct(quote.edge), pct(quote.roi),
                      money(quote.stake) if quote.stake else "-", quote.contracts or "-", verdict]],
                    right=(0, 1, 2, 3, 4, 5, 6)))
    for note in result.notes:
        print(f"Note: {note}")
    if result.uses_model:
        print(f"Note: some prices here are estimated (model, interpolated, one-way or same-game), so this needs "
              f"{pct(min_roi, 0)} return, not {pct(cfg['parlay_min_roi'], 0)}.")
    _print_notes(extras)


def cmd_parlays(args, cfg, models):
    path = _price_sheet(args)
    games, desc = load_games(args, cfg, whole_season=True)
    extras = make_extras(args, cfg)
    opps, problems = evaluate_rows(read_price_rows(path), games, models, cfg, extras)
    found = find_parlays(opps, models, cfg, args.min_legs, args.legs, args.same_game, args.top, extras)
    print(f"Fair odds from {desc}\n")
    if not found:
        print("No combos to suggest. Each leg must be a priced contract whose fair chance beats its own price,")
        print("with legs from different games (add --same-game to allow same-game combos).")
        _print_problems(problems)
        return
    for i, f in enumerate(found, start=1):
        cap = f"${f.max_price:.2f}" if f.max_price else "none"
        print(f"#{i}  fair chance {pct(f.result.prob)}   leg prices imply ${f.implied:.2f}   "
              f"value {f.value:.2f}x   pay at most {cap}")
        for leg, p in zip(f.result.legs, f.result.leg_probs):
            print(f"      {leg.description:<34} {leg.game.label + (' LIVE' if leg.game.live else ''):<15} "
                  f"price ${leg.price:.2f}  fair {pct(p)}")
        for note in f.result.notes:
            print(f"      note: {note}")
    print("\nValue multiplies each leg's fair chance divided by its app price; above 1.00x the legs are underpriced.")
    print("'Leg prices imply' is what the combo would cost if the app priced it in line with those legs. The app")
    print("quotes its own combo price, usually worse, so build the combo in the app and buy only if the quote is at")
    print(f"or below 'pay at most'. Check a quote with: {PROG} parlay \"leg\" \"leg\" --price X")
    _print_problems(problems)
    _print_notes(extras)


def cmd_log(args, cfg, models):
    price = parse_price(args.price)
    games, _ = load_games(args, cfg, whole_season=True)
    extras = make_extras(args, cfg)
    _normalize_check_args(args)
    if contract_kind(args.contract) == "prop":
        if not args.player or not args.market:
            raise SystemExit("a prop trade needs --player and --market")
        market = normalize_market(args.market)
        line = parse_line("prop", args.line) if args.line is not None else None
        game = find_game(games, game_text=args.team)
        contract, team, player = "prop", None, args.player
    else:
        contract, team, line = _contract_args(args)
        game = find_game(games, team=team)
        market = player = None
        if contract == "total":
            team = None
    try:
        fair, name = contract_fair(game, models, contract, team, line, extras, player, market)
        player = name or player
    except (NoMarketData, SourceError, LookupError):
        fair = None
    fee = float(args.fee) if args.fee is not None else fee_for_price(price, cfg["fee_schedule"])
    trade = log_trade(TRADES, game, contract, team, line, args.side, price, fee, args.contracts, fair,
                      args.notes or "", player, market)
    _print_logged(trade, price, fee)


def _print_logged(trade, price, fee):
    edge = ""
    if trade["fair_prob"]:
        edge = f", fair {pct(float(trade['fair_prob']))}, edge {pct(float(trade['fair_prob']) - price - fee)}"
    print(f"Logged #{trade['id']}: {describe_trade(trade)} ({trade['game']}), "
          f"{trade['contracts']} at ${price:.2f} + ${fee:.2f} fee{edge}")
    print(f"Journal: {TRADES}")


def cmd_log_combo(args, cfg, models):
    price = parse_price(args.price)
    games, _ = load_games(args, cfg, whole_season=True)
    extras = make_extras(args, cfg)
    legs = [parse_leg(text, games) for text in args.legs]
    try:
        prob = parlay_probability(legs, models, extras).prob
        fair = Fair(prob, "combo")
    except (NoMarketData, SourceError, LookupError):
        fair = None
    fee = float(args.fee) if args.fee is not None else fee_for_price(price, cfg["fee_schedule"])
    notes = " + ".join(f"{l.description} ({l.game.label})" for l in legs)
    trade = log_trade(TRADES, None, "combo", None, None, "YES", price, fee, args.contracts, fair, notes)
    _print_logged(trade, price, fee)


def cmd_result(args, cfg, models):
    t = set_result(TRADES, args.id, args.outcome)
    print(f"#{t['id']} {describe_trade(t)}: {t['status']}, profit {money(float(t['pnl']))}")


def cmd_settle(args, cfg, models):
    rows, desc = load_nflverse_rows(CACHE, max_age_minutes=30, refresh=args.refresh,
                                    local_file=args.lines_file or args.nflverse_file)
    settled, still_open, manual = settle_trades(TRADES, rows, models, cfg["devig_method"])
    if settled:
        out = [[t["id"], t["game"], describe_trade(t), t["final_score"], t["status"], money(float(t["pnl"])),
                pct(float(t["closing_edge"])) if t.get("closing_edge") else "-"] for t in settled]
        print(table(["#", "Game", "Trade", "Final", "Result", "Profit", "Closing edge"], out, right=(5, 6)))
        print()
    else:
        print(f"Nothing new to settle. Scores from {desc}.")
    print(f"{still_open} game-line trades still open.")
    if manual:
        print(f"{manual} open props/combos: settle them with `{PROG} result ID won|lost|void`.")


def cmd_report(args, cfg, models):
    print(report(read_trades(TRADES)))


def build_parser() -> argparse.ArgumentParser:
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--source", choices=["nflverse", "odds-api"], help="where odds come from (default: config)")
    common.add_argument("--refresh", action="store_true", help="ignore cached odds and download fresh ones")
    common.add_argument("--days", type=float, help="look this many days ahead instead of this NFL week")
    common.add_argument("--config", help="path to config.json (default: next to this script, then the current folder)")
    common.add_argument("--set", action="append", metavar="KEY=VALUE", help="change a setting for this run")
    common.add_argument("--lines-file", help="use lines from a CSV in nflverse games.csv format instead of downloading")
    common.add_argument("--nflverse-file", help=argparse.SUPPRESS)
    common.add_argument("--odds-file", help=argparse.SUPPRESS)
    common.add_argument("--event-odds-file", help=argparse.SUPPRESS)

    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="command", required=True)

    sub.add_parser("board", parents=[common], help="fair odds for this week's and live games").set_defaults(func=cmd_board)

    def contract_args(p):
        p.add_argument("team", help="team name, nickname or abbreviation (for totals, either team)")
        p.add_argument("contract", help="win, spread, total, or a spread line like +7.5")
        p.add_argument("line", nargs="?", help="spread: the line as the app shows it (+7.5, -3); total: points line")

    p = sub.add_parser("check", parents=[common], help="check one game-line price")
    contract_args(p)
    p.add_argument("--yes", help="price to buy YES (cents or dollars)")
    p.add_argument("--no", help="price to buy NO (cents or dollars)")
    p.set_defaults(func=cmd_check)

    p = sub.add_parser("prop", parents=[common], help="check a player prop price (needs an Odds API key)")
    p.add_argument("player", help='player name, e.g. "Jahmyr Gibbs"')
    p.add_argument("market", help='e.g. "anytime td", "pass yds", "rec yds", "receptions"')
    p.add_argument("line", nargs="?", help="for yards/receptions: the line, e.g. 249.5 or 250+")
    p.add_argument("--game", required=True, help="the player's team, or the game like 'MIN @ DET'")
    p.add_argument("--yes", help="price to buy YES / over")
    p.add_argument("--no", help="price to buy NO / under")
    p.set_defaults(func=cmd_prop)

    p = sub.add_parser("parlay", parents=[common], help="fair price of a combo, and whether a quote is good")
    p.add_argument("legs", nargs="+", help='e.g. "TEN +7.5" "bills win" "KC@DEN over 41.5" '
                                            '"Jahmyr Gibbs | anytime td | MIN @ DET"')
    p.add_argument("--price", help="the combo price the app quotes (the % shown, in cents)")
    p.set_defaults(func=cmd_parlay)

    p = sub.add_parser("template", parents=[common], help="write a price sheet to fill in")
    p.add_argument("--file", help="default data/dk_prices.csv")
    p.add_argument("--force", action="store_true", help="overwrite a sheet that already has prices")
    p.set_defaults(func=cmd_template)

    p = sub.add_parser("scan", parents=[common], help="rank the prices in your sheet")
    p.add_argument("--file", help="default data/dk_prices.csv")
    p.add_argument("--all", action="store_true", help="show every price, not only ones worth buying")
    p.add_argument("--top", type=int, default=3, help="when nothing is a BUY, how many closest prices to show")
    p.set_defaults(func=cmd_scan)

    p = sub.add_parser("parlays", parents=[common], help="best combos from the prices in your sheet")
    p.add_argument("--file", help="default data/dk_prices.csv")
    p.add_argument("--legs", type=int, default=3, choices=range(2, 7), help="most legs per combo (default 3)")
    p.add_argument("--min-legs", type=int, default=2, choices=range(2, 7), help="fewest legs (default 2)")
    p.add_argument("--same-game", action="store_true", help="allow more than one leg from the same game")
    p.add_argument("--top", type=int, default=10, help="how many combos to show")
    p.set_defaults(func=cmd_parlays)

    p = sub.add_parser("log", parents=[common], help="record a single trade you placed")
    contract_args(p)
    p.add_argument("--side", required=True, choices=["yes", "no", "YES", "NO"])
    p.add_argument("--price", required=True, help="price paid per contract (cents or dollars)")
    p.add_argument("--contracts", required=True, type=int)
    p.add_argument("--fee", type=float, help="fee per contract in dollars (default: fee schedule)")
    p.add_argument("--player", help="for a prop: the player")
    p.add_argument("--market", help="for a prop: e.g. 'anytime td'")
    p.add_argument("--notes")
    p.set_defaults(func=cmd_log)

    p = sub.add_parser("log-combo", parents=[common], help="record a combo you placed")
    p.add_argument("legs", nargs="+")
    p.add_argument("--price", required=True, help="combo price paid per contract")
    p.add_argument("--contracts", required=True, type=int)
    p.add_argument("--fee", type=float)
    p.set_defaults(func=cmd_log_combo)

    p = sub.add_parser("result", parents=[common], help="settle one trade by hand")
    p.add_argument("id")
    p.add_argument("outcome", choices=["won", "lost", "void"])
    p.set_defaults(func=cmd_result)

    sub.add_parser("settle", parents=[common], help="settle finished games").set_defaults(func=cmd_settle)
    sub.add_parser("report", parents=[common], help="results summary").set_defaults(func=cmd_report)
    return ap


def main(argv=None) -> None:
    args = build_parser().parse_args(argv)
    config_path = args.config or next((p for p in (ROOT / "config.json", Path.cwd() / "config.json") if p.exists()),
                                      ROOT / "config.json")
    cfg = load_config(config_path, parse_overrides(args.set))
    models = load_models()
    try:
        args.func(args, cfg, models)
    except SourceError as err:
        raise SystemExit(f"Couldn't get data: {err}")
    except (ValueError, LookupError, NoMarketData) as err:
        raise SystemExit(str(err))


if __name__ == "__main__":
    main()
