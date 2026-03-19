from flask import Flask, render_template, request
from flask_caching import Cache
import pandas as pd
import numpy as np
import ast
import pycountry
import pycountry_convert as pc
import os

app = Flask(__name__)
app.debug = True 

# --- CACHE CONFIGURATION ---
# Simple cache is best for Vercel's ephemeral nature
cache = Cache(app, config={'CACHE_TYPE': 'simple'})

# --- CONFIGURATION ---
CORE_AVG = ['fto', '333_team_bld', '333_mirror_blocks', '333_mirror_blocks_bld', 'mpyram', 'kilominx', 'redi', 'magic', 'mmagic', '333_linear_fm', '333ft']
CORE_SIN = ['333_speed_bld', 'miniguild', 'miniguild_2_person', '333mts']
MISC_AVG_EVENTS = ['222_blanker', '222_mirror_blocks', '444_mirror_blocks', '555_mirror_blocks', 'fisher', '333_windmill_cube', '333_axis_cube', '333_twist_cube', '333_void', '333_cube_mile', '333_siamese', '223_cuboid', '233_cuboid', '334_cuboid', 'super_133', '888', '999', '101010', 'mkilominx', 'gigaminx', 'baby_fto', 'mfto', 'cto', '2pentahedron', '3pentahedron', 'pyramorphix', 'pyram_duo', 'dino', 'ivy_cube', 'rainbow_cube', 'corner_heli222', 'helicopter', 'curvycopter', 'gear_cube', 'super_gear_cube', 'magic_oh', '222fm', '444fm', 'snake', '15puzzle', '8puzzle','222oh','444oh','clock_oh','333_oven_mitts','333_paw_mitts','222bf','new_penta_clock','penta_clock']
MISC_SIN_EVENTS = ['333_bets', '333_supersolve', '333bf_bottle', '333_braille_bld','234567relay','2345relay_bld',]

AVG_EVENTS = set(CORE_AVG + MISC_AVG_EVENTS)
SIN_EVENTS = set(CORE_SIN + MISC_SIN_EVENTS)
ALL_TARGET_EVENTS = list(AVG_EVENTS | SIN_EVENTS)
CONTINENTS = ['Africa', 'Asia', 'Europe', 'North America', 'Oceania', 'South America']

# --- HELPERS ---
def format_time(value, event_id, is_avg=False):
    try:
        val_float = float(value)
        if val_float <= 0: return "-"
    except (ValueError, TypeError):
        return "-"
    
    if 'fm' in event_id.lower():
        return f"{val_float / 100.0:.2f}" if is_avg else str(int(val_float))

    seconds = int(val_float) / 100.0
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
    if GLOBAL_DATA:
        return GLOBAL_DATA['res'], GLOBAL_DATA['exp'], GLOBAL_DATA['pers'], GLOBAL_DATA['ev'], GLOBAL_DATA['cont']

    try:
        # Vercel Optimization: Read necessary columns + record_category for filtering
        res_df = pd.read_csv("export_results.csv", usecols=[
            'competition_id', 'person_ids', 'event_id', 'round_id', 'best', 
            'average', 'ranking', 'attempts', 'regional_single_record', 
            'regional_average_record', 'record_category'
        ])
        pers_df = pd.read_csv("export_persons.csv", usecols=['id', 'name', 'wca_id', 'region_code'])
        ev_df = pd.read_csv("export_events.csv")
        rounds_df = pd.read_csv("export_rounds.csv", usecols=['competition_id', 'id', 'round_type_id'])
        contests_df = pd.read_csv("export_contests.csv")
        
        # --- NEW FILTERING LOGIC ---
        
        # 1. Filter Meetups: Keep only if event is 333_cube_mile or category is NOT meetups
        res_df = res_df[
            (res_df['record_category'] != 'meetups') | 
            (res_df['event_id'] == '333_cube_mile')
        ]

        # 2. Filter Video-Based: Only allow specific events for video-based-results
        allowed_video_events = {
            '333mbo', '666bf', '777bf', '888bf', '999bf', '101010bf', 
            '111111bf', '444mbf', '555mbf', '2345relay_bld', '234567relay_bld', 
            '2345678relay_bld', 'miniguild_bld', 'minx_bld', 'minx444_bld', 
            'minx555_bld', 'minx2345relay_bld', 'pyram_crystal_bld', '333_speed_bld'
        }
        
        res_df = res_df[
            (res_df['record_category'] != 'video-based-results') | 
            (res_df['event_id'].isin(allowed_video_events))
        ]

        # --- END FILTERING LOGIC ---

        event_names = ev_df.set_index('event_id')['name'].to_dict()
        
        region_data = pers_df['region_code'].apply(get_region_info)
        pers_df['full_country'] = [x[0] for x in region_data]
        pers_df['continent'] = [x[1] for x in region_data]
        pers_df['id'] = pers_df['id'].astype(str)

        # Merge and Explode
        res_df = res_df.merge(rounds_df, left_on=['competition_id', 'round_id'], right_on=['competition_id', 'id'], how='left', suffixes=('', '_round'))

        res_df['pid_list'] = res_df['person_ids'].apply(lambda x: ast.literal_eval(x) if str(x).startswith('[') else [x])
        res_exploded = res_df.explode('pid_list').rename(columns={'pid_list': 'person_id'})
        res_exploded['person_id'] = res_exploded['person_id'].astype(str)
        
        GLOBAL_DATA.update({
            'res': res_df, 'exp': res_exploded, 'pers': pers_df, 
            'ev': event_names, 'cont': contests_df
        })
        return load_and_process_data()
    except Exception as e:
        print(f"File Error: {e}")
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), {}, pd.DataFrame()

