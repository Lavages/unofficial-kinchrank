from flask import Flask, render_template, request
from flask_caching import Cache
import pandas as pd
import numpy as np
import ast
import pycountry
import pycountry_convert as pc
import os

app = Flask(__name__)

# --- VERCEL PATH FIX ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# --- CACHE CONFIGURATION ---
cache = Cache(app, config={'CACHE_TYPE': 'simple'})

# --- CONFIGURATION ---
CORE_AVG = ['fto', '333_team_bld', '333_mirror_blocks', '333_mirror_blocks_bld', 'mpyram', 'kilominx', 'redi', 'magic', 'mmagic', '333_linear_fm', '333ft']
CORE_SIN = ['333_speed_bld', 'miniguild', 'miniguild_2_person', '333mts']
MISC_AVG_EVENTS = ['222_blanker', '222_mirror_blocks', '444_mirror_blocks', '555_mirror_blocks', 'fisher', '333_windmill_cube', '333_axis_cube', '333_twist_cube','333oh_x2', '333_void', '333_cube_mile', '333_siamese', '223_cuboid', '133_cuboid','233_cuboid', '334_cuboid', 'super_133', '888', '999', '101010', 'mkilominx', 'gigaminx', 'baby_fto', 'mfto', 'cto', '2pentahedron', '3pentahedron', 'pyramorphix', 'pyram_duo','333_team_bld_old', 'dino', 'ivy_cube', 'rainbow_cube', 'corner_heli222', 'helicopter', 'curvycopter', 'gear_cube', 'super_gear_cube','skewb_oh', 'magic_oh', '222fm', '444fm', 'snake', '15puzzle', '8puzzle','222oh','444oh','clock_oh','333_oven_mitts','333_paw_mitts','222bf','new_penta_clock','penta_clock','minx_oh','clock_bld','clock_doubles']
MISC_SIN_EVENTS = ['333_bets', '333_supersolve', '333bf_bottle', '333oh_bottle','333bf_oh','333_braille_bld','234567relay','2345relay_bld','miniguild_oh']

AVG_EVENTS = set(CORE_AVG + MISC_AVG_EVENTS)
SIN_EVENTS = set(CORE_SIN + MISC_SIN_EVENTS)
ALL_TARGET_EVENTS = list(AVG_EVENTS | SIN_EVENTS)
CONTINENTS = ['Africa', 'Asia', 'Europe', 'North America', 'Oceania', 'South America']

# --- HELPERS ---
def format_time(value, event_id, is_avg=False):
    try:
        val_float = float(value)
        if val_float == -1: return "DNF" # Return DNF string for WCA standard
        if val_float == -2: return "DNS" # Return DNS string for Did Not Start
        if val_float <= 0: return "-"
    except (ValueError, TypeError):
        return "-"
    
    if 'fm' in event_id.lower():
        return f"{val_float / 100.0:.2f}" if is_avg else str(int(val_float))

    seconds = val_float / 100.0
    if seconds < 60:
        return f"{seconds:.2f}"
    return f"{int(seconds // 60)}:{seconds % 60:05.2f}"

@cache.memoize(timeout=86400)
def get_region_info(code):
    try:
        manual_continents = {'HK': 'Asia', 'TW': 'Asia', 'XK': 'Europe', 'PS': 'Asia'}
        country = pycountry.countries.get(alpha_2=code)
        c_name = country.name if country else code
        cont_name = manual_continents.get(code) or pc.convert_continent_code_to_continent_name(pc.country_alpha2_to_continent_code(code))
        return c_name, cont_name
    except:
        return code, "Other"

# --- DATA PERSISTENCE ---
GLOBAL_DATA = {}

