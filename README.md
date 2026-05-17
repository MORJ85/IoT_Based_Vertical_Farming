
# Canopy Thermal Logger and Greenhouse Data Analysis Pipeline

## Overview

This project is a thermal imaging and environmental sensing pipeline designed for greenhouse and vertical farming applications.

The goal of this system is to monitor plant canopy temperature, microclimate conditions, and derived stress-related indicators in order to support irrigation scheduling, plant stress detection, and future greenhouse climate-control recommendations.

The system uses a FLIR Lepton thermal camera to capture canopy thermal images and an HDC1080 sensor to record air temperature and relative humidity. The collected data are processed to calculate canopy temperature statistics, vapor pressure deficit, canopy-air temperature difference, and a relative evapotranspiration proxy index.

The project is divided into two main parts:

1. Camera Run
2. Data Analysis

---

## Project Goal

The main goal of this project is to develop a sensing and analysis pipeline for:

- Monitoring plant canopy temperature
- Detecting possible water stress and heat stress
- Estimating canopy cooling behavior
- Calculating microclimate indicators such as VPD
- Creating structured datasets for future modeling
- Supporting irrigation and greenhouse climate-control decisions

---

## Repository Structure

The recommended project structure is:

```text
canopy-thermal-logger/
├── camera_run.py
├── data_analysis.py
├── README.md
├── requirements.txt
└── .gitignore
```

## File Descriptions

| File | Description |
|------|-------------|
| `camera_run.py` | Runs the thermal camera and environmental sensor, creates canopy mask, saves hourly data and images |
| `data_analysis.py` | Reads the saved CSV data, performs quality control, calculates summaries, creates plots, and generates stress indicators |
| `README.md` | Project documentation |
| `requirements.txt` | Python dependencies |
| `.gitignore` | Prevents large data files and outputs from being uploaded to GitHub |

### 1. Camera Run

The file 'camera_run.py' is responsible for collecting raw data from the hardware sensors.

**Main Tasks**

The camera run script performs the following steps:

1. Initializes the FLIR Lepton thermal camera
2. Initializes the HDC1080 temperature and humidity sensor
3. Captures thermal frames during a startup warmup period
4. Builds a canopy mask from the thermal image
5. Captures thermal images at a fixed time interval
6. Calculates canopy temperature features
7. Reads air temperature and relative humidity
8. Calculates VPD, CTD, canopy cooling, and ET proxy index
9. Saves raw thermal images as TIFF files
10. Saves thermal PNG images
11. Saves canopy mask and canopy overlay images
12. Saves all numerical values into a CSV file


**Hardware Used**

The current implementation uses:

- Raspberry Pi or Linux-based system
- FLIR Lepton thermal camera
- PureThermal Mini or compatible FLIR interface
- HDC1080 temperature and humidity sensor
- Optional OLED display in earlier versions

The current simplified code focuses on:
- FLIR thermal imaging
- HDC1080 air temperature and humidity sensing

**Data Collection Workflow**
```text
The camera run workflow is: 
Start program
↓
Initialize FLIR camera
↓
Initialize HDC1080 sensor
↓
Collect thermal frames during warmup
↓
Create canopy mask
↓
Start hourly logging loop
↓
Capture thermal image
↓
Read air temperature and humidity
↓
Calculate canopy and environmental features
↓
Save CSV row
↓
Save TIFF and PNG images
↓
Repeat every hour
```

**Canopy Mask Creation**

At the beginning of the experiment, the script collects thermal frames for a short warmup period.

The default settings are:

```python
MASK_WARMUP_SEC = 120
MIN_WARMUP_FRAMES = 30
```

During this period, the system captures multiple thermal frames and calculates an average thermal image.

The canopy mask is generated using thermal segmentation. The current method uses an Otsu-style thresholding approach to separate the plant canopy from the background.

The algorithm tests two possible regions:

- Cooler-than-threshold region
- Warmer-than-threshold region

Then it selects the region that is more likely to correspond to the plant canopy based on:

- Area percentage
- Border contact
- Largest connected component

The final canopy mask is used for all later canopy temperature calculations.

