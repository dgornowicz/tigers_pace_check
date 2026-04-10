import requests
import datetime
import streamlit as st

# ── Config ───────────────────────────────────────────────────
TEAM_ID   = 116   # Detroit Tigers
LEAGUE_ID = 103   # American League
SEASON    = datetime.date.today().year

# ── Helper Functions ─────────────────────────────────────────
def win_pct(w, l):
    total = w + l
    if total == 0:
        return 0.0, '0.0%'
    pct = w / total
    return pct, f'{pct * 100:.1f}%'

def pace(w, l, season_games=162):
    total = w + l
    if total == 0:
        return '0-0'
    proj_w = round((w / total) * season_games)
    return f'{proj_w}-{season_games - proj_w}'

def pythagorean(rs, ra, games_played):
    if rs + ra == 0:
        return 0, games_played, '0-0', '0.0%'
    ratio = (rs ** 2) / (rs ** 2 + ra ** 2)
    xw = round(ratio * games_played)
    xl = games_played - xw
    return xw, xl, pace(xw, xl), f'{ratio * 100:.1f}%'

# ── Fetch All Stats ───────────────────────────────────────────
def fetch_tigers_stats(team_id=TEAM_ID, season=SEASON):
    today_str    = datetime.date.today().strftime('%Y-%m-%d')
    season_start = f'{season}-03-01'

    standings_url = (
        f'https://statsapi.mlb.com/api/v1/standings'
        f'?leagueId=103,104&season={season}&standingsTypes=regularSeason'
    )
    stats_url = (
        f'https://statsapi.mlb.com/api/v1/teams/{team_id}/stats'
        f'?stats=season&group=hitting,pitching&season={season}'
    )
    schedule_url = (
        f'https://statsapi.mlb.com/api/v1/schedule'
        f'?teamId={team_id}&startDate={season_start}&endDate={today_str}'
        f'&sportId=1&gameType=R&hydrate=linescore'
    )

    s_resp = requests.get(standings_url, timeout=10)
    s_resp.raise_for_status()

    team_record = None
    current_wl  = {}

    for division in s_resp.json().get('records', []):
        for team in division.get('teamRecords', []):
            tid = team['team']['id']
            current_wl[tid] = (team['wins'], team['losses'])
            if tid == team_id:
                team_record = team

    if not team_record:
        raise ValueError('Team not found in standings response.')

    w  = team_record['wins']
    l  = team_record['losses']
    rs = team_record.get('runsScored', 0)
    ra = team_record.get('runsAllowed', 0)

    streak_info = team_record.get('streak', {})
    streak_str  = f"{streak_info.get('streakType', '?')[0].upper()}{streak_info.get('streakNumber', 0)}"

    l10_w, l10_l = 0, 0
    for split in team_record.get('records', {}).get('splitRecords', []):
        if split.get('type') == 'lastTen':
            l10_w = split['wins']
            l10_l = split['losses']
            break

    if rs == 0 and ra == 0:
        try:
            t_resp = requests.get(stats_url, timeout=10)
            t_resp.raise_for_status()
            for group in t_resp.json().get('stats', []):
                if group['group']['displayName'] == 'hitting':
                    rs = group['splits'][0]['stat'].get('runs', 0)
                elif group['group']['displayName'] == 'pitching':
                    ra = group['splits'][0]['stat'].get('runs', 0)
        except Exception:
            pass

    vs500_w, vs500_l = 0, 0
    sc_resp = requests.get(schedule_url, timeout=10)
    sc_resp.raise_for_status()

    for date_block in sc_resp.json().get('dates', []):
        for game in date_block.get('games', []):
            if game.get('status', {}).get('abstractGameState') != 'Final':
                continue

            away = game['teams']['away']
            home = game['teams']['home']
            tigers_is_home = home['team']['id'] == team_id
            opp            = away if tigers_is_home else home
            tigers_side    = home if tigers_is_home else away

            tigers_score = tigers_side.get('score', 0)
            opp_score    = opp.get('score', 0)
            opp_id       = opp['team']['id']

            opp_w, opp_l = current_wl.get(opp_id, (0, 0))
            opp_total    = opp_w + opp_l

            if opp_total == 0 or opp_w / opp_total <= 0.500:
                continue

            if tigers_score > opp_score:
                vs500_w += 1
            else:
                vs500_l += 1

    return {
        'w': w, 'l': l,
        'rs': rs, 'ra': ra,
        'streak': streak_str,
        'l10_w': l10_w, 'l10_l': l10_l,
        'vs500_w': vs500_w, 'vs500_l': vs500_l,
    }

# ── Streamlit UI ─────────────────────────────────────────────
st.set_page_config(page_title='Tigers Pace Check', page_icon='🐅')
st.title('🐅 Tigers Pace Check')

if st.button('Run Pace Check', type='primary'):
    with st.spinner('Fetching latest stats...'):
        try:
            d = fetch_tigers_stats()

            today        = datetime.date.today().strftime('%#m/%#d')
            games_played = d['w'] + d['l']

            _, wl_pct_str                      = win_pct(d['w'], d['l'])
            wl_pace_str                        = pace(d['w'], d['l'])
            xw, xl, xwl_pace_str, xwl_pct_str = pythagorean(d['rs'], d['ra'], games_played)
            vs500_games                        = d['vs500_w'] + d['vs500_l']
            _, vs500_pct                       = win_pct(d['vs500_w'], d['vs500_l'])
            vs500_share                        = f"{vs500_games / games_played * 100:.1f}%" if games_played else '0.0%'
            streak_emoji                       = '🔥' if d['streak'].startswith('W') else '❄️'

            st.subheader(f'🐅 Tigers Pace Check — {today}')
            st.divider()
            st.markdown(f'🏆 **W-L:** {d["w"]}-{d["l"]} ({wl_pct_str}) → pace: {wl_pace_str}')
            st.markdown(f'📊 **xW-L:** {xw}-{xl} ({xwl_pct_str}) → pace: {xwl_pace_str}')
            st.markdown(f'💪 **>.500:** {d["vs500_w"]}-{d["vs500_l"]} ({vs500_pct}) ({vs500_share} of games)')
            st.markdown(f'{streak_emoji} **L10:** {d["l10_w"]}-{d["l10_l"]} ({d["streak"]} Streak)')

        except Exception as e:
            st.error(f'Failed to fetch stats: {e}')