def load_and_process_data():
    global GLOBAL_DATA
    if GLOBAL_DATA:
        return GLOBAL_DATA['res'], GLOBAL_DATA['exp'], GLOBAL_DATA['pers'], GLOBAL_DATA['ev'], GLOBAL_DATA['cont']

    try:
        res_df = pd.read_csv(os.path.join(BASE_DIR, "export_results.csv"), usecols=[
            'competition_id', 'person_ids', 'event_id', 'round_id', 'best', 
            'average', 'ranking', 'attempts', 'regional_single_record', 
            'regional_average_record', 'record_category'
        ])
        pers_df = pd.read_csv(os.path.join(BASE_DIR, "export_persons.csv"), usecols=['id', 'name', 'wca_id', 'region_code'])
        ev_df = pd.read_csv(os.path.join(BASE_DIR, "export_events.csv"))
        rounds_df = pd.read_csv(os.path.join(BASE_DIR, "export_rounds.csv"), usecols=['competition_id', 'id', 'round_type_id'])
        contests_df = pd.read_csv(os.path.join(BASE_DIR, "export_contests.csv"))
        
        # Merge competition start dates into results for accurate chronological sorting
        contests_dates = contests_df[['competition_id', 'start_date']].copy()
        res_df = res_df.merge(contests_dates, on='competition_id', how='left')
        res_df['start_date'] = pd.to_datetime(res_df['start_date'])

        # --- FILTERING LOGIC ---
        res_df = res_df[(res_df['record_category'] != 'meetups') | (res_df['event_id'] == '333_cube_mile')]
        allowed_video = {'333mbo', '666bf', '777bf', '888bf', '999bf', '101010bf', '111111bf', '444mbf', '555mbf', '2345relay_bld', '234567relay_bld', '2345678relay_bld', 'miniguild_bld', 'minx_bld', 'minx444_bld', 'minx555_bld', 'minx2345relay_bld', 'pyram_crystal_bld', '333_speed_bld'}
        res_df = res_df[(res_df['record_category'] != 'video-based-results') | (res_df['event_id'].isin(allowed_video))]

        event_names = ev_df.set_index('event_id')['name'].to_dict()
        
        region_data = pers_df['region_code'].apply(get_region_info)
        pers_df['full_country'] = [x[0] for x in region_data]
        pers_df['continent'] = [x[1] for x in region_data]
        pers_df['id'] = pers_df['id'].astype(str)

        res_df = res_df.merge(rounds_df, left_on=['competition_id', 'round_id'], right_on=['competition_id', 'id'], how='left', suffixes=('', '_round'))
        res_df['pid_list'] = res_df['person_ids'].apply(lambda x: ast.literal_eval(x) if str(x).startswith('[') else [x])
        res_exploded = res_df.explode('pid_list').rename(columns={'pid_list': 'person_id'})
        res_exploded['person_id'] = res_exploded['person_id'].astype(str)
        
        GLOBAL_DATA = {
            'res': res_df, 'exp': res_exploded, 'pers': pers_df, 
            'ev': event_names, 'cont': contests_df
        }
        return GLOBAL_DATA['res'], GLOBAL_DATA['exp'], GLOBAL_DATA['pers'], GLOBAL_DATA['ev'], GLOBAL_DATA['cont']
    except Exception as e:
        print(f"Data Loading Error: {e}")
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), {}, pd.DataFrame()
# Add this near your other helpers
def get_event_icon_tag(event_id):
    # --- WCA OFFICIAL EVENTS ---
    # Using the 'cubing-icon' class which is usually a font-face
    wca_events = {
        '333','222','444','555','666','777','333bf','333fm','333oh',
        'clock','minx','pyram','skewb','sq1','444bf','555bf',
        '333mbf','333ft','333mbo','magic','mmagic'
    }

    if event_id in wca_events:
        return f'<span class="cubing-icon event-{event_id}"></span>'

    # --- SPECIAL CASES (naming mismatch) ---
    special_map = {
        'gear_cube': 'gear',
        'ivy_cube': 'ivy',
        'corner_heli222': 'corner_helicopter_222'
    }
    
    icon_name = special_map.get(event_id, event_id)

    # --- UPDATED LOGIC ---
    # We combine local and github logic into one cleaner img tag 
    # to avoid the "red <" syntax errors caused by complex multi-line strings.
    return f'''<img src="https://raw.githubusercontent.com/cubing/icons/main/src/svg/unofficial/{icon_name}.svg" 
                class="event-icon" 
                alt="{event_id}" 
                onerror="this.onerror=null; this.src='/static/icons/{event_id}.svg'; this.style.color='transparent';">'''

