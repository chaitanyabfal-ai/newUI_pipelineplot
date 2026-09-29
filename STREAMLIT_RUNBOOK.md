# Gas MOC Smart Optimizer - Streamlit Runbook

## 📖 Overview

**Version 5.0 - Streamlit Edition**

The **Gas MOC Smart Optimizer** is now available as a modern web application built with Streamlit. This replaces the original tkinter GUI while maintaining all functionality. The Streamlit version provides:

- ✅ Browser-based interface (no local GUI dependencies)
- ✅ Same core simulation engine and optimization logic
- ✅ Improved visualization and interactivity
- ✅ Easier deployment and sharing
- ✅ Better integration with web-based workflows

---

## 🚀 Quick Start

### Prerequisites

- **Python 3.8 or higher** (Python 3.10+ recommended)
- **pip** (Python package manager)
- Modern web browser (Chrome, Firefox, Edge, Safari)

### Installation

#### 1. Clone or download the project

```bash
# If using git
git clone <repository-url>
cd Gas-MOC-Smart-Optimizer

# Or navigate to your existing project directory
cd /path/to/Gas-MOC-Smart-Optimizer
```

#### 2. Create and activate virtual environment

**Windows:**
```bash
python -m venv venv
venv\Scripts\activate
```

**macOS/Linux:**
```bash
python3 -m venv venv
source venv/bin/activate
```

#### 3. Install dependencies

```bash
pip install -r requirements.txt
```

The `requirements.txt` includes:
- streamlit
- numpy
- pandas
- matplotlib
- scipy

#### 4. Run the application

```bash
streamlit run app.py
```

Your default browser will automatically open to `http://localhost:8501`

---

## 📦 Project Structure

```
Gas-MOC-Smart-Optimizer/
├── app.py              # Streamlit web application
├── core.py             # Core simulation & optimization engine
├── requirements.txt    # Python dependencies
├── RUNBOOK.md          # Original tkinter runbook (WSL)
├── STREAMLIT_RUNBOOK.md  # This file - Streamlit user guide
└── PROJECT_EXPLANATION.md  # Technical documentation
```

---

## 🎯 Using the Streamlit Application

### Application Layout

The application has three main areas:

1. **Sidebar** (Left)
   - Data loading (PT data, elevation profile)
   - Quick actions (load examples, save config)
   - System information
   - About section

2. **Main Content Area** (Center)
   - Configuration tab
   - Results tab
   - Convergence tab
   - Diameter Profile tab
   - Pressure Match tab
   - Error Analysis tab

3. **Log Panel** (Bottom)
   - Expandable log showing all application messages
   - Useful for debugging and tracking operations

### Step-by-Step Workflow

#### Step 1: Load PT Data

1. In the sidebar, use **"Upload PT CSV"**
2. Select your CSV file with columns: `time`, `pressure_bar`
3. Or click **"Load Example PT Data"** for synthetic data

✅ **Verification:** PT data info appears in sidebar, warning disappears

#### Step 2: (Optional) Load Elevation Profile

1. In the sidebar, use **"Upload Elevation CSV"**
2. Select your CSV file with columns: `distance_m`, `elevation_m`
3. Or click **"Load Example Elevation"** for synthetic elevation

✅ **Verification:** Elevation info appears in sidebar

#### Step 3: Configure Simulation

Navigate to the **Configuration** tab and expand each section:

##### 📏 Pipeline Geometry
- Set pipe length, grid spacing
- Configure nominal diameter and roughness
- Set PT and valve locations
- Verify segment count (should be > 0)

##### 🎈 Gas Properties
- Set temperature, gas constant, viscosity
- Configure compressibility and heat ratio

##### 🔧 Valve Parameters
- Set ISA/IEC coefficients (xT, Fp, Cv_max)
- Configure K_multiplier

##### ⏱️ Valve Timing
- Set open start, opening ramp, hold open, closing ramp
- Verify total time covers entire valve cycle
- Check timeline preview

##### 📊 Pressures
- Set upstream and downstream pressures
- Select upstream boundary condition

##### ⚙️ MOC Numerical Parameters
- Set Courant β (0.01-1.0, default 0.9)
- Set B_factor (0.98-1.02, default 1.0)

##### 📐 Initial Diameter Profile
- Select profile type (uniform or probable)
- For probable: configure multipliers and locations

##### 🎯 Optimization Settings
- Set D multiplier range
- Configure max iterations and population size
- Set regularization weights
- Select optimization method
- **Recommended:** Use workers=1 for Streamlit

#### Step 4: Run Simulation

1. Click **"▶️ Run Simulation"** button
2. Wait for completion (spinner appears)
3. Check application log for progress

✅ **Verification:** Success message with RMSE, results appear in tabs