**Saved Image Outputs**

For each hourly record, the script saves:


**1. Raw Thermal TIFF**

This file contains the raw radiometric thermal frame.

Example:

'raw_tiff/thermal_raw_YYYYMMDD_HHMMSS.tiff'

**2. Thermal PNG**

This is a colorized thermal image for visual inspection.

Example:

"png/thermal_color_YYYYMMDD_HHMMSS.png"

**3. Canopy Overlay PNG**

This image shows the detected canopy region overlaid on the thermal image.

Example:
'png/thermal_canopy_overlay_YYYYMMDD_HHMMSS.png'

**4. Canopy Mask PNG**

This image shows the binary canopy mask.

Example:
'png/canopy_mask_YYYYMMDD_HHMMSS.png'


**Output Folder Structure**

Each time the program runs, it creates a new run folder:

'plant_thermal_hourly/run_YYYY-MM-DD_HH-MM-SS/'

Inside each run folder:

```text
plant_thermal_hourly/
└── run_YYYY-MM-DD_HH-MM-SS/
    ├── hourly_canopy_data_YYYY-MM-DD_HH-MM-SS.csv
    ├── raw_tiff/
    │   └── thermal_raw_YYYYMMDD_HHMMSS.tiff
    ├── png/
    │   ├── thermal_color_YYYYMMDD_HHMMSS.png
    │   ├── thermal_canopy_overlay_YYYYMMDD_HHMMSS.png
    │   └── canopy_mask_YYYYMMDD_HHMMSS.png
    ├── mask/
    │   ├── startup_mean_thermal_YYYYMMDD_HHMMSS.png
    │   ├── startup_canopy_mask_YYYYMMDD_HHMMSS.png
    │   └── startup_canopy_overlay_YYYYMMDD_HHMMSS.png
    └── logs/
        └── logger.log
```

**CSV Output**
The main CSV file contains hourly records.

Example file:
hourly_canopy_data_YYYY-MM-DD_HH-MM-SS.csv   

 **CSV Columns**

The CSV contains the following columns:

| Column | Description |
|--------|-------------|
| `Elapsed Time (s)` | Time since the start of the main logging loop |
| `Timestamp` | Date and time of the saved record |
| `Canopy Avg Temp (C)` | Average canopy temperature |
| `Canopy Min Temp (C)` | Minimum temperature within the canopy mask |
| `Canopy Max Temp (C)` | Maximum temperature within the canopy mask |
| `Canopy Std Temp (C)` | Standard deviation of canopy temperature |
| `Canopy Pixel Count` | Number of pixels included in the canopy mask |
| `Canopy Cover (%)` | Percentage of thermal frame covered by canopy |
| `Full Frame Avg Temp (C)` | Average temperature of the full thermal image |
| `Full Frame Min Temp (C)` | Minimum full-frame temperature |
| `Full Frame Max Temp (C)` | Maximum full-frame temperature |
| `Air Temp (C)` | Air temperature from HDC1080 |
| `Relative Humidity (%)` | Relative humidity from HDC1080 |
| `VPD (kPa)` | Vapor Pressure Deficit |
| `CTD Canopy-Air (C)` | Canopy temperature minus air temperature |
| `Canopy Cooling Air-Canopy (C)` | Air temperature minus canopy temperature |
| `ET Index Relative` | Relative evapotranspiration proxy index |
| `Mask Status` | Whether canopy mask creation was successful |
| `Mask Threshold (C)` | Thermal threshold used for segmentation |
| `Mask Selected Side` | Selected thermal region: cooler or warmer |
| `Mask Area (%)` | Area of detected canopy mask |
| `QC FLIR Valid` | Thermal camera quality-control flag |
| `QC HDC Valid` | HDC1080 sensor quality-control flag |
| `Raw Thermal TIFF Path` | Path to saved raw TIFF image |
| `Thermal PNG Path` | Path to saved thermal PNG image |
| `Canopy Overlay PNG Path` | Path to saved canopy overlay image |
| `Canopy Mask PNG Path` | Path to saved canopy mask image |
| `Color Vmin (C)` | Minimum temperature used for PNG color scaling |
| `Color Vmax (C)` | Maximum temperature used for PNG color scaling |