@app.route('/', methods=['GET', 'POST'])
def kinch_leaderboard():
    selected_events = request.form.getlist('events') if request.method == 'POST' else request.args.getlist('events')
    target_region = (request.form.get('region') if request.method == 'POST' else request.args.get('region')) or 'All'
    
    if not selected_events: selected_events = CORE_AVG + CORE_SIN

    _, res_exploded, persons, event_names, _ = load_and_process_data()
    if res_exploded.empty: return "Error: Data missing."

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
                           CORE_AVG=CORE_AVG,    # <--- Add this
                           CORE_SIN=CORE_SIN)

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
                           CORE_AVG=CORE_AVG,    # <--- Add this
                           CORE_SIN=CORE_SIN)
def format_round(r):
    return {
        'f': 'Final',
        's': 'Semi Final',
        '1': 'First Round',
        '2': 'Second Round',
        '3': 'Third Round'
    }.get(str(r), str(r))
@app.route('/person/<person_id>')
def person_profile(person_id):
    _, res_exploded, pers_df, event_names, _ = load_and_process_data()
    p_row = pers_df[pers_df['id'] == person_id]
    if p_row.empty: return "Person not found", 404
    
    person = p_row.iloc[0].to_dict()
    country, continent = person['full_country'], person['continent']
    p_res = res_exploded[res_exploded['person_id'] == person_id].copy()

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
    for eid in p_res['event_id'].unique():
        ev_list = []
        for _, row in p_res[p_res['event_id'] == eid].iterrows():
            try:
                atts = ast.literal_eval(row['attempts'])
                f_solves = [("(DNF)" if a['result'] == -1 else "(DNS)" if a['result'] == -2 else format_time(a['result'], eid)) for a in atts]
                solves_joined = ", ".join(f_solves)
            except: solves_joined = "-"

            ev_list.append({
                'competition_id': row['competition_id'], 'event_name': event_names.get(eid, eid),
                'round_id': format_round(row.get('round_type_id', row.get('round_id', "-"))),
                'ranking': int(row['ranking']) if pd.notna(row['ranking']) else "-",
                'single_formatted': format_time(row['best'], eid),
                'average_formatted': format_time(row['average'], eid, True) if row['average'] > 0 else "-",
                'solves_joined': solves_joined, 'single_is_pb': row['best'] == pbs[eid]['best'],
                'average_is_pb': row['average'] == pbs[eid]['average'] and row['average'] > 0
            })
        grouped_results[eid] = ev_list

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
    comp_info = contests_df[contests_df['competition_id'] == competition_id]
    
    display_name = comp_info.iloc[0]['name'] if not comp_info.empty else competition_id.replace('_', ' ')
    location = f"{comp_info.iloc[0]['city']}, {comp_info.iloc[0]['venue']}" if not comp_info.empty else "Unknown Location"
    date_val = str(comp_info.iloc[0]['start_date']).split('T')[0] if not comp_info.empty else ""

    comp_results = res_df[res_df['competition_id'] == competition_id]
    winners_list = []
    
    # Process only winners with solves logic
    for _, row in comp_results[comp_results['ranking'] == 1].iterrows():
        eid = row['event_id']
        pids = row.get('pid_list', [])
        p_info = pers_df[pers_df['id'] == str(pids[0])] if pids else pd.DataFrame()
        
        try:
            atts = ast.literal_eval(row['attempts'])
            f_solves = [("(DNF)" if a['result'] == -1 else "(DNS)" if a['result'] == -2 else format_time(a['result'], eid)) for a in atts]
            solves_joined = ", ".join(f_solves)
        except: 
            solves_joined = "-"

        winners_list.append({
            'event_name': event_names.get(eid, eid),
            'winner_name': p_info.iloc[0]['name'] if not p_info.empty else "Unknown",
            'winner_id': pids[0] if pids else None,
            'representing': p_info.iloc[0]['full_country'] if not p_info.empty else "",
            'best': format_time(row['best'], eid),
            'average': format_time(row['average'], eid, True) if row['average'] > 0 else None,
            'solves_joined': solves_joined
        })

    return render_template('competition.html', comp_name=display_name, comp_location=location, comp_date=date_val, winners=winners_list)

# Vercel entry point
app = app

if __name__ == '__main__':
    app.run()