#### Step 5: Run Optimization (Optional)

1. Review simulation results first
2. Adjust optimization settings if needed
3. Click **"🔍 Start Optimization"** button
4. Monitor progress in status bar and log
5. Wait for completion (can take minutes to hours)

✅ **Verification:** Success message, optimized results in all tabs

#### Step 6: Export Results

In the **Results** tab:
- **Export Results CSV:** PT data, model output, errors
- **Export Diameters CSV:** Segment diameters and changes
- **Save Configuration:** Current parameter settings

---

## 📊 Configuration Parameters Reference

### Pipeline Geometry

| Parameter | Description | Default | Units |
|-----------|-------------|---------|-------|
| L | Pipe length | 8000.0 | m |
| dx | Grid spacing | 200.0 | m |
| D_nom | Nominal diameter | 0.1937 | m |
| eps_mm | Pipe roughness | 0.045 | mm |
| x_pt_m | PT sensor location | 7600.0 | m |
| valve_pos_m | Valve location | 8000.0 | m |
| g | Gravity | 9.81 | m/s² |

### Gas Properties

| Parameter | Description | Default | Units |
|-----------|-------------|---------|-------|
| T_celsius | Gas temperature | 25.0 | °C |
| R_gas | Specific gas constant | 424.0 | J/kg·K |
| mu_dyn | Dynamic viscosity | 1.1e-5 | Pa·s |
| Z_factor | Compressibility | 0.996 | - |
| gamma | Heat ratio | 1.26 | - |

### Valve Parameters (ISA/IEC)

| Parameter | Description | Default | Units |
|-----------|-------------|---------|-------|
| xT | Terminal pressure-drop ratio | 0.9 | - |
| Fp | Piping geometry factor | 1.0 | - |
| Cv_max | Rated flow coefficient | 500.0 | - |
| K_multiplier | Valve resistance multiplier | 5.0 | - |

### Valve Timing (4-Phase Cycle)

| Parameter | Description | Default | Units |
|-----------|-------------|---------|-------|
| t_valve_open_start | Time valve starts opening | 30.0 | s |
| t_valve_opening | Opening ramp duration | 5.0 | s |
| t_valve_hold_open | Hold fully open duration | 60.0 | s |
| t_valve_closing | Closing ramp duration | 5.0 | s |
| T_total | Total simulation time | 200.0 | s |

**Important:** T_total must be > t_valve_open_start + t_valve_opening + t_valve_hold_open + t_valve_closing

### Pressures

| Parameter | Description | Default | Units |
|-----------|-------------|---------|-------|
| P_upstream_bar | Upstream pressure | 8.098 | bar |
| P_atm_bar | Downstream/atmospheric pressure | 1.0 | bar |
| upstream_bc | Upstream boundary condition | CLOSED_END | - |
| V_tank | Tank volume (FINITE_TANK only) | 10.0 | m³ |

**Boundary Conditions:**
- `CONSTANT_P`: Constant upstream pressure
- `CLOSED_END`: No flow at upstream (closed pipe)
- `FINITE_TANK`: Upstream connected to finite volume tank

### MOC Numerical Parameters

| Parameter | Description | Range | Default |
|-----------|-------------|-------|---------|
| beta | Courant number | 0.01-1.0 | 0.9 |
| B_factor | Wave speed scaling | 0.98-1.02 | 1.0 |

**Notes:**
- β=1.0: Exact CFL condition (most accurate, least stable)
- β<1.0: Sub-Courant (more diffusive, more stable)
- B_factor: ±2% wave speed tuning

### Initial Diameter Profile

| Parameter | Description | Default | Units |
|-----------|-------------|---------|-------|
| profile_type | Profile type | uniform | - |
| prob_D_init | Baseline multiplier | 0.95 | - |
| prob_D_mult | Reduced multiplier | 0.75 | - |
| prob_L_ds | Location from downstream | 200.0 | m |
| prob_seg_len | Reduced segment length | 1000.0 | m |

**Profile Types:**
- `uniform`: All segments have nominal diameter (D_nom)
- `probable`: Baseline diameter (D_nom × prob_D_init) with reduced region (D_nom × prob_D_mult)

### Optimization Settings

| Parameter | Description | Default | Units |
|-----------|-------------|---------|-------|
| D_range_min | Minimum diameter multiplier | 0.70 | - |
| D_range_max | Maximum diameter multiplier | 1.05 | - |
| max_iter | Maximum DE iterations | 150 | - |
| popsize | Population size | 15 | - |
| lambda_smooth | Smoothness regularization | 1e-6 | - |
| lambda_tv | Total variation regularization | 1e-7 | - |
| workers | Parallel workers | 1 | - |
| method | Optimization method | differential_evolution | - |

