import os
import sqlite3
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns

DB_PATH = "data/output.db"
FIGURES_DIR = "figures"
TIME_ORDER = ["Night", "Morning", "Afternoon", "Evening"]
PLACEHOLDER_FACTORS = ["Unspecified", "Does Not Apply"]


def load_from_db(db_path=DB_PATH):
    """EDA строится на данных из SQLite"""
    with sqlite3.connect(db_path) as conn:
        df = pd.read_sql_query("SELECT * FROM collisions;", conn)
    df["crash_datetime"] = pd.to_datetime(df["crash_datetime"])
    df["has_injury"] = df["number_of_persons_injured"] > 0
    return df


def descriptive_statistics(df):
    print(f"Shape: {df.shape[0]} rows, {df.shape[1]} columns")
    print(f"Period: {df['crash_datetime'].min()} - {df['crash_datetime'].max()}")
    print("\nData types:")
    print(df.dtypes.value_counts().to_string())

    numeric_cols = ["number_of_persons_injured", "number_of_persons_killed",
                    "num_vehicles", "total_casualties", "hour"]
    print("\nNumerical statistics:")
    print(df[numeric_cols].describe().round(2).to_string())

    print("\nCategorical statistics:")
    for col in ["borough", "severity", "time_of_day", "vehicle_type_code1"]:
        top = df[col].value_counts().head(5)
        print(f"\n{col}: {df[col].nunique()} unique values, top 5:")
        print((top.to_frame("count").assign(percent=(top / len(df) * 100).round(1))).to_string())


def grouped_analysis(df):
    by_borough = (
        df.groupby("borough")
        .agg(crashes=("collision_id", "count"),
             injury_rate=("has_injury", "mean"),
             avg_injured=("number_of_persons_injured", "mean"))
        .assign(injury_rate=lambda t: (t["injury_rate"] * 100).round(1))
        .round(2).sort_values("crashes", ascending=False)
    )
    print("\nBy borough (injury_rate = % of crashes with at least one injured person):")
    print(by_borough.to_string())

    by_time = (
        df.groupby("time_of_day")
        .agg(crashes=("collision_id", "count"), injury_rate=("has_injury", "mean"))
        .reindex(TIME_ORDER)
        .assign(injury_rate=lambda t: (t["injury_rate"] * 100).round(1))
    )
    print("\nBy time of day:")
    print(by_time.to_string())

    by_vehicles = (
        df.groupby("num_vehicles")
        .agg(crashes=("collision_id", "count"), avg_injured=("number_of_persons_injured", "mean"))
        .round(2)
    )
    print("\nBy number of vehicles involved:")
    print(by_vehicles.to_string())
    return by_borough


def save(fig, name):
    path = os.path.join(FIGURES_DIR, name)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)
    print(f"Saved {path}")


def plot_crashes_by_hour(df):
    counts = df["hour"].value_counts().reindex(range(24), fill_value=0)
    fig, ax = plt.subplots(figsize=(10, 5))
    ax.bar(counts.index, counts.values, color="#4C72B0")
    ax.set_title("Number of crashes by hour of day")
    ax.set_xlabel("Hour of day")
    ax.set_ylabel("Number of crashes")
    ax.set_xticks(range(24))
    save(fig, "1_crashes_by_hour.png")


def plot_borough_comparison(by_borough):
    data = by_borough.drop(index="Unknown", errors="ignore")
    fig, ax1 = plt.subplots(figsize=(10, 5))
    ax1.bar(data.index, data["crashes"], color="#4C72B0", label="Crashes")
    ax1.set_xlabel("Borough")
    ax1.set_ylabel("Number of crashes")
    ax2 = ax1.twinx()
    ax2.plot(data.index, data["injury_rate"], color="#C44E52", marker="o", linewidth=2,
             label="Crashes with injuries, %")
    ax2.set_ylabel("Crashes with injuries, %")
    ax2.set_ylim(0, 100)
    lines = ax1.get_legend_handles_labels()[0] + ax2.get_legend_handles_labels()[0]
    labels = ax1.get_legend_handles_labels()[1] + ax2.get_legend_handles_labels()[1]
    ax1.legend(lines, labels, loc="upper right")
    ax1.set_title("Crashes and share of crashes with injuries by borough")
    save(fig, "2_borough_comparison.png")


def plot_top_factors(df):
    factors = df.loc[~df["contributing_factor_vehicle_1"].isin(PLACEHOLDER_FACTORS),
                     "contributing_factor_vehicle_1"].value_counts().head(10).sort_values()
    fig, ax = plt.subplots(figsize=(10, 6))
    ax.barh(factors.index, factors.values, color="#55A868")
    ax.set_title("Top 10 contributing factors (excluding 'Unspecified' / 'Does Not Apply')")
    ax.set_xlabel("Number of crashes")
    ax.set_ylabel("Contributing factor (vehicle 1)")
    save(fig, "3_top_contributing_factors.png")


def plot_heatmap(df):
    pivot = df.pivot_table(index="borough", columns="time_of_day", values="collision_id",
                           aggfunc="count", fill_value=0).reindex(columns=TIME_ORDER, fill_value=0)
    fig, ax = plt.subplots(figsize=(8, 5))
    sns.heatmap(pivot, annot=True, fmt="d", cmap="Blues", cbar_kws={"label": "Number of crashes"}, ax=ax)
    ax.set_title("Crashes by borough and time of day")
    ax.set_xlabel("Time of day")
    ax.set_ylabel("Borough")
    save(fig, "4_borough_time_heatmap.png")


if __name__ == "__main__":
    os.makedirs(FIGURES_DIR, exist_ok=True)
    df = load_from_db()

    print("=== Descriptive statistics ===")
    descriptive_statistics(df)

    print("\n=== Grouped analysis ===")
    by_borough = grouped_analysis(df)

    print("\n=== Visualizations ===")
    plot_crashes_by_hour(df)
    plot_borough_comparison(by_borough)
    plot_top_factors(df)
    plot_heatmap(df)