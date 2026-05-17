import os
import glob
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt


# ============================================================
# SETTINGS
# ============================================================

ROOT_DIR = "./plant_thermal_hourly"
OUTPUT_DIR_NAME = "analysis_outputs"


# ============================================================
# FIND LATEST RUN
# ============================================================

def find_latest_run(root_dir=ROOT_DIR):
    run_dirs = sorted(glob.glob(os.path.join(root_dir, "run_*")))

    if not run_dirs:
        raise FileNotFoundError("No run folder found.")

    return run_dirs[-1]


def find_csv_file(run_dir):
    csv_files = glob.glob(os.path.join(run_dir, "hourly_canopy_data_*.csv"))

    if not csv_files:
        raise FileNotFoundError("No hourly canopy CSV found.")

    return csv_files[0]


# ============================================================
# LOAD AND CLEAN DATA
# ============================================================

def load_data(csv_path):
    df = pd.read_csv(csv_path)

    df["Timestamp"] = pd.to_datetime(df["Timestamp"], errors="coerce")

    numeric_columns = [
        "Elapsed Time (s)",
        "Canopy Avg Temp (C)",
        "Canopy Min Temp (C)",
        "Canopy Max Temp (C)",
        "Canopy Std Temp (C)",
        "Canopy Pixel Count",
        "Canopy Cover (%)",
        "Full Frame Avg Temp (C)",
        "Full Frame Min Temp (C)",
        "Full Frame Max Temp (C)",
        "Air Temp (C)",
        "Relative Humidity (%)",
        "VPD (kPa)",
        "CTD Canopy-Air (C)",
        "Canopy Cooling Air-Canopy (C)",
        "ET Index Relative",
        "QC FLIR Valid",
        "QC HDC Valid"
    ]

    for col in numeric_columns:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    return df


def quality_control(df):
    clean = df.copy()

    if "QC FLIR Valid" in clean.columns:
        clean = clean[clean["QC FLIR Valid"] == 1]

    if "QC HDC Valid" in clean.columns:
        clean = clean[clean["QC HDC Valid"] == 1]

    clean = clean.dropna(subset=[
        "Timestamp",
        "Canopy Avg Temp (C)",
        "Air Temp (C)",
        "Relative Humidity (%)",
        "VPD (kPa)"
    ])

    return clean


# ============================================================
# SUMMARY TABLES
# ============================================================

def create_summary(df):
    summary = {
        "number_of_records": len(df),
        "start_time": df["Timestamp"].min(),
        "end_time": df["Timestamp"].max(),

        "canopy_avg_temp_mean_C": df["Canopy Avg Temp (C)"].mean(),
        "canopy_avg_temp_min_C": df["Canopy Avg Temp (C)"].min(),
        "canopy_avg_temp_max_C": df["Canopy Avg Temp (C)"].max(),

        "air_temp_mean_C": df["Air Temp (C)"].mean(),
        "air_temp_min_C": df["Air Temp (C)"].min(),
        "air_temp_max_C": df["Air Temp (C)"].max(),

        "rh_mean_percent": df["Relative Humidity (%)"].mean(),
        "vpd_mean_kPa": df["VPD (kPa)"].mean(),
        "vpd_max_kPa": df["VPD (kPa)"].max(),

        "ctd_mean_C": df["CTD Canopy-Air (C)"].mean(),
        "ctd_max_C": df["CTD Canopy-Air (C)"].max(),

        "et_index_mean": df["ET Index Relative"].mean(),
        "et_index_max": df["ET Index Relative"].max(),

        "canopy_cover_mean_percent": df["Canopy Cover (%)"].mean()
    }

    return pd.DataFrame([summary])


def create_daily_summary(df):
    temp = df.copy()
    temp["Date"] = temp["Timestamp"].dt.date

    daily = temp.groupby("Date").agg({
        "Canopy Avg Temp (C)": ["mean", "min", "max", "std"],
        "Air Temp (C)": ["mean", "min", "max"],
        "Relative Humidity (%)": ["mean", "min", "max"],
        "VPD (kPa)": ["mean", "max"],
        "CTD Canopy-Air (C)": ["mean", "max"],
        "ET Index Relative": ["mean", "sum", "max"],
        "Canopy Cover (%)": ["mean"]
    })

    daily.columns = ["_".join(col).strip() for col in daily.columns.values]
    daily = daily.reset_index()

    return daily