### 2. Data Analysis

The file 'data_analysis.py' is used after data collection.

It reads the saved CSV file, performs quality control, calculates summary statistics, creates plots, and adds simple stress indicators.

**Main Tasks**

The analysis script performs the following steps:

1. Finds the latest run folder
2. Finds the corresponding hourly CSV file
3. Loads the CSV data
4. Converts timestamp and numeric columns
5. Applies quality control
6. Removes invalid records
7. Calculates summary statistics
8. Calculates daily summaries
9. Adds stress-risk flags
10. Saves cleaned data
11. Saves summary tables
12. Creates plots

**Analysis Output Folder**

The analysis results are saved inside the latest run folder:
plant_thermal_hourly/run_YYYY-MM-DD_HH-MM-SS/analysis_outputs/

The output files include:

analysis_outputs/
├── clean_analyzed_data.csv
├── summary.csv
├── daily_summary.csv
├── canopy_temperature.png
├── air_temperature.png
├── relative_humidity.png
├── vpd.png
├── ctd.png
├── et_index.png
└── canopy_cover.png

**Cleaned Data**

The file clean_analyzed_data.csv contains quality-controlled records.

Invalid FLIR or HDC1080 records are removed using the QC columns:

```python
QC FLIR Valid
QC HDC Valid
```

Records with missing timestamp, canopy temperature, air temperature, relative humidity, or VPD are also removed.

**Summary File**

The file summary.csv contains overall summary statistics such as:

- Number of records
- Start time
- End time
- Mean canopy temperature
- Minimum canopy temperature
- Maximum canopy temperature
- Mean air temperature
- Mean relative humidity
- Mean VPD
- Maximum VPD
- Mean CTD
- Maximum CTD
- Mean ET proxy index
- Maximum ET proxy index
- Mean canopy cover

**Daily Summary**

The file daily_summary.csv summarizes data by day.

It includes daily statistics for:
- Canopy temperature
- Air temperature
- Relative humidity
- VPD
- CTD
- ET proxy index
- Canopy cover

This is useful for comparing plant response across days.

**Thermal and Environmental Indicators**
**1. Vapor Pressure Deficit**

Vapor Pressure Deficit, or VPD, is calculated from air temperature and relative humidity.

The formula is:

```python
es = 0.6108 * exp((17.27 * Tair) / (Tair + 237.3))
ea = es * RH / 100
VPD = es - ea
```
Where:

- Tair is air temperature in degrees Celsius
- RH is relative humidity in percent
- es is saturation vapor pressure
- ea is actual vapor pressure
- VPD is vapor pressure deficit in kPa

VPD is important because it describes the atmospheric demand for water vapor. High VPD means the air is dry and the plant may lose water faster through transpiration.    

** 2. Canopy Temperature Difference**

Canopy Temperature Difference is calculated as:

````md
```python
CTD = Canopy Temperature - Air Temperature
```

Interpretation:
- Positive CTD means the canopy is warmer than the air
- Negative CTD means the canopy is cooler than the air
- A warmer canopy may indicate reduced transpiration or plant stress
- A cooler canopy may indicate active transpiration and evaporative cooling

**3. Canopy Cooling**

Canopy cooling is calculated as:

````md
```python
Canopy Cooling = Air Temperature - Canopy Temperature
```

Interpretation:
- Higher positive cooling means the canopy is cooler than the surrounding air
- This can indicate stronger transpiration
- Low or negative cooling may indicate heat stress or limited water availability   

**4. Relative ET Proxy Index**

The current implementation calculates a relative evapotranspiration proxy index:
````md
```python
ET Index = max(0, Canopy Cooling) * VPD
```
This value is not actual evapotranspiration in physical units such as mm/h.

It is a relative indicator based on:
- How much cooler the canopy is compared to the air
- How strong the atmospheric drying demand is

A higher value may indicate stronger evaporative cooling and transpiration activity, but it should not be interpreted as actual ET without further calibration.       

**Stress Indicators**
The analysis script adds simple stress-risk flags.