# Register it so you can use it in HTML
app.jinja_env.globals.update(get_icon=get_event_icon_tag)
@app.route('/', methods=['GET', 'POST'])
def kinch_leaderboard():
    selected_events = request.form.getlist('events') if request.method == 'POST' else request.args.getlist('events')
    target_region = (request.form.get('region') if request.method == 'POST' else request.args.get('region')) or 'All'
    
    if not selected_events: selected_events = CORE_AVG + CORE_SIN

    _, res_exploded, persons, event_names, _ = load_and_process_data()
    if res_exploded.empty: return "Internal Server Error: Data could not be loaded. Check Vercel logs.", 500

    unique_countries = sorted(persons['full_country'].unique().tolist())

    if target_region != "All":
        rel_ids = persons[(persons['full_country'] == target_region) | (persons['continent'] == target_region)]['id'].unique()
        df = res_exploded[res_exploded['person_id'].isin(rel_ids)].copy()
    else:
        df = res_exploded.copy()

    df = df[df['event_id'].isin(selected_events)]
    valid = df[df['best'] > 0].copy()
    
    if valid.empty:
        return render_template('leaderboard.html', leaderboard=[], event_names=event_names, 
                               event_ids=selected_events, all_events=ALL_TARGET_EVENTS,
                               regions=unique_countries, current_region=target_region, continents=CONTINENTS,
                               CORE_AVG=CORE_AVG, CORE_SIN=CORE_SIN)

    pb_avg = valid[valid['average'] > 0].groupby(['person_id', 'event_id'])['average'].min().unstack()
    pb_sin = valid.groupby(['person_id', 'event_id'])['best'].min().unstack()
    bench_avg, bench_sin = pb_avg.min(), pb_sin.min()

    kinch_matrix = pd.DataFrame(index=pb_sin.index).reindex(columns=selected_events)
    for ev in selected_events:
        if ev in AVG_EVENTS:
            if ev in pb_avg.columns and ev in bench_avg.index:
                kinch_matrix[ev] = (bench_avg[ev] / pb_avg[ev] * 100)
        else:
            if ev in pb_sin.columns and ev in bench_sin.index:
                kinch_matrix[ev] = (bench_sin[ev] / pb_sin[ev] * 100)

    kinch_matrix = kinch_matrix.fillna(0.0)
    kinch_matrix['total'] = kinch_matrix[selected_events].sum(axis=1) / len(selected_events)
    
    leaderboard = kinch_matrix.merge(persons[['id', 'name', 'wca_id', 'full_country']], left_index=True, right_on='id')
    leaderboard = leaderboard[leaderboard['total'] > 0].sort_values('total', ascending=False)
    
    final_data = [{
        'rank': i + 1, 'id': row['id'], 'name': row['name'],
        'wca_id': row['wca_id'] if pd.notna(row['wca_id']) and row['wca_id'] != "" else "-",
        'region': row['full_country'], 'total': round(row['total'], 2),
        'scores': {ev: round(row.get(ev, 0.0), 1) for ev in selected_events}
    } for i, row in enumerate(leaderboard.head(500).to_dict('records'))]

    return render_template('leaderboard.html', leaderboard=final_data, event_names=event_names, 
                           event_ids=selected_events, all_events=ALL_TARGET_EVENTS,
                           regions=unique_countries, current_region=target_region, continents=CONTINENTS,
                           CORE_AVG=CORE_AVG, CORE_SIN=CORE_SIN)

def format_round(r):
    return {'f': 'Final', 's': 'Semi Final', '1': 'First Round', '2': 'Second Round', '3': 'Third Round'}.get(str(r), str(r))

