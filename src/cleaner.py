import os
import numpy as np
import pandas as pd

VALIDATED_PATH = "data/validated_data.csv"
CLEANED_PATH = "data/cleaned_data.csv"
BOROUGH_SUMMARY_PATH = "data/borough_summary.csv"
PIVOT_PATH = "data/borough_time_of_day_pivot.csv"

MISSING_DROP_THRESHOLD = 0.7   # колонки, где пропусков больше 70%, удаляем


def load_data(path):
    # zip_code читаем как текст, иначе pandas превратит 11201 в 11201.0
    return pd.read_csv(path, dtype={"zip_code": str})


def report_missing(df, title):
    missing = df.isna().sum()
    missing = missing[missing > 0].sort_values(ascending=False)
    print(f"\n{title}: {int(missing.sum())} missing cells")
    if not missing.empty:
        print((missing.to_frame("missing")
               .assign(percent=(missing / len(df) * 100).round(1))).to_string())


def remove_duplicates(df):
    before = len(df)
    df = df.drop_duplicates()                                   # полностью одинаковые строки
    df = df.drop_duplicates(subset="collision_id", keep="first")  # одна авария = одна запись
    print(f"\nDuplicates removed: {before - len(df)} (rows: {before} -> {len(df)})")
    return df


def normalize_text(series, case="title"):
    """Убирает лишние пробелы и приводит текст к одному регистру."""
    s = series.str.strip().str.replace(r"\s+", " ", regex=True)
    return s.str.title() if case == "title" else s.str.upper()


def handle_missing_and_types(df):
    df = df.drop(columns=["location"], errors="ignore")   # вложенный словарь, дублирует latitude/longitude

    count_cols = [c for c in df.columns if c.startswith("number_of_")]
    vehicle_cols = [c for c in df.columns if c.startswith("vehicle_type_code")]
    factor_cols = [c for c in df.columns if c.startswith("contributing_factor_vehicle")]
    street_cols = [c for c in df.columns if c.endswith("street_name")]

    # NumPy: число машин в аварии = сколько колонок vehicle_type заполнено (считаем ДО удаления пустых колонок)
    df["num_vehicles"] = np.sum(df[vehicle_cols].notna().to_numpy(), axis=1)

    # Колонки, почти полностью пустые (vehicle 3-5, factor 3-5, off_street и т.п.), удаляем
    missing_share = df.isna().mean()
    to_drop = missing_share[missing_share > MISSING_DROP_THRESHOLD].index.tolist()
    df = df.drop(columns=to_drop)
    print(f"\nColumns dropped (> {int(MISSING_DROP_THRESHOLD * 100)}% missing): {to_drop}")

    # Пропуски в оставшихся колонках
    count_cols = [c for c in count_cols if c in df.columns]
    df[count_cols] = df[count_cols].fillna(0).astype(int)        # нет данных о пострадавших -> 0
    df["borough"] = df["borough"].fillna("Unknown")
    df["zip_code"] = df["zip_code"].fillna("Unknown")
    for col in [c for c in factor_cols if c in df.columns]:
        df[col] = df[col].fillna("Unspecified")
    for col in [c for c in vehicle_cols if c in df.columns]:
        df[col] = df[col].fillna("Unknown")
    for col in [c for c in street_cols if c in df.columns]:
        df[col] = df[col].fillna("Unknown")
    # latitude/longitude оставляем NaN: координаты нельзя выдумать

    # Нормализация текста
    df["borough"] = normalize_text(df["borough"])
    for col in [c for c in factor_cols + vehicle_cols if c in df.columns]:
        df[col] = normalize_text(df[col])
    for col in [c for c in street_cols if c in df.columns]:
        df[col] = normalize_text(df[col], case="upper")

    # Типы данных
    df["crash_date"] = pd.to_datetime(df["crash_date"])
    df["crash_time"] = df["crash_time"].str.zfill(5)             # "9:05" -> "09:05"
    df["crash_datetime"] = pd.to_datetime(
        df["crash_date"].dt.strftime("%Y-%m-%d") + " " + df["crash_time"], format="%Y-%m-%d %H:%M"
    )
    df["latitude"] = df["latitude"].astype(float)
    df["longitude"] = df["longitude"].astype(float)
    df["borough"] = df["borough"].astype("category")
    return df


def add_features(df):
    """Новые признаки с помощью NumPy."""
    df["hour"] = df["crash_datetime"].dt.hour
    df["day_of_week"] = df["crash_datetime"].dt.day_name()
    df["is_weekend"] = np.isin(df["crash_datetime"].dt.dayofweek, [5, 6])
    df["total_casualties"] = np.add(df["number_of_persons_injured"], df["number_of_persons_killed"])
    df["severity"] = np.select(
        [df["number_of_persons_killed"] > 0, df["number_of_persons_injured"] > 0],
        ["Fatal", "Injury"],
        default="Property damage only",
    )
    df["time_of_day"] = np.select(
        [df["hour"] < 6, df["hour"] < 12, df["hour"] < 18],
        ["Night", "Morning", "Afternoon"],
        default="Evening",
    )
    return df


def filtering_example(df):
    """Фильтрация по нескольким условиям: аварии с пострадавшими ночью, в выходные."""
    subset = df[
        (df["number_of_persons_injured"] > 0)
        & (df["time_of_day"] == "Night")
        & (df["is_weekend"])
    ]
    print(f"\nFilter (injuries AND night AND weekend): {len(subset)} crashes")
    return subset


def borough_summary(df):
    summary = (
        df.groupby("borough", observed=True)
        .agg(
            crashes=("collision_id", "count"),
            total_injured=("number_of_persons_injured", "sum"),
            avg_injured=("number_of_persons_injured", "mean"),
            total_killed=("number_of_persons_killed", "sum"),
            avg_vehicles=("num_vehicles", "mean"),
        )
        .round(2)
        .sort_values("crashes", ascending=False)
    )
    print("\nGroupBy borough:")
    print(summary.to_string())
    return summary


def reshape_example(df):
    """pivot_table: районы x время суток; melt: обратно в длинный формат."""
    order = ["Night", "Morning", "Afternoon", "Evening"]
    pivot = df.pivot_table(
        index="borough", columns="time_of_day", values="collision_id",
        aggfunc="count", fill_value=0, observed=True,
    ).reindex(columns=order, fill_value=0)
    print("\nPivot table (crashes by borough and time of day):")
    print(pivot.to_string())

    long = pivot.reset_index().melt(id_vars="borough", var_name="time_of_day", value_name="crashes")
    print(f"Melt back to long format: {pivot.shape} wide -> {long.shape} long")
    return pivot, long


if __name__ == "__main__":
    df = load_data(VALIDATED_PATH)
    print(f"Loaded validated records: {len(df)} rows, {df.shape[1]} columns")

    report_missing(df, "Missing values BEFORE cleaning")
    df = remove_duplicates(df)
    df = handle_missing_and_types(df)
    df = add_features(df)
    report_missing(df, "Missing values AFTER cleaning")

    filtering_example(df)
    summary = borough_summary(df)
    pivot, _ = reshape_example(df)

    print("\nFinal data types:")
    print(df.dtypes.to_string())

    os.makedirs("data", exist_ok=True)
    df.to_csv(CLEANED_PATH, index=False)
    summary.to_csv(BOROUGH_SUMMARY_PATH)
    pivot.to_csv(PIVOT_PATH)
    print(f"\nCleaned records: {len(df)} -> saved to {CLEANED_PATH}")