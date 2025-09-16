import os
import sys
import time
import json
import logging
from flask import Flask, jsonify, request, render_template
from dotenv import load_dotenv
from collections import defaultdict

# Load environment variables from .env file
load_dotenv()

# --- App Initialization ---
app = Flask(__name__)
app.logger.setLevel(logging.INFO)

# --- WCA Data Module Imports ---
from wca_data import get_all_wca_persons_data, is_wca_data_loaded, continent_map

# --- Continent Scope Mapping ---
CONTINENT_SCOPES = {
    "africa": "af",
    "asia": "as",
    "europe": "eu",
    "north-america": "na",
    "south-america": "sa",
    "oceania": "oc",
}

# --- API Route Functions ---
def find_and_format_rank(scope_str: str, ranking_type: str, event_id: str, rank_number: int):
    if not is_wca_data_loaded():
        return jsonify({"error": "Core competitor data is still loading."}), 503

    ranking_type_norm = None
    if ranking_type in ["single", "singles"]:
        ranking_type_norm = "singles"
    elif ranking_type in ["average", "averages"]:
        ranking_type_norm = "averages"
    else:
        return jsonify({"error": "Invalid ranking type. Use 'single'/'singles' or 'average'/'averages'."}), 400

    if not isinstance(rank_number, int) or rank_number <= 0:
        return jsonify({"error": "Rank number must be a positive integer."}), 400

    requested_scopes = [s.strip().lower().replace(" ", "-") for s in scope_str.split(",") if s.strip()]
    if not requested_scopes:
        return jsonify({"error": "Invalid scope provided."}), 400

    # Collect all eligible competitors for the given scope, event, and ranking type
    eligible_competitors = []
    persons_data = get_all_wca_persons_data()
    if not persons_data:
        return jsonify({"error": "Failed to retrieve competitor data."}), 500

    for person in persons_data.values():
        person_country = person.get("country", "").lower()
        person_continent = continent_map.get(person_country.upper(), "").lower()

        is_eligible_scope = False
        for scope_key in requested_scopes:
            if scope_key == "world":
                is_eligible_scope = True
                break
            elif scope_key in CONTINENT_SCOPES and scope_key == person_continent:
                is_eligible_scope = True
                break
            elif scope_key == person_country:
                is_eligible_scope = True
                break

        if not is_eligible_scope:
            continue

        ranks = person.get("rank", {})
        events = ranks.get(ranking_type_norm, [])
        for event_info in events:
            if event_info.get("eventId") == event_id:
                best_result = event_info.get("best")
                if best_result is not None:
                    eligible_competitors.append({
                        "wca_id": person.get("id"),
                        "result": best_result
                    })
                break

    if not eligible_competitors:
        return jsonify({"error": f"No ranks found for {event_id} in scopes '{scope_str}'."}), 404

    # Sort competitors by result
    sorted_competitors = sorted(eligible_competitors, key=lambda x: x["result"])
    
    # Apply Standard Competition Ranking (min method)
    ranked_competitors = []
    current_rank = 1
    i = 0
    while i < len(sorted_competitors):
        tied_competitors = []
        current_result = sorted_competitors[i]['result']
        j = i
        while j < len(sorted_competitors) and sorted_competitors[j]['result'] == current_result:
            person_data = persons_data.get(sorted_competitors[j]['wca_id'])
            if person_data:
                tied_competitors.append({
                    "person": {
                        "name": person_data.get("name"),
                        "wcaId": person_data.get("id"),
                        "countryIso2": person_data.get("country")
                    },
                    "result": sorted_competitors[j]['result'],
                    "actualRank": current_rank
                })
            j += 1

        ranked_competitors.extend(tied_competitors)
        current_rank = len(ranked_competitors) + 1
        i = j

    # Check for the requested rank. If it's too high, return an error.
    max_rank = ranked_competitors[-1]['actualRank'] if ranked_competitors else 0
    if rank_number > max_rank:
        return jsonify({
            "error": f"Requested rank #{rank_number} is out of the valid range. The highest rank for this selection is #{max_rank}."
        }), 404
    
    # Find the requested rank
    found_competitors = [comp for comp in ranked_competitors if comp['actualRank'] == rank_number]
    
    # If not found (due to a tie), find the closest rank
    if not found_competitors:
        for comp in ranked_competitors:
            if comp['actualRank'] >= rank_number:
                found_competitors = [c for c in ranked_competitors if c['actualRank'] == comp['actualRank']]
                break

    # Add a message if the requested rank was not found but a nearby rank was
    if found_competitors and found_competitors[0]['actualRank'] != rank_number:
        for comp in found_competitors:
            comp['note'] = f"Requested rank #{rank_number} not found. Displaying nearest competitor(s) at rank #{comp['actualRank']} instead."
    
    # If there are multiple competitors, indicate a tie
    if len(found_competitors) > 1:
        for comp in found_competitors:
            comp['isTie'] = True

    if not found_competitors:
        return jsonify({"error": "Failed to retrieve competitor data for the nearest rank."}), 500

    return jsonify({"competitors": found_competitors})

# --- App Routes ---
@app.route("/")
def index():
    if not is_wca_data_loaded():
        return "Data is loading, please wait...", 503
    return render_template('index.html')

@app.route("/competitors")
def competitors():
    if not is_wca_data_loaded():
        return "Data is loading, please wait...", 503
    return render_template('competitors.html')

@app.route("/completionist")
def completionist():
    if not is_wca_data_loaded():
        return "Data is loading, please wait...", 503
    return render_template('completionist.html')

@app.route("/specialist")
def specialist():
    if not is_wca_data_loaded():
        return "Data is loading, please wait...", 503
    return render_template('specialist.html')

# --- Add this route for the new page ---
@app.route("/comparison")
def comparison():
    if not is_wca_data_loaded():
        return "Data is loading, please wait...", 503
    return render_template('comparison.html')

@app.route("/api/global-rankings/<scope>/<ranking_type>/<event_id>")
def get_global_rankings(scope, ranking_type, event_id):
    rank_number = request.args.get("rankNumber", type=int)
    if not rank_number:
        return jsonify({"error": "Missing rankNumber"}), 400
    return find_and_format_rank(scope, ranking_type, event_id, rank_number)

@app.route("/api/rankings/<scope>/<event_id>/<ranking_type>/<int:rank_number>")
def get_rankings(scope: str, event_id: str, ranking_type: str, rank_number: int):
    return find_and_format_rank(scope, ranking_type, event_id, rank_number)

# --- Blueprint Imports ---
from competitors import competitors_bp
from completionist import completionists_bp
from specialist import specialist_bp
from comparison import comparison_bp # <-- ADD THIS LINE

app.register_blueprint(competitors_bp, url_prefix="/api")
app.register_blueprint(completionists_bp, url_prefix="/api")
app.register_blueprint(specialist_bp, url_prefix="/api")
app.register_blueprint(comparison_bp, url_prefix="/api/comparison") # <-- AND THIS LINE

# --- Main Execution ---
if __name__ == "__main__":
    app.logger.info("Starting Flask application...")
    app.run(host="0.0.0.0", port=5000)