**High VPD Risk**
````md
```python
High VPD Risk = 1 if VPD >= 2.0 kPa
```
High VPD may indicate dry atmospheric conditions and increased plant water demand.

**Heat Stress Risk**
````md
```python
Heat Stress Risk = 1 if Canopy Avg Temp >= 35.0 C
```

This threshold can be adjusted depending on crop type and experimental conditions.

**Low Cooling Risk**
````md
```python
Low Cooling Risk = 1 if Canopy Cooling <= 0.0 C
```

If the canopy is not cooler than the air, this may indicate reduced transpiration or possible plant stress.

**Overall Stress Flag**

````md
```python
Overall Stress Flag = 1 if any stress flag is active

This is a simple indicator for quick screening. It should be validated with crop-specific observations and experimental data.


## Installation
Python Packages

Install the required packages:
```bash
pip install numpy pandas matplotlib pillow tifffile flirpy luma.oled adafruit-blinka adafruit-circuitpython-busdevice    
```

## System Packages

For FLIR/PureThermal support, the following Linux packages may be required:
```bash
sudo apt update
sudo apt install v4l-utils uvcdynctrl    
```

## Running the Project
**Step 1: Run the Camera Logger**

To start collecting data:

```bash
!python3 camera_run.py
```
The program will:

1. Build the canopy mask
2. Start hourly logging
3. Save CSV records
4. Save thermal images 

**Step 2: Run Data Analysis**

After collecting data, run:

```bash
python3 data_analysis.py
```
The script will automatically find the latest run folder and analyze the CSV file.    


## Running from Jupyter Notebook

If you are using Jupyter Notebook, you can run the scripts using:

```python
!python3 camera_run.py
```

and after data collection:

```python
!python3 data_analysis.py
```

To create the files from a notebook, use:

```python
%%writefile camera_run.py
# paste camera_run.py code here
```
and:

```python
%%writefile data_analysis.py
# paste data_analysis.py code here
```

## Important Settings
Inside camera_run.py, the most important settings are:
```python
SAVE_EVERY_SEC = 3600
MASK_WARMUP_SEC = 120
MIN_WARMUP_FRAMES = 30
```

**For Testing**

For quick testing, use shorter intervals:

```python
SAVE_EVERY_SEC = 60
MASK_WARMUP_SEC = 30
```

**For Final Experiment**

For hourly data collection:
```python
SAVE_EVERY_SEC = 3600
MASK_WARMUP_SEC = 120
```

## GitHub Notes

Large output files should not be uploaded to GitHub.
A .gitignore file exists to exclude generated data.
This keeps the repository clean and prevents large image or data files from being uploaded.


## Future Development
Possible future improvements include:

- More robust canopy segmentation
- Dynamic canopy mask updating during long experiments
- CWSI calculation
- Integration of PAR or solar radiation sensor
- Integration of airflow sensor
- Integration of CO2 sensor
- Actual evapotranspiration estimation
- Penman-Monteith-based transpiration modeling
- Crop-specific stress thresholds
- Irrigation scheduling recommendations
- Greenhouse climate-control recommendations
- Real-time dashboard      
- Automated stress alerts


## Scientific Notes

The current system provides relative thermal and environmental indicators related to plant transpiration and stress.

The current ET proxy index is not actual evapotranspiration. Actual ET estimation would require additional variables such as:

- Radiation or PAR
- Wind speed or airflow
- Canopy conductance
- Leaf area index
- Crop parameters
- Calibration data such as lysimeter measurements

Therefore, the current implementation is best described as a canopy thermal monitoring and stress-indicator system.

## Ownership and Development

This project was developed for **UrbanGreenTech**, a company founded by **Reza Jarkeh** in **The Netherlands**

The code is part of UrbanGreenTech's greenhouse and vertical farming technology development, focusing on canopy thermal monitoring, microclimate sensing, and data-driven decision support for sustainable controlled-environment agriculture.

## License

All rights reserved.

This code is owned by **UrbanGreenTech**. It may not be used, copied, modified, distributed, or published without written permission from UrbanGreenTech or Reza Jarkeh.    