# ============================================================
# PLOTS
# ============================================================

def save_plot(df, x_col, y_col, title, ylabel, output_path):
    plt.figure(figsize=(10, 5))
    plt.plot(df[x_col], df[y_col], marker="o")
    plt.title(title)
    plt.xlabel("Time")
    plt.ylabel(ylabel)
    plt.xticks(rotation=45)
    plt.tight_layout()
    plt.savefig(output_path, dpi=300)
    plt.close()


def create_plots(df, output_dir):
    save_plot(
        df,
        "Timestamp",
        "Canopy Avg Temp (C)",
        "Canopy Average Temperature",
        "Canopy Temperature (C)",
        os.path.join(output_dir, "canopy_temperature.png")
    )

    save_plot(
        df,
        "Timestamp",
        "Air Temp (C)",
        "Air Temperature",
        "Air Temperature (C)",
        os.path.join(output_dir, "air_temperature.png")
    )

    save_plot(
        df,
        "Timestamp",
        "Relative Humidity (%)",
        "Relative Humidity",
        "Relative Humidity (%)",
        os.path.join(output_dir, "relative_humidity.png")
    )

    save_plot(
        df,
        "Timestamp",
        "VPD (kPa)",
        "Vapor Pressure Deficit",
        "VPD (kPa)",
        os.path.join(output_dir, "vpd.png")
    )

    save_plot(
        df,
        "Timestamp",
        "CTD Canopy-Air (C)",
        "Canopy Temperature Difference",
        "CTD (C)",
        os.path.join(output_dir, "ctd.png")
    )

    save_plot(
        df,
        "Timestamp",
        "ET Index Relative",
        "Relative ET Proxy Index",
        "ET Index",
        os.path.join(output_dir, "et_index.png")
    )

    save_plot(
        df,
        "Timestamp",
        "Canopy Cover (%)",
        "Canopy Cover",
        "Canopy Cover (%)",
        os.path.join(output_dir, "canopy_cover.png")
    )


# ============================================================
# SIMPLE STRESS FLAGS
# ============================================================

def add_stress_flags(df):
    out = df.copy()

    out["High VPD Risk"] = np.where(out["VPD (kPa)"] >= 2.0, 1, 0)
    out["Heat Stress Risk"] = np.where(out["Canopy Avg Temp (C)"] >= 35.0, 1, 0)
    out["Low Cooling Risk"] = np.where(out["Canopy Cooling Air-Canopy (C)"] <= 0.0, 1, 0)

    out["Overall Stress Flag"] = np.where(
        (out["High VPD Risk"] == 1) |
        (out["Heat Stress Risk"] == 1) |
        (out["Low Cooling Risk"] == 1),
        1,
        0
    )

    return out


# ============================================================
# MAIN ANALYSIS
# ============================================================

def main():
    run_dir = find_latest_run()
    csv_path = find_csv_file(run_dir)

    output_dir = os.path.join(run_dir, OUTPUT_DIR_NAME)
    os.makedirs(output_dir, exist_ok=True)

    print("Run directory:", run_dir)
    print("CSV file:", csv_path)

    df_raw = load_data(csv_path)
    df_clean = quality_control(df_raw)
    df_analyzed = add_stress_flags(df_clean)

    summary = create_summary(df_analyzed)
    daily_summary = create_daily_summary(df_analyzed)

    clean_path = os.path.join(output_dir, "clean_analyzed_data.csv")
    summary_path = os.path.join(output_dir, "summary.csv")
    daily_path = os.path.join(output_dir, "daily_summary.csv")

    df_analyzed.to_csv(clean_path, index=False)
    summary.to_csv(summary_path, index=False)
    daily_summary.to_csv(daily_path, index=False)

    create_plots(df_analyzed, output_dir)

    print("Analysis completed.")
    print("Clean data:", clean_path)
    print("Summary:", summary_path)
    print("Daily summary:", daily_path)
    print("Plots saved in:", output_dir)


if __name__ == "__main__":
    main()