**Optimization Methods:**
- `differential_evolution`: Global optimization (DE)
- `de_then_lbfgsb`: DE + L-BFGS-B local refinement (recommended)
- `lbfgsb`: Local gradient-based optimization only

**Regularization:**
- λ_smooth: Penalizes large diameter variations between adjacent segments
- λ_tv: Penalizes total deviation from initial profile
- Higher values = smoother results but potentially worse fit
- Lower values = better fit but potentially jagged profile

---

## 🎨 Tab Descriptions

### 🎛️ Configuration
All simulation and optimization parameters organized in expandable sections.

**Features:**
- Organized by parameter category
- Real-time validation and feedback
- Valve timeline preview
- Action buttons for running simulations/optimizations
- Status display

### 📊 Results
Summary of simulation and optimization results.

**Features:**
- Metrics: RMSE, MAE, evaluations
- Diameter statistics: mean, min, max, std dev
- Export options for results
- Comparison between initial and optimized

### 📈 Convergence
Visualization of optimization progress.

**Features:**
- RMSE vs evaluation number (log scale)
- Best-so-far tracking
- Diameter mean ± std dev vs evaluation
- Nominal diameter reference line
- Summary statistics

### 📏 Diameter Profile
Visualization of pipe diameter along the length.

**Features:**
- Optimized or initial diameter profile
- Overlay of initial profile (if different)
- Nominal diameter reference line
- Valve and PT position markers
- Elevation profile (if loaded)
- Visual comparison of changes

### 🎯 Pressure Match
Comparison of model output with PT data.

**Features:**
- PT data points (scatter)
- Initial simulation curve (dashed)
- Optimized simulation curve (solid)
- Full time history visualization
- Error metrics

### 📊 Error Analysis
Detailed error analysis between model and PT data.

**Features:**
- Error vs time plot
- Error distribution histogram
- Initial vs optimized comparison
- Mean error indicator
- Statistical analysis

---

## ⚠️ Important Considerations

### Performance

1. **Simulation Caching:**
   - Streamlit caches `run_gas_moc` results
   - Same parameters = instant results
   - Different parameters = re-computation
   - Cache cleared on app restart

2. **Optimization Duration:**
   - Depends on: n_segments, max_iter, popsize, T_total
   - Typical runs: minutes to hours
   - Progress bar shows current evaluation
   - Can stop at any time

3. **Multiprocessing:**
   - **Always use workers=1 in Streamlit**
   - workers > 1 may cause issues in web context
   - App will warn you if you select workers > 1
   - For true parallel processing, consider command-line usage

### Data Quality

1. **PT Data:**
   - Must have `time` and `pressure_bar` columns
   - Time should be in seconds
   - Pressure in bar (absolute)
   - Good time resolution for accurate results

2. **Elevation Profile:**
   - Should cover entire pipeline or region of interest
   - Must start at distance 0 (upstream end)
   - Can be positive (uphill) or negative (downhill)
   - If not provided, flat pipeline assumed

### Validation

Before accepting optimization results:

1. **Check Pressure Match:**
   - Does optimized curve follow PT data?
   - Are there systematic deviations?
   - Does valve timing match actual operation?

2. **Check Diameter Profile:**
   - Is the profile physically reasonable?
   - Are there sudden jumps or unrealistic values?
   - Does it make sense given the pressure data?

3. **Check Error Analysis:**
   - Is error distribution centered around zero?
   - Are there time periods with consistently high errors?
   - Is the optimized error better than initial?

4. **Check Convergence:**
   - Did RMSE improve during optimization?
   - Did it converge to a stable value?
   - Was the final value significantly better than initial?

---

## 🔧 Troubleshooting

### Common Issues and Solutions

#### "PT data not loaded" warning
- **Cause:** No PT data uploaded
- **Solution:** Upload valid PT CSV or use example data

#### "Invalid grid parameters (L / dx)"
- **Cause:** L not divisible by dx, or invalid values
- **Solution:** Ensure L > dx > 0 and L/dx is reasonable

#### Simulation/optimization takes too long
- **Cause:** Too many segments, long simulation time, large population
- **Solutions:**
  - Reduce L or increase dx (fewer segments)
  - Reduce T_total
  - Use smaller popsize
  - Use simpler profile

#### Optimization doesn't improve
- **Causes:**
  - Poor initial parameters
  - Insufficient search space
  - Numerical issues
- **Solutions:**
  - Verify simulation matches PT data before optimizing
  - Widen D_range_min and D_range_max
  - Try different profile type
  - Increase max_iter or popsize
  - Reduce regularization weights

#### Optimization diverges or produces NaN
- **Causes:**
  - Numerical instability
  - Extreme parameter values
  - Valve timing issues
