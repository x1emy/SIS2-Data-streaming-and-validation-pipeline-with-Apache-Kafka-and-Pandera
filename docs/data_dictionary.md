# Data Dictionary — table `collisions` (data/output.db)

One row = one motor vehicle collision in New York City.

| Column | Type | Description |
|---|---|---|
| collision_id | TEXT, PK | Unique collision identifier (32-character hash) |
| crash_datetime | TEXT (datetime) | Date and time of the crash (combined) |
| crash_date | TEXT (date) | Date of the crash |
| crash_time | TEXT (HH:MM) | Time of the crash |
| borough | TEXT | NYC borough; "Unknown" if not reported |
| zip_code | TEXT | ZIP code; "Unknown" if not reported |
| latitude, longitude | REAL | Coordinates within NYC; NULL if not reported |
| on_street_name, cross_street_name | TEXT | Street names (upper case); "UNKNOWN" if missing |
| number_of_persons_injured / killed | INTEGER | Total injured / killed persons (≥ 0) |
| number_of_pedestrians_injured / killed | INTEGER | Injured / killed pedestrians |
| number_of_cyclist_injured / killed | INTEGER | Injured / killed cyclists |
| number_of_motorist_injured / killed | INTEGER | Injured / killed motorists |
| contributing_factor_vehicle_1 / 2 | TEXT | Reported cause for vehicle 1 / 2; "Unspecified" if missing |
| vehicle_type_code1 / 2 | TEXT | Type of vehicle 1 / 2; "Unknown" if missing |
| num_vehicles | INTEGER | Number of vehicles involved (derived with NumPy) |
| hour | INTEGER | Hour of the crash, 0–23 (derived) |
| day_of_week | TEXT | Day name (derived) |
| is_weekend | INTEGER (0/1) | 1 if Saturday or Sunday (derived) |
| total_casualties | INTEGER | Injured + killed (derived) |
| severity | TEXT | "Fatal", "Injury" or "Property damage only" (derived) |
| time_of_day | TEXT | Night (0–5), Morning (6–11), Afternoon (12–17), Evening (18–23) (derived) |

Source columns removed during cleaning: `location` (nested duplicate of coordinates) and columns with more than 70% missing values (`off_street_name`, vehicle/factor 3–5).