@app.route('/person/<person_id>')
def person_profile(person_id):
    _, res_exploded, pers_df, event_names, contests_df = load_and_process_data()
    p_row = pers_df[pers_df['id'] == person_id]
    if p_row.empty: return "Person not found", 404
    
    person = p_row.iloc[0].to_dict()
    country, continent = person['full_country'], person['continent']
    p_res = res_exploded[res_exploded['person_id'] == person_id].copy()

    # --- SAFETY FIX: Ensure IDs are strings and Rankings are numbers ---
    p_res['competition_id'] = p_res['competition_id'].apply(lambda x: str(x) if pd.notna(x) else "")
    p_res['ranking'] = pd.to_numeric(p_res['ranking'], errors='coerce').fillna(0)

    # --- SORTING LOGIC FOR FINAL OVER FIRST ROUND ---
    # Define priority: Finals (f) -> Semi (s) -> Round 3 -> Round 2 -> Round 1
    round_priority = {'f': 0, 's': 1, '3': 2, '2': 3, '1': 4}
    p_res['round_rank'] = p_res['round_type_id'].map(round_priority).fillna(9)
    
    # Sort by date (Most Recent) then by Round Rank (Final on top)
    p_res = p_res.sort_values(by=['start_date', 'round_rank'], ascending=[False, True])

    medals = {
        'gold': int((p_res['ranking'] == 1).sum()),
        'silver': int((p_res['ranking'] == 2).sum()),
        'bronze': int((p_res['ranking'] == 3).sum())
    }

    wr_count = (p_res['regional_single_record'] == 'WR').sum() + (p_res['regional_average_record'] == 'WR').sum()
    nr_count = (p_res['regional_single_record'] == 'NR').sum() + (p_res['regional_average_record'] == 'NR').sum()
    cr_list = ['AfR', 'AsR', 'ER', 'NAR', 'OcR', 'SAR']
    cr_count = p_res['regional_single_record'].isin(cr_list).sum() + p_res['regional_average_record'].isin(cr_list).sum()

    pbs = p_res.groupby('event_id').agg({'best': 'min', 'average': lambda x: x[x > 0].min() if not x[x > 0].empty else 0}).to_dict('index')
    
    grouped_results = {}
    
    # Map competition names for the results tab
    comp_name_map = contests_df.set_index('competition_id')['name'].to_dict()

    for eid in p_res['event_id'].unique():
        ev_list = []
        event_results = p_res[p_res['event_id'] == eid]
        
        # Chronological sort (Oldest First) for historical PR calculation
        chronological = event_results.sort_values(by='start_date', ascending=True)
        running_best_single = float('inf')
        running_best_avg = float('inf')
        history_meta = {}

        for idx, row in chronological.iterrows():
            is_pr_single = (0 < row['best'] < running_best_single)
            is_pr_avg = (0 < row['average'] < running_best_avg)
            if is_pr_single: running_best_single = row['best']
            if is_pr_avg: running_best_avg = row['average']
            history_meta[idx] = {'pr_s': is_pr_single, 'pr_a': is_pr_avg}

        # Build list using the already sorted p_res (Recent First + Final on top)
        for idx, row in event_results.iterrows():
            try:
                try:
                    raw_attempts = row['attempts']
                    atts = ast.literal_eval(raw_attempts) if isinstance(raw_attempts, str) and raw_attempts.startswith('[') else []
                    raw_results = [a.get('result', 0) for a in atts if isinstance(a, dict)]
                except:
                    raw_results = []
                
                f_solves = []
                if len(raw_results) == 5:
                    proc_values = [v if v > 0 else float('inf') for v in raw_results]
                    best_idx, worst_idx = proc_values.index(min(proc_values)), proc_values.index(max(proc_values))
                    for i, v in enumerate(raw_results):
                        time_str = "DNF" if v == -1 else "DNS" if v == -2 else format_time(v, eid)
                        f_solves.append(f"({time_str})" if i == best_idx or i == worst_idx else time_str)
                else:
                    f_solves = ["DNF" if v == -1 else "DNS" if v == -2 else format_time(v, eid) for v in raw_results]
                
                solves_joined = " ".join(f_solves)
            except:
                solves_joined = "-"

            s_label = row.get('regional_single_record') if pd.notna(row.get('regional_single_record')) else None
            a_label = row.get('regional_average_record') if pd.notna(row.get('regional_average_record')) else None
            meta = history_meta.get(idx, {'pr_s': False, 'pr_a': False})

            # Logic to handle Red/Pink text classes
            s_class = "pink-text" if s_label else ("red-text" if meta['pr_s'] else "")
            a_class = "pink-text" if a_label else ("red-text" if meta['pr_a'] else "")

            ev_list.append({
                'competition_id': str(row['competition_id']),
                'competition_name': comp_name_map.get(row['competition_id'], row['competition_id']),
                'event_name': event_names.get(eid, eid),
                'round_name': format_round(row.get('round_type_id', row.get('round_id', "-"))),
                'round_id': row.get('round_type_id', row.get('round_id', "-")),
                'ranking': int(row['ranking']) if row['ranking'] > 0 else "-",
                'single_formatted': format_time(row['best'], eid),
                'average_formatted': format_time(row['average'], eid, True) if row['average'] != 0 else "-",
                's_label': s_label, 'a_label': a_label,
                's_class': s_class, 'a_class': a_class,
                'solves': solves_joined
            })
        grouped_results[eid] = ev_list

    # --- PB Calculation for Records Tab ---
    all_pbs = res_exploded.groupby(['person_id', 'event_id']).agg({'best': 'min', 'average': lambda x: x[x > 0].min() if not x[x > 0].empty else 0}).reset_index()
    all_pbs = all_pbs.merge(pers_df[['id', 'full_country', 'continent']], left_on='person_id', right_on='id')

    records_tab_data = []
    for eid in ALL_TARGET_EVENTS:
        if eid not in pbs: continue
        my_sin, my_avg = pbs[eid]['best'], pbs[eid]['average']
        def get_rank(val, field, r_field=None, r_val=None):
            if val <= 0: return "-"
            data = all_pbs[all_pbs['event_id'] == eid]
            if r_field: data = data[data[r_field] == r_val]
            return (data[(data[field] > 0) & (data[field] < val)]['person_id'].nunique() + 1)

        records_tab_data.append({
            'event_id': eid, 'event_name': event_names.get(eid, eid), 'single': my_sin, 'average': my_avg,
            'wr_s': get_rank(my_sin, 'best'), 'cr_s': get_rank(my_sin, 'best', 'continent', continent),
            'nr_s': get_rank(my_sin, 'best', 'full_country', country),
            'wr_a': get_rank(my_avg, 'average'), 'cr_a': get_rank(my_avg, 'average', 'continent', continent),
            'nr_a': get_rank(my_avg, 'average', 'full_country', country),
        })

    return render_template('profile.html', person=person, records=records_tab_data, 
                            stats={'comps': p_res['competition_id'].nunique(), 'solves': len(p_res), 'medals': medals, 'records': {'wr': int(wr_count), 'cr': int(cr_count), 'nr': int(nr_count)}}, 
                            grouped_results=grouped_results, format_time=format_time)

