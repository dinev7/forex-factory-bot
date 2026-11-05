def load_airport_data():
    """Load airport data from a local JSON file."""
    import json

    try:
        with open("airport.json", "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        raise RuntimeError(
            "airports.json file not found. Please ensure it exists in the current directory."
        )
    except json.JSONDecodeError as e:
        raise RuntimeError(f"Error decoding airports.json: {e}")


data = load_airport_data()


latCalc = data["airports"]["code{LAX}"]["lat"]
print(latCalc)  # Output: 33.9416