- **Solutions:**
  - Reduce D_range_max (try 1.05 instead of 1.10)
  - Lower beta (try 0.8 instead of 0.9)
  - Adjust B_factor closer to 1.0
  - Use smaller dx (better resolution)
  - Verify T_total > valve cycle duration

#### Workers > 1 causes errors
- **Cause:** Multiprocessing issues in Streamlit
- **Solution:** Always use workers=1

#### File upload doesn't work
- **Causes:**
  - Browser security restrictions
  - File format issues
- **Solutions:**
  - Try a different browser
  - Verify CSV format (comma-separated, correct columns)
  - Use example data to test

#### Plots don't appear
- **Causes:**
  - No results available
  - Browser compatibility
- **Solutions:**
  - Run simulation or optimization first
  - Try refreshing the page
  - Check browser console for errors

---

## 📚 Understanding the Method

### Method of Characteristics (MOC)

The Gas MOC solves the partial differential equations of compressible fluid flow:

1. **Mass Conservation:** ∂(ρA)/∂t + ∂(ρuA)/∂x = 0
2. **Momentum:** ∂u/∂t + u∂u/∂x + (1/ρ)∂p/∂x + g sinθ + (f/2D)u|u| = 0
3. **State Equation:** p = ρZRT (ideal gas)

**Characteristics:**
- C+: dx/dt = +B (forward-traveling wave)
- C-: dx/dt = -B (backward-traveling wave)
- B = sqrt(ZRT) is the wave speed

**Numerical Scheme:**
- Spatial domain: N segments of length dx
- Time step: dt = β·dx/B (Courant condition)
- β ≤ 1 for stability
- Bounds: Upstream (various BC), Downstream (valve)

### Valve Model

4-phase linear valve cycle with ISA/IEC N6 flow model:

```
Mass Flow = N6 * Fp * Cv_eff * Y * sqrt(x * p_up * rho_up)
```

Where:
- Cv_eff = (Cv_max / K_multiplier) * τ
- τ = valve opening fraction (0-1)
- Y = expansion factor
- x = pressure drop ratio

### Optimization

**Differential Evolution (DE):**
- Population-based global optimizer
- Good for non-smooth, multi-modal problems
- Handles bounds naturally
- Warm-start from initial profile

**Cost Function:**
```
Cost = Weighted_RMSE + λ_smooth * Smoothness + λ_tv * Total_Variation
```

**Weighted RMSE:**
- Transient regions weighted 20-25× higher
- Captures important dynamic behavior
- Less sensitive to steady-state noise

---

## 🎓 Tips and Best Practices

### Starting Out

1. **Use Example Data First:**
   - Load example PT data and elevation
   - Run simulation with default parameters
   - Verify it works before using your data

2. **Start Simple:**
   - Use uniform diameter profile
   - Use default parameters
   - Small number of segments (start with dx=200-400m)

3. **Validate Before Optimizing:**
   - Run simulation first
   - Check Pressure Match tab
   - Verify RMSE is reasonable before optimization

### Parameter Tuning

**For Faster Simulations:**
- Increase dx (fewer segments)
- Decrease T_total (shorter simulation)
- Use uniform profile
- Disable elevation if not needed

**For Better Optimization:**
- Use probable profile if you have prior knowledge
- Increase max_iter for complex problems
- Increase popsize for better exploration
- Adjust regularization weights

**For Numerical Stability:**
- Keep β in 0.5-0.9 range
- Keep B_factor in 0.98-1.02 range
- Ensure T_total > valve cycle duration
- Ensure PT location is upstream of valve

### Advanced Usage

**Custom Profiles:**
- Use probable profile to encode prior knowledge
- Set baseline multiplier based on average diameter
- Set reduced multiplier and location based on known features

**Regularization:**
- Increase λ_smooth if profile is too jagged
- Increase λ_tv if optimization strays too far from initial
- Decrease both if optimization is over-constrained

**Multi-stage Optimization:**
1. Run with coarse grid (large dx)
2. Use result as initial profile for fine grid
3. Or use uniform → probable → optimized workflow

---

## 📞 Support and Resources

### Documentation Files

- `RUNBOOK.md`: Original tkinter runbook (WSL-specific)
- `STREAMLIT_RUNBOOK.md`: This file - Streamlit user guide
- `PROJECT_EXPLANATION.md`: Technical documentation

### Getting Help

1. **Check this Runbook** for common issues
2. **Review PROJECT_EXPLANATION.md** for technical details
3. **Check the application log** for error messages
4. **Validate your input data** meets requirements

---

## 📄 License

This software is provided for gas pipeline simulation and optimization purposes.

*Version: 5.0 (Streamlit Edition)*
*Last updated: September 2026*
