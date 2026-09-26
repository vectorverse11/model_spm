# Virtual Beam Stiffness Testing SPM

A software-only simulator for cantilever beam stiffness testing.
Mirrors COP's philosophy: user inputs → calculation engine → curves & report.

## Features
- Beam bending flexibility
- Upright (column) flexibility
- Semi-rigid connection rotation
- Hook axial compliance
- 10% preload (Eurocode practice)
- Optional seating non-linearity
- Live Streamlit GUI

## Install
```bash
pip install -r requirements.txt
```

## Run
```bash
streamlit run app.py
```

Open http://localhost:8501