@app.route('/competition/<competition_id>')
def competition_page(competition_id):
    res_df, _, pers_df, event_names, contests_df = load_and_process_data()
    
    # 1. Load event order from CSV
    ev_df = pd.read_csv(os.path.join(BASE_DIR, "export_events.csv"))
    ev_df = ev_df.sort_values('id')
    ordered_events = ev_df['event_id'].tolist()
    event_order = ev_df.set_index('event_id')['id'].to_dict()

    # 2. Get Competition Metadata
    comp_info = contests_df[contests_df['competition_id'] == competition_id]
    display_name = comp_info.iloc[0]['name'] if not comp_info.empty else competition_id.replace('_', ' ')
    location = f"{comp_info.iloc[0]['city']}, {comp_info.iloc[0]['venue']}" if not comp_info.empty else "Unknown Location"
    date_val = str(comp_info.iloc[0]['start_date']).split('T')[0] if not comp_info.empty else ""

    # 3. Filter and Prepare Results
    comp_results = res_df[res_df['competition_id'] == competition_id].copy()
    comp_results['pid_list'] = comp_results['person_ids'].apply(
        lambda x: ast.literal_eval(x) if str(x).startswith('[') else [x]
    )
    comp_results['sort_order'] = comp_results['event_id'].map(event_order).fillna(999)
    comp_results = comp_results.sort_values('sort_order')

    # Constants and Setup
    ROUND_NAMES = {'f': 'Final', 's': 'Semi-final', 'd': 'Second Round', '1': 'First Round', '2': 'Second Round', '3': 'Third Round'}
    round_priority = {'f': 0, 's': 1, '3': 2, '2': 3, '1': 4}
    
    podiums = {}
    winners_list = []
    all_rounds = {}
    results_by_person = {}

    # --- 4. Logic for "By Person" Tab (Updated with Parentheses Logic) ---
    person_exploded = comp_results.explode('pid_list')
    
    for _, row in person_exploded.iterrows():
        pid = str(row['pid_list'])
        if pid not in results_by_person:
            p_info = pers_df[pers_df['id'] == pid]
            results_by_person[pid] = {
                'name': p_info.iloc[0]['name'] if not p_info.empty else "Unknown",
                'representing': p_info.iloc[0]['full_country'] if not p_info.empty else "Unknown",
                'results': []
            }
        
        eid = row['event_id']
        attempts = ast.literal_eval(row['attempts'])
        raw = [a['result'] for a in attempts]
        
        # Calculate indices for Ao5 parentheses
        b_idx = w_idx = -1
        if len(raw) == 5:
            valid = [v if v > 0 else float('inf') for v in raw]
            b_idx, w_idx = valid.index(min(valid)), valid.index(max(valid))

        # Format solve strings with parentheses
        formatted_solves = []
        for i, v in enumerate(raw):
            time_str = "DNF" if v == -1 else "DNS" if v == -2 else format_time(v, eid)
            if i == b_idx or i == w_idx:
                formatted_solves.append(f"({time_str})")
            else:
                formatted_solves.append(time_str)
        
        results_by_person[pid]['results'].append({
            'event_id': eid,
            'event_name': event_names.get(eid, eid),
            'round_name': ROUND_NAMES.get(row['round_type_id'], row['round_type_id']),
            'rank': int(row['ranking']),
            'best': format_time(row['best'], eid),
            'average': format_time(row['average'], eid, True) if row['average'] > 0 else "-",
            'solves': formatted_solves # Updated to use list with parentheses
        })

    results_by_person = dict(sorted(results_by_person.items(), key=lambda item: item[1]['name']))

    # --- 5. Logic for "All Results" Tab (Updated to apply parentheses) ---
    for eid in ordered_events:
        event_all_data = comp_results[comp_results['event_id'] == eid]
        if not event_all_data.empty:
            all_rounds[eid] = {'event_name': event_names.get(eid, eid), 'rounds': []}
            avail_rounds = sorted(event_all_data['round_type_id'].unique(), key=lambda x: round_priority.get(x, 9))
            
            for rid in avail_rounds:
                round_df = event_all_data[event_all_data['round_type_id'] == rid].sort_values('ranking')
                round_results = []
                for _, row in round_df.iterrows():
                    pids = row.get('pid_list', [])
                    p_info = pers_df[pers_df['id'] == str(pids[0])] if pids else pd.DataFrame()
                    attempts = ast.literal_eval(row['attempts'])
                    raw = [a['result'] for a in attempts]
                    
                    b_idx = w_idx = -1
                    if len(raw) == 5:
                        valid = [v if v > 0 else float('inf') for v in raw]
                        b_idx, w_idx = valid.index(min(valid)), valid.index(max(valid))

                    # Apply parentheses to the solves list
                    formatted_solves = []
                    for i, v in enumerate(raw):
                        time_str = "DNF" if v == -1 else "DNS" if v == -2 else format_time(v, eid)
                        if i == b_idx or i == w_idx:
                            formatted_solves.append(f"({time_str})")
                        else:
                            formatted_solves.append(time_str)

                    round_results.append({
                        'rank': int(row['ranking']),
                        'person_id': str(pids[0]) if pids else "#",
                        'name': p_info.iloc[0]['name'] if not p_info.empty else "Unknown",
                        'representing': p_info.iloc[0]['full_country'] if not p_info.empty else "Unknown",
                        'best': format_time(row['best'], eid),
                        'average': format_time(row['average'], eid, True) if row['average'] > 0 else "-",
                        'solves': formatted_solves,
                        'best_idx': b_idx, 'worst_idx': w_idx
                    })
                all_rounds[eid]['rounds'].append({'round_name': ROUND_NAMES.get(rid, f"Round {rid}"), 'results': round_results})

    # --- 6. Logic for Winners & Podiums (Updated to apply parentheses) ---
    finals = comp_results[comp_results['round_type_id'] == 'f']
    for eid in ordered_events:
        if eid not in finals['event_id'].values: continue
        event_finals = finals[finals['event_id'] == eid].sort_values('ranking')
        results_list = []
        
        for _, row in event_finals[event_finals['ranking'] <= 3].iterrows():
            pids = row.get('pid_list', [])
            members = []
            for pid in pids:
                p_info = pers_df[pers_df['id'] == str(pid)]
                if not p_info.empty:
                    members.append({'id': str(pid), 'name': p_info.iloc[0]['name'], 'country': p_info.iloc[0]['full_country']})
            
            attempts = ast.literal_eval(row['attempts'])
            raw = [a['result'] for a in attempts]
            b_idx = w_idx = -1
            if len(raw) == 5:
                valid = [v if v > 0 else float('inf') for v in raw]
                b_idx, w_idx = valid.index(min(valid)), valid.index(max(valid))

            formatted_solves = []
            for i, v in enumerate(raw):
                time_str = "DNF" if v == -1 else "DNS" if v == -2 else format_time(v, eid)
                if i == b_idx or i == w_idx:
                    formatted_solves.append(f"({time_str})")
                else:
                    formatted_solves.append(time_str)

            formatted_res = {
                'person_id': members[0]['id'] if members else "#",
                'name': members[0]['name'] if members else "Unknown",
                'representing': members[0]['country'] if members else "Unknown",
                'best': format_time(row['best'], eid),
                'average': format_time(row['average'], eid, True) if row['average'] > 0 else "-",
                'solves': formatted_solves,
                'best_idx': b_idx, 'worst_idx': w_idx
            }
            results_list.append(formatted_res)

            if row['ranking'] == 1:
                winners_list.append({
                    'event_id': eid, 'event_name': event_names.get(eid, eid),
                    'team_members': members, 'representing': ", ".join(set(m['country'] for m in members)),
                    'best': formatted_res['best'], 'average': formatted_res['average'] if row['average'] > 0 else None,
                    'solves': formatted_solves, 'best_idx': b_idx, 'worst_idx': w_idx
                })
        podiums[eid] = {'event_id': eid, 'event_name': event_names.get(eid, eid), 'results': results_list}

    return render_template('competition.html', 
                           comp_name=display_name, 
                           comp_location=location, 
                           comp_date=date_val, 
                           winners=winners_list, 
                           podiums=podiums,
                           all_rounds=all_rounds,
                           results_by_person=results_by_person,
                           competition_id=competition_id)
app = app
if __name__ == '__main__':
    # Enable debug mode as requested
    app.run(debug=True)