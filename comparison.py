import logging
from flask import Blueprint, jsonify, request, render_template

# --- WCA Data Module Imports ---
from wca_data import get_all_wca_persons_data, get_all_wca_comparison_data, is_wca_data_loaded

# --- Logging ---
logger = logging.getLogger(__name__)

# --- Blueprint ---
comparison_bp = Blueprint("comparison_bp", __name__)

# --- Constants ---
MAX_RESULTS = 100

EVENT_MAP = {
    "3x3": "333",
    "2x2": "222",
    "4x4": "444",
    "5x5": "555",
    "6x6": "666",
    "7x7": "777",
    "3x3 Blindfolded": "333bf",
    "3x3 One-Handed": "333oh",
    "3x3 Fewest Moves": "333fm",
    "Clock": "clock",
    "Megaminx": "minx",
    "Pyraminx": "pyram",
    "Square-1": "sq1",
    "Skewb": "skewb",
    "4x4 Blindfolded": "444bf",
    "5x5xBlindfolded": "555bf",
    "3x3 Multi-Blind": "333mbf"
}
REVERSE_EVENT_MAP = {v: k for k, v in EVENT_MAP.items()}

# --- Utility Functions ---
def format_result(event_id, result):
    if not result or result <= 0:
        return "DNF"
    if event_id == "333fm":
        return f"{result} moves"
    if event_id == "333mbf":
        value_str = str(result).rjust(10, "0")
        time_in_seconds = int(value_str[3:8] if value_str.startswith("0") else value_str[5:10])
        minutes = time_in_seconds // 60
        seconds = time_in_seconds % 60
        return f"{minutes}:{seconds:02d}"
    total_seconds = result / 100.0
    minutes = int(total_seconds // 60)
    seconds = int(total_seconds % 60)
    milliseconds = int((total_seconds * 100) % 100)
    if total_seconds >= 600:
        milliseconds = 0
    return f"{minutes:02d}:{seconds:02d}.{milliseconds:02d}"

# --- Core Logic ---
def find_fastest_comparisons(event1, event2):
    """Retrieves pre-computed comparison data from the central store."""
    if not is_wca_data_loaded():
        return None
    comparison_data = get_all_wca_comparison_data()
    
    # Ensure a consistent key order
    key = tuple(sorted((event1, event2)))
    
    # The pre-computed data is already sorted and capped
    results = comparison_data.get(key, [])
    
    # If the original request was event2 > event1, re-order the results
    if event1 == key[0] and event2 == key[1]:
        return results
    else:
        formatted = []
        for r in results:
            formatted.append({
                "name": r["name"], "wca_id": r["wca_id"], "country": r["country"],
                "best1": r["best2"], "best2": r["best1"], "diff": -r["diff"]
            })
        return formatted


# ---------------- Routes ----------------
@comparison_bp.route('/')
def comparison_home():
    return render_template('comparison.html')

@comparison_bp.route('/compare_events', methods=['GET'])
def api_compare_events():
    event1_name_short = request.args.get('event1')
    event2_name_short = request.args.get('event2')
    
    if not event1_name_short or not event2_name_short:
        return jsonify({"error": "Missing event1 or event2"}), 400
    
    event1_id = EVENT_MAP.get(event1_name_short)
    event2_id = EVENT_MAP.get(event2_name_short)
    
    if not event1_id or not event2_id:
        return jsonify({"error": "Invalid event ID"}), 400
    
    if event1_id == event2_id:
        return jsonify({"error": "Cannot compare an event to itself."}), 400

    results = find_fastest_comparisons(event1_id, event2_id)
    
    if results is None:
        return jsonify({"error": "Core competitor data is still loading."}), 503

    formatted = [{
        "name": r["name"], "wca_id": r["wca_id"], "country": r["country"],
        "event1_name": REVERSE_EVENT_MAP.get(event1_id), "event1_time": format_result(event1_id, r["best1"]),
        "event2_name": REVERSE_EVENT_MAP.get(event2_id), "event2_time": format_result(event2_id, r["best2"]),
        "time_difference_s": r["diff"]
    } for r in results]
    
    return jsonify({"data": formatted, "message": f"Competitors with faster {REVERSE_EVENT_MAP.get(event1_id)} than {REVERSE_EVENT_MAP.get(event2_id)}"})