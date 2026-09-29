#!/usr/bin/env python3
"""
Gas MOC Smart Optimizer — Streamlit Web Application
===================================================

Modern web-based interface for the Gas Method of Characteristics (MOC) 
Smart Optimizer for 2-BC-UP pipeline systems.

This replaces the original tkinter GUI with a Streamlit-based web application
that provides the same functionality with a more user-friendly and accessible
interface.

Author: Bharat Flow Analytics
Version: 5.0 (Streamlit Edition)
Date: 2026-09
"""

import streamlit as st
import os
import sys
import datetime
import json
import math
import tempfile

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.figure import Figure

# Import core simulation and optimization logic
from core import (
    run_gas_moc, GasMOCOptimizer,
    build_initial_profile, get_base_params, get_default_config
)


# =============================================================================
#  STREAMLIT APPLICATION
# =============================================================================

def main():
    """Main Streamlit application entry point."""
    
    # Page configuration
    st.set_page_config(
        page_title="Gas MOC Smart Optimizer",
        page_icon="⚙️",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    
    # Custom CSS for better styling
    st.markdown("""
    <style>
    .main > div {max-width: 1600px; margin: 0 auto;}
    .stTabs [data-baseweb="tab-list"] {gap: 8px;}
    .stTabs [data-baseweb="tab"] {height: 40px; padding: 0 20px;}
    .stButton>button {font-weight: bold;}
    div[data-testid="stMetricValue"] {font-size: 24px;}
    </style>
    """, unsafe_allow_html=True)
    
    # Initialize session state
    initialize_session_state()
    
    # Title and description
    st.title("⚙️ Gas MOC Smart Optimizer")
    st.markdown("""
    **Gas Method of Characteristics (MOC) Smart Optimizer for 2-BC-UP Pipeline Systems**
    
    *Optimize per-segment pipe diameters to match downstream pressure-transducer (PT) data*
    
    ---
    """)
    
    # Sidebar
    render_sidebar()
    
    # Check if PT data is loaded
    if st.session_state.t_pt is None:
        st.warning("⚠️ Please load PT data to begin. Use the sidebar to upload your CSV file.")
        st.stop()
    
    # Create tabs
    tabs = st.tabs([
        "🎛️ Configuration", 
        "📊 Results", 
        "📈 Convergence", 
        "📏 Diameter Profile",
        "🎯 Pressure Match",
        "📊 Error Analysis"
    ])
    
    # Render each tab
    with tabs[0]:
        render_configuration_tab()
    with tabs[1]:
        render_results_tab()
    with tabs[2]:
        render_convergence_tab()
    with tabs[3]:
        render_diameter_profile_tab()
    with tabs[4]:
        render_pressure_match_tab()
    with tabs[5]:
        render_error_analysis_tab()
    
    # Log display at bottom
    st.divider()
    with st.expander("📋 Application Log", expanded=False):
        for msg in st.session_state.log_messages[-50:]:
            st.text(msg)


def initialize_session_state():
    """Initialize session state variables."""
    defaults = {
        'pt_data': None, 't_pt': None, 'p_pt': None,
        'elevation_profile': None, 'optimizer': None,
        'result_data': None, 'initial_simulation': None,
        'n_segments': 0, 'D_initial_profile': None,
        'opt_progress': 0, 'opt_status': "Ready",
        'opt_running': False, 'log_messages': [],
    }
    
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value
    
    if 'config' not in st.session_state:
        st.session_state.config = get_default_config()


def log_message(msg):
    """Add a message to the application log."""
    timestamp = datetime.datetime.now().strftime("%H:%M:%S")
    full_msg = f"[{timestamp}] {msg}"
    st.session_state.log_messages.append(full_msg)


def update_segment_count():
    """Update the number of segments based on L and dx."""
    try:
        cfg = st.session_state.config
        L = float(cfg.get('L', 8000.0))
        dx = float(cfg.get('dx', 200.0))
        st.session_state.n_segments = int(round(L / dx))
    except:
        st.session_state.n_segments = 0


# =============================================================================
#  SIDEBAR
# =============================================================================

def render_sidebar():
    """Render the sidebar with data loading and configuration options."""
    with st.sidebar:
        st.header("📁 Data & Configuration")
        
        # File uploaders
        st.subheader("PT Data")
        pt_file = st.file_uploader(
            "Upload PT CSV",
            type=['csv'],
            key='pt_uploader',
            help="CSV with columns: time, pressure_bar"
        )
        if pt_file:
            load_pt_data(pt_file)
        
        st.subheader("Elevation Profile")
        elev_file = st.file_uploader(
            "Upload Elevation CSV",
            type=['csv'],
            key='elev_uploader',
            help="CSV with columns: distance_m, elevation_m"
        )
        if elev_file:
            load_elevation_data(elev_file)
        
        st.divider()
        st.subheader("⚡ Quick Actions")
        
        if st.button("📥 Load Example PT Data"):
            load_example_pt_data()
            st.rerun()
        
        if st.button("📥 Load Example Elevation"):
            load_example_elevation()
            st.rerun()
        
        if st.button("💾 Save Configuration"):
            save_config()
        
        with st.expander("📂 Load Configuration"):
            load_config()
        
        st.divider()
        st.subheader("ℹ️ System Info")
        
        cpu_count = os.cpu_count() or 1
        st.info(f"""
        **CPU Cores:** {cpu_count}  
        **PT Data:** {'✓ Loaded' if st.session_state.t_pt is not None else '✗ Not loaded'}  
        **Elevation:** {'✓ Loaded' if st.session_state.elevation_profile is not None else '✗ Not loaded'}  
        **Segments:** {st.session_state.n_segments}
        """)
        
        st.divider()
        st.markdown("""
        ### 📚 About
        
        **Gas MOC Smart Optimizer v5.0**
        
        A web-based tool for optimizing pipe diameters using the Method of 
        Characteristics (MOC) for gas pipeline systems.
        
        ---
        
        [View Source](#) | [Documentation](#)
        """)


# =============================================================================
#  DATA LOADING FUNCTIONS
# =============================================================================

def load_pt_data(uploaded_file):
    """Load PT data from uploaded CSV file."""
    try:
        df = pd.read_csv(uploaded_file)
        if 'time' not in df.columns or 'pressure_bar' not in df.columns:
            st.error("❌ CSV must have 'time' and 'pressure_bar' columns")
            return
        
        st.session_state.t_pt = df['time'].values
        st.session_state.p_pt = df['pressure_bar'].values
        st.session_state.pt_data = df
        
        log_message(f"✓ Loaded PT data: {len(st.session_state.t_pt)} pts, "
                    f"range {st.session_state.t_pt.min():.1f}–{st.session_state.t_pt.max():.1f} s, "
                    f"pressure {st.session_state.p_pt.min():.3f}–{st.session_state.p_pt.max():.3f} bar")
        
        update_segment_count()
        st.success("✓ PT data loaded successfully!")
        st.rerun()
    except Exception as e:
        st.error(f"❌ Failed to load PT data: {e}")


def load_elevation_data(uploaded_file):
    """Load elevation profile from uploaded CSV file."""
    try:
        df = pd.read_csv(uploaded_file)
        
        # Find distance and elevation columns
        dist_col = None
        elev_col = None
        for c in df.columns:
            cl = c.lower().strip()
            if cl in ('distance_m', 'distance', 'dist', 'x', 'chainage'):
                dist_col = c
            if cl in ('elevation_m', 'elevation', 'elev', 'height', 'z'):
                elev_col = c
        
        if dist_col is None or elev_col is None:
            st.error("❌ CSV must have columns for distance and elevation")
            return
        
        dist = df[dist_col].values.astype(float)
        elev = df[elev_col].values.astype(float)
        
        # Sort by distance
        order = np.argsort(dist)
        dist = dist[order]
        elev = elev[order]
        
        st.session_state.elevation_profile = np.column_stack([dist, elev])
        st.session_state.config['elevation_profile'] = st.session_state.elevation_profile
        
        log_message(f"✓ Loaded elevation: {len(dist)} pts, "
                    f"range {elev.min():.2f}–{elev.max():.2f} m")
        
        st.success("✓ Elevation profile loaded!")
        st.rerun()
    except Exception as e:
        st.error(f"❌ Failed to load elevation data: {e}")


def load_example_pt_data():
    """Load example PT data for demonstration."""
    try:
        # Create synthetic PT data
        t = np.linspace(0, 200, 2000)
        p = np.ones_like(t) * 8.0
        
        # Valve effects
        valve_open_start = 30.0
        valve_open_end = 35.0
        open_mask = (t >= valve_open_start) & (t <= valve_open_end)
        p[open_mask] = 8.0 - 0.5 * (t[open_mask] - valve_open_start) / (valve_open_end - valve_open_start)
        
        hold_mask = (t > valve_open_end) & (t <= 90.0)
        p[hold_mask] = 7.75 - 0.1 * np.random.randn(len(p[hold_mask]))
        
        valve_close_start = 90.0
        valve_close_end = 95.0
        close_mask = (t >= valve_close_start) & (t <= valve_close_end)
        p[close_mask] = 7.75 + 0.5 * (t[close_mask] - valve_close_start) / (valve_close_end - valve_close_start)
        
        wave_mask = (t > valve_close_end) & (t <= 150.0)
        p[wave_mask] = 8.0 + 0.2 * np.sin(2 * np.pi * (t[wave_mask] - valve_close_end) / 20.0)
        
        # Add noise
        p = p + 0.01 * np.random.randn(len(t))
        
        st.session_state.t_pt = t
        st.session_state.p_pt = p
        st.session_state.pt_data = pd.DataFrame({'time': t, 'pressure_bar': p})
        
        log_message(f"✓ Loaded example PT data: {len(t)} pts")
        update_segment_count()
        st.success("✓ Example PT data loaded!")
        st.rerun()
    except Exception as e:
        st.error(f"❌ Failed to create example data: {e}")


def load_example_elevation():
    """Load example elevation profile for demonstration."""
    try:
        dist = np.linspace(0, 8000, 100)
        elev = np.zeros_like(dist)
        hill_start = 3000
        hill_end = 5000
        hill_mask = (dist >= hill_start) & (dist <= hill_end)
        elev[hill_mask] = 50 * np.sin(np.pi * (dist[hill_mask] - hill_start) / (hill_end - hill_start))
        
        st.session_state.elevation_profile = np.column_stack([dist, elev])
        st.session_state.config['elevation_profile'] = st.session_state.elevation_profile
        
        log_message(f"✓ Loaded example elevation: {len(dist)} pts")
        st.success("✓ Example elevation loaded!")
        st.rerun()
    except Exception as e:
        st.error(f"❌ Failed to create example elevation: {e}")


def save_config():
    """Save current configuration to JSON file."""
    try:
        config_str = json.dumps(st.session_state.config, indent=2)
        st.download_button(
            label="💾 Download Configuration",
            data=config_str,
            file_name=f"gas_moc_config_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
            mime="application/json",
        )
        log_message("✓ Configuration export ready")
    except Exception as e:
        st.error(f"❌ Failed to save configuration: {e}")


def load_config():
    """Load configuration from uploaded JSON file."""
    try:
        uploaded = st.file_uploader("Select JSON config", type=['json'], key='config_loader')
        if uploaded:
            cfg = json.loads(uploaded.read())
            st.session_state.config.update(cfg)
            log_message("✓ Configuration loaded")
            st.success("✓ Configuration loaded!")
            st.rerun()
    except Exception as e:
        if "uploaded" not in str(e):
            st.error(f"❌ Failed to load configuration: {e}")


# =============================================================================
#  SIMULATION AND OPTIMIZATION FUNCTIONS
# =============================================================================

def run_simulation():
    """Run the MOC simulation with current configuration."""
    if st.session_state.t_pt is None:
        st.warning("⚠️ Please load PT data first")
        return False
    
    update_segment_count()
    
    if st.session_state.n_segments == 0:
        st.error("❌ Invalid grid parameters (L / dx)")
        return False
    
    try:
        with st.spinner("🔄 Running simulation..."):
            log_message("\n" + "="*50)
            log_message("Running initial simulation...")
            
            if st.session_state.elevation_profile is not None:
                log_message("  Elevation profile: ACTIVE")
            else:
                log_message("  Elevation profile: FLAT")
            
            params = get_base_params(st.session_state.config)
            D_nom = float(st.session_state.config['D_nom'])
            
            D_prof = build_initial_profile(
                D_nom, 
                st.session_state.n_segments,
                st.session_state.config.get('profile_type', 'uniform'),
                L=st.session_state.config.get('L', 8000.0),
                dx=st.session_state.config.get('dx', 200.0),
                D_init=st.session_state.config.get('prob_D_init', 0.95),
                D_mult=st.session_state.config.get('prob_D_mult', 0.75),
                L_ds=st.session_state.config.get('prob_L_ds', 200.0),
                seg_len=st.session_state.config.get('prob_seg_len', 1000.0)
            )
            st.session_state.D_initial_profile = D_prof
            
            log_message(f"  Profile: {st.session_state.config.get('profile_type', 'uniform').upper()}")
            log_message(f"  D mean={D_prof.mean()*1e3:.3f} mm, min={D_prof.min()*1e3:.3f} mm, max={D_prof.max()*1e3:.3f} mm")
            
            params['D'] = D_prof
            
            # Run simulation with caching
            res = run_gas_moc(**params)
            
            # Interpolate and calculate errors
            p_interp = np.interp(st.session_state.t_pt, res['time'], res['P_down_pt'])
            error = p_interp - st.session_state.p_pt
            rmse = np.sqrt(np.mean(error**2))
            mae = np.mean(np.abs(error))
            
            st.session_state.initial_simulation = {
                't_model': res['time'],
                'p_model': res['P_down_pt'],
                'p_interp': p_interp,
                'rmse': rmse,
                'mae': mae,
                'D_array': D_prof,
                'error': error,
                'profile_type': st.session_state.config.get('profile_type', 'uniform'),
                'res': res,
            }
            
            log_message(f"✓ Simulation done — RMSE: {rmse*1000:.3f} mbar, MAE: {mae*1000:.3f} mbar")
            st.session_state.opt_status = f"Initial RMSE: {rmse*1000:.3f} mbar"
            st.success(f"✓ Simulation completed! RMSE: {rmse*1000:.3f} mbar")
            
        return True
    except Exception as e:
        import traceback
        st.error(f"❌ Simulation failed: {e}")
        log_message(f"✗ Error: {e}")
        log_message(traceback.format_exc())
        return False


def run_optimization():
    """Run the diameter optimization."""
    if st.session_state.t_pt is None:
        st.warning("⚠️ Please load PT data first")
        return False
    
    update_segment_count()
    
    if st.session_state.n_segments == 0:
        st.error("❌ Invalid grid parameters (L / dx)")
        return False
    
    try:
        cfg = st.session_state.config
        params = get_base_params(cfg)
        D_nom = float(cfg['D_nom'])
        D_range = (float(cfg['D_range_min']), float(cfg['D_range_max']))
        max_iter = int(cfg['max_iter'])
        popsize = int(cfg['popsize'])
        
        # Get workers - warn if > 1
        workers = int(cfg.get('workers', 1))
        
        D_prof = build_initial_profile(
            D_nom, 
            st.session_state.n_segments,
            cfg.get('profile_type', 'uniform'),
            L=cfg.get('L', 8000.0),
            dx=cfg.get('dx', 200.0),
            D_init=cfg.get('prob_D_init', 0.95),
            D_mult=cfg.get('prob_D_mult', 0.75),
            L_ds=cfg.get('prob_L_ds', 200.0),
            seg_len=cfg.get('prob_seg_len', 1000.0)
        )
        st.session_state.D_initial_profile = D_prof
        
        log_message("\n" + "="*50)
        log_message(f"Starting optimization — {st.session_state.n_segments} segments")
        
        if st.session_state.elevation_profile is not None:
            log_message("  Elevation profile: ACTIVE")
        
        log_message(f"  Search space: D ∈ [{D_range[0]:.3f}×, {D_range[1]:.3f}×] D_nom")
        log_message(f"  Method: {cfg.get('method', 'differential_evolution')}")
        
        # Create optimizer
        st.session_state.optimizer = GasMOCOptimizer(
            st.session_state.t_pt, 
            st.session_state.p_pt, 
            params, 
            D_nom,
            st.session_state.n_segments,
            D_initial_profile=D_prof,
        )
        
        # Set regularization parameters
        try:
            st.session_state.optimizer.lambda_smooth = float(cfg['lambda_smooth'])
            st.session_state.optimizer.lambda_tv = float(cfg['lambda_tv'])
        except:
            pass
        
        # Set up progress tracking
        st.session_state.opt_running = True
        st.session_state.opt_progress = 0
        
        # Create progress bar
        progress_placeholder = st.empty()
        status_placeholder = st.empty()
        
        # Define callback for progress updates
        def progress_callback(data):
            st.session_state.opt_progress = data['eval']
            st.session_state.opt_status = (
                f"Eval {data['eval']}: D={data['D_mean']*1000:.3f}±{data['D_std']*1000:.3f} mm, "
                f"RMSE={data['rmse']:.4f} mbar"
                + (" ✓ BEST" if data.get('improved') else "")
            )
            
            # Update progress bar
            max_evals = max_iter * popsize
            progress = min(data['eval'] / max_evals, 1.0)
            progress_placeholder.progress(progress, text=st.session_state.opt_status)
            status_placeholder.info(st.session_state.opt_status)
        
        st.session_state.optimizer.progress_callback = progress_callback
        
        # Run optimization
        method = cfg.get('method', 'differential_evolution')
        
        with st.spinner("🔄 Running optimization..."):
            try:
                result = st.session_state.optimizer.optimize(
                    method=method,
                    D_range=D_range,
                    max_iter=max_iter,
                    popsize=popsize,
                    workers=workers,
                )
            except Exception as e:
                st.error(f"❌ Optimization failed: {e}")
                log_message(f"✗ Optimization error: {e}")
                st.session_state.opt_running = False
                return False
        
        # Process results
        if result is not None:
            D_opt = st.session_state.optimizer.best_D_array
            params = get_base_params(st.session_state.config)
            params['D'] = D_opt
            
            with st.spinner("🔄 Final simulation with optimized diameters..."):
                res = run_gas_moc(**params)
            
            p_interp = np.interp(st.session_state.t_pt, res['time'], res['P_down_pt'])
            error = p_interp - st.session_state.p_pt
            rmse = np.sqrt(np.mean(error**2))
            mae = np.mean(np.abs(error))
            
            st.session_state.result_data = {
                'base_params': params,
                'D_nom': D_nom,
                'D_opt_array': D_opt,
                't_model': res['time'],
                'p_model': res['P_down_pt'],
                't_pt': st.session_state.t_pt,
                'p_pt': st.session_state.p_pt,
                'p_interp': p_interp,
                'error': error,
                'rmse': rmse,
                'mae': mae,
                'x_segments': res['x_segments'],
                'elevation_arr': res['elevation_arr'],
                'history': st.session_state.optimizer.history,
                'n_evals': st.session_state.optimizer.eval_count,
            }
            
            log_message("\n" + "="*50)
            log_message("✓ Optimization completed!")
            log_message(f"  RMSE: {rmse*1000:.3f} mbar, MAE: {mae*1000:.3f} mbar")
            log_message(f"  D range: {D_opt.min()*1e3:.3f} – {D_opt.max()*1e3:.3f} mm")
            
            st.session_state.opt_status = f"✓ Done: RMSE={rmse*1000:.3f} mbar"
            status_placeholder.success(st.session_state.opt_status)
            
            st.success(f"✓ Optimization complete! RMSE: {rmse*1000:.3f} mbar")
        else:
            st.warning("⚠️ Optimization stopped")
            log_message("⚠ Optimization stopped")
            st.session_state.opt_status = "Stopped"
            status_placeholder.warning("Optimization stopped")
        
        st.session_state.opt_running = False
        return True
        
    except Exception as e:
        import traceback
        st.error(f"❌ Optimization failed: {e}")
        log_message(f"✗ Error: {e}")
        log_message(traceback.format_exc())
        st.session_state.opt_running = False
        return False


def stop_optimization():
    """Stop the running optimization."""
    if st.session_state.optimizer:
        st.session_state.optimizer.stop()
        log_message("Stopping...")
        st.session_state.opt_running = False


# =============================================================================
#  TAB RENDERING FUNCTIONS
# =============================================================================

def render_configuration_tab():
    """Render the configuration tab with all parameter inputs."""
    cfg = st.session_state.config
    
    st.header("🎛️ Simulation Configuration")
    
    # Pipeline Geometry
    with st.expander("📏 Pipeline Geometry", expanded=True):
        col1, col2, col3 = st.columns(3)
        with col1:
            cfg['L'] = st.number_input("Pipe Length (m)", value=cfg.get('L', 8000.0), step=10.0)
            cfg['dx'] = st.number_input("Grid Spacing (m)", value=cfg.get('dx', 200.0), step=10.0)
        with col2:
            cfg['D_nom'] = st.number_input("Nominal Diameter (m)", value=cfg.get('D_nom', 0.1937), step=0.001, format="%.4f")
            cfg['eps_mm'] = st.number_input("Roughness (mm)", value=cfg.get('eps_mm', 0.045), step=0.001, format="%.4f")
        with col3:
            cfg['x_pt_m'] = st.number_input("PT Location (m)", value=cfg.get('x_pt_m', 7600.0), step=10.0)
            cfg['valve_pos_m'] = st.number_input("Valve Location (m)", value=cfg.get('valve_pos_m', 8000.0), step=10.0)
        
        update_segment_count()
        st.info(f"**Optimizable Segments:** {st.session_state.n_segments}")
    
    # Gas Properties
    with st.expander("🎈 Gas Properties", expanded=True):
        col1, col2, col3 = st.columns(3)
        with col1:
            cfg['T_celsius'] = st.number_input("Temperature (°C)", value=cfg.get('T_celsius', 25.0), step=1.0)
            cfg['R_gas'] = st.number_input("Gas Constant R (J/kg·K)", value=cfg.get('R_gas', 424.0), step=1.0)
        with col2:
            cfg['mu_dyn'] = st.text_input("Dynamic Viscosity (Pa·s)", value=str(cfg.get('mu_dyn', 1.1e-5)))
            cfg['Z_factor'] = st.number_input("Compressibility Z", value=cfg.get('Z_factor', 0.996), step=0.001, format="%.4f")
        with col3:
            cfg['gamma'] = st.number_input("Heat Ratio γ", value=cfg.get('gamma', 1.26), step=0.01, format="%.3f")
            cfg['g'] = st.number_input("Gravity (m/s²)", value=cfg.get('g', 9.81), step=0.1)
    
    # Valve Parameters
    with st.expander("🔧 Valve Parameters (ISA/IEC)", expanded=True):
        col1, col2, col3 = st.columns(3)
        with col1:
            cfg['xT'] = st.number_input("Terminal Pressure-Drop Ratio xT", value=cfg.get('xT', 0.9), step=0.01)
            cfg['Fp'] = st.number_input("Piping Geometry Factor Fp", value=cfg.get('Fp', 1.0), step=0.01)
        with col2:
            cfg['Cv_max'] = st.number_input("Cv_max (rated)", value=cfg.get('Cv_max', 500.0), step=1.0)
            cfg['K_multiplier'] = st.number_input("K Multiplier", value=cfg.get('K_multiplier', 5.0), step=0.1)
        with col3:
            pass
    
    # Valve Timing
    with st.expander("⏱️ Valve Timing (4-Phase Cycle)", expanded=True):
        col1, col2, col3 = st.columns(3)
        with col1:
            cfg['t_valve_open_start'] = st.number_input("Open Start (s)", value=cfg.get('t_valve_open_start', 30.0), step=1.0)
            cfg['t_valve_opening'] = st.number_input("Opening Ramp (s)", value=cfg.get('t_valve_opening', 5.0), step=0.5)
        with col2:
            cfg['t_valve_hold_open'] = st.number_input("Hold Open (s)", value=cfg.get('t_valve_hold_open', 60.0), step=1.0)
            cfg['t_valve_closing'] = st.number_input("Closing Ramp (s)", value=cfg.get('t_valve_closing', 5.0), step=0.5)
        with col3:
            cfg['T_total'] = st.number_input("Total Time (s)", value=cfg.get('T_total', 200.0), step=1.0)
        
        # Show valve timeline
        try:
            t0 = cfg['t_valve_open_start']
            t1 = t0 + cfg['t_valve_opening']
            t2 = t1 + cfg['t_valve_hold_open']
            t3 = t2 + cfg['t_valve_closing']
            ttot = cfg['T_total']
            
            status = "✓" if t3 <= ttot else "⚠ T_total too short!"
            
            st.markdown(f"""
            **Timeline:** 0-{t0:.1f}s CLOSED | {t0:.1f}-{t1:.1f}s OPENING | 
            {t1:.1f}-{t2:.1f}s OPEN | {t2:.1f}-{t3:.1f}s CLOSING | >{t3:.1f}s CLOSED {status}
            """)
        except:
            pass
    
    # Pressures
    with st.expander("📊 Pressures", expanded=True):
        col1, col2, col3 = st.columns(3)
        with col1:
            cfg['P_upstream_bar'] = st.number_input("Upstream Pressure (bar)", value=cfg.get('P_upstream_bar', 8.098), step=0.1)
        with col2:
            cfg['P_atm_bar'] = st.number_input("Downstream Pressure (bar)", value=cfg.get('P_atm_bar', 1.0), step=0.1)
        with col3:
            cfg['upstream_bc'] = st.selectbox("Upstream BC", ["CONSTANT_P", "CLOSED_END", "FINITE_TANK"], 
                                              index=["CONSTANT_P", "CLOSED_END", "FINITE_TANK"].index(cfg.get('upstream_bc', 'CLOSED_END')))
        
        if cfg['upstream_bc'] == "FINITE_TANK":
            cfg['V_tank'] = st.number_input("V_tank (m³)", value=cfg.get('V_tank', 10.0), step=1.0)
    
    # MOC Numerical Parameters
    with st.expander("⚙️ MOC Numerical Parameters", expanded=True):
        col1, col2 = st.columns(2)
        with col1:
            cfg['beta'] = st.number_input("Courant β", value=cfg.get('beta', 0.9), min_value=0.01, max_value=1.0, step=0.01, format="%.4f")
            st.caption("β=1 → exact CFL; β<1 → diffusive/stable")
        with col2:
            cfg['B_factor'] = st.number_input("B_factor", value=cfg.get('B_factor', 1.0), min_value=0.98, max_value=1.02, step=0.001, format="%.4f")
            st.caption("B_eff = sqrt(Z·R·T) × B_factor (±2% wave-speed tuning)")
    
    # Initial Diameter Profile
    with st.expander("📐 Initial Diameter Profile", expanded=True):
        col1, col2 = st.columns([1, 3])
        with col1:
            cfg['profile_type'] = st.radio("Profile Type", ["uniform", "probable"])
        with col2:
            if cfg['profile_type'] == "probable":
                col_a, col_b = st.columns(2)
                with col_a:
                    cfg['prob_D_init'] = st.number_input("Baseline D multiplier", value=cfg.get('prob_D_init', 0.95), step=0.01)
                    cfg['prob_D_mult'] = st.number_input("Reduced D multiplier", value=cfg.get('prob_D_mult', 0.75), step=0.01)
                with col_b:
                    cfg['prob_L_ds'] = st.number_input("Location from DS (m)", value=cfg.get('prob_L_ds', 200.0), step=10.0)
                    cfg['prob_seg_len'] = st.number_input("Reduced segment length (m)", value=cfg.get('prob_seg_len', 1000.0), step=10.0)
    
    # Optimization Settings
    with st.expander("🎯 Optimization Settings", expanded=True):
        col1, col2 = st.columns(2)
        with col1:
            cfg['D_range_min'] = st.number_input("D Multiplier Min", value=cfg.get('D_range_min', 0.70), step=0.01)
            cfg['D_range_max'] = st.number_input("D Multiplier Max", value=cfg.get('D_range_max', 1.05), step=0.01)
            cfg['max_iter'] = st.number_input("Max DE Iterations", value=cfg.get('max_iter', 150), step=10, min_value=10)
            cfg['popsize'] = st.number_input("Population Size", value=cfg.get('popsize', 15), step=5, min_value=5)
        with col2:
            cfg['lambda_smooth'] = st.text_input("λ Smoothness", value=str(cfg.get('lambda_smooth', 1e-6)))
            cfg['lambda_tv'] = st.text_input("λ Total Var", value=str(cfg.get('lambda_tv', 1e-7)))
            cfg['workers'] = st.number_input("DE Workers", value=cfg.get('workers', 1), min_value=1, step=1)
            if cfg['workers'] > 1:
                st.warning("⚠️ Workers > 1 may cause issues in Streamlit")
            cfg['method'] = st.selectbox("Method", ["differential_evolution", "de_then_lbfgsb", "lbfgsb"])
    
    st.divider()
    
    # Action buttons
    col1, col2, col3 = st.columns([1, 1, 1])
    with col1:
        if st.button("▶️ Run Simulation", disabled=st.session_state.t_pt is None):
            run_simulation()
            st.rerun()
    with col2:
        if st.button("🔍 Start Optimization", disabled=(st.session_state.t_pt is None or st.session_state.opt_running)):
            run_optimization()
            st.rerun()
    with col3:
        if st.button("⏹ Stop Optimization", disabled=not st.session_state.opt_running):
            stop_optimization()
            st.rerun()
    
    # Status
    st.info(f"**Status:** {st.session_state.opt_status}")


def render_results_tab():
    """Render the results tab with summary information."""
    st.header("📊 Results Summary")
    
    if st.session_state.result_data is None and st.session_state.initial_simulation is None:
        st.info("💡 Run a simulation or optimization to see results here.")
        return
    
    # Show initial simulation results
    if st.session_state.initial_simulation:
        init = st.session_state.initial_simulation
        st.subheader("🔵 Initial Simulation")
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("RMSE", f"{init['rmse']*1000:.3f} mbar")
        with col2:
            st.metric("MAE", f"{init['mae']*1000:.3f} mbar")
        with col3:
            st.metric("Profile", init['profile_type'])
    
    # Show optimization results
    if st.session_state.result_data:
        res = st.session_state.result_data
        st.subheader("🟢 Optimized Results")
        
        col1, col2, col3 = st.columns(3)
        with col1:
            init_rmse = st.session_state.initial_simulation['rmse'] * 1000 if st.session_state.initial_simulation else 0
            delta = res['rmse']*1000 - init_rmse
            st.metric("RMSE", f"{res['rmse']*1000:.3f} mbar", delta=f"{delta:.3f} mbar")
        with col2:
            st.metric("MAE", f"{res['mae']*1000:.3f} mbar")
        with col3:
            st.metric("Evaluations", res['n_evals'])
        
        # Diameter statistics
        D_opt = res['D_opt_array']
        st.subheader("Diameter Statistics")
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Mean", f"{D_opt.mean()*1000:.3f} mm")
        with col2:
            st.metric("Min", f"{D_opt.min()*1000:.3f} mm")
        with col3:
            st.metric("Max", f"{D_opt.max()*1000:.3f} mm")
        with col4:
            st.metric("Std Dev", f"{D_opt.std()*1000:.3f} mm")
        
        # Export options
        st.subheader("💾 Export Results")
        col1, col2, col3 = st.columns(3)
        with col1:
            export_results_csv()
        with col2:
            export_diameters_csv()
        with col3:
            save_config()


def render_convergence_tab():
    """Render the convergence tab with optimization history."""
    st.header("📈 Convergence History")
    
    if st.session_state.result_data is None:
        st.info("💡 Run optimization to see convergence history.")
        return
    
    res = st.session_state.result_data
    hist = res['history']
    
    if not hist:
        st.info("No optimization history available.")
        return
    
    evals = [h['eval'] for h in hist]
    rmse = [h['rmse_mbar'] for h in hist]
    D_mean = [h['D_mean'] * 1e3 for h in hist]
    D_std = [h['D_std'] * 1e3 for h in hist]
    
    # Plot RMSE convergence
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 8))
    
    # RMSE plot
    ax1.semilogy(evals, rmse, '-', lw=1, color='lightsteelblue', alpha=0.6, label='RMSE per eval')
    best_so_far = []
    best = np.inf
    for r in rmse:
        if r < best:
            best = r
        best_so_far.append(best)
    ax1.semilogy(evals, best_so_far, '-', lw=2.5, color='steelblue', label='Best RMSE so far')
    ax1.set_ylabel("RMSE (mbar) — log scale")
    ax1.set_title("Convergence — RMSE vs Evaluation Number")
    ax1.legend(fontsize=9)
    ax1.grid(True, alpha=0.3, which='both')
    
    # Diameter evolution
    ax2.plot(evals, D_mean, 'g-', lw=2, label='Mean D (mm)')
    ax2.fill_between(evals,
                     np.array(D_mean) - np.array(D_std),
                     np.array(D_mean) + np.array(D_std),
                     alpha=0.25, color='g', label='±1σ')
    ax2.axhline(res['D_nom'] * 1e3, color='gray', ls='--', lw=1.2, 
                label=f'Nominal {res["D_nom"]*1e3:.2f} mm')
    ax2.set_xlabel("Evaluation #")
    ax2.set_ylabel("Diameter (mm)")
    ax2.set_title("Diameter Mean ± Std vs Evaluation")
    ax2.legend(fontsize=9)
    ax2.grid(True, alpha=0.3)
    
    fig.tight_layout()
    st.pyplot(fig)
    
    # Summary statistics
    st.subheader("Summary Statistics")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Initial RMSE", f"{rmse[0]:.3f} mbar")
    with col2:
        st.metric("Final RMSE", f"{rmse[-1]:.3f} mbar")
    with col3:
        st.metric("Improvement", f"{rmse[0] - rmse[-1]:.3f} mbar")


def render_diameter_profile_tab():
    """Render the diameter profile tab."""
    st.header("📏 Diameter Profile")
    
    res = st.session_state.result_data or st.session_state.initial_simulation
    
    if res is None:
        st.info("💡 Run a simulation or optimization to see diameter profile.")
        return
    
    # Get data
    if st.session_state.result_data:
        x = st.session_state.result_data['x_segments']
        D_o = st.session_state.result_data['D_opt_array'] * 1e3
        D_n = st.session_state.result_data['D_nom'] * 1e3
        D_i = st.session_state.D_initial_profile * 1e3 if st.session_state.D_initial_profile is not None else None
        is_optimized = True
    else:
        # Use initial simulation
        cfg = st.session_state.config
        L = float(cfg['L'])
        dx = float(cfg['dx'])
        n = st.session_state.n_segments
        x = np.linspace(0, L, n)
        D_o = st.session_state.initial_simulation['D_array'] * 1e3
        D_n = float(cfg['D_nom']) * 1e3
        D_i = None
        is_optimized = False
    
    # Create figure
    fig, ax = plt.subplots(figsize=(12, 6))
    
    # Plot optimized/initial profile
    label = 'Optimized' if is_optimized else 'Initial'
    ax.plot(x, D_o, '-o', lw=2, ms=3, color='red', 
            label=f'{label} ({D_o.min():.2f}–{D_o.max():.2f} mm)')
    
    # Plot initial profile if available
    if D_i is not None:
        ax.plot(x, D_i, '--', lw=1.5, color='orange', alpha=0.7, label='Initial profile')
    
    # Reference lines
    ax.axhline(D_n, color='gray', ls=':', lw=1.5, label=f'Nominal {D_n:.2f} mm')
    ax.fill_between(x, D_n, D_o, alpha=0.2, color='green')
    
    # Valve and PT positions
    cfg = st.session_state.config
    vx = float(cfg['valve_pos_m'])
    px = float(cfg['x_pt_m'])
    ax.axvline(vx, color='purple', ls=':', lw=1.5, label=f'Valve @ {vx:.0f} m')
    ax.axvline(px, color='blue', ls=':', lw=1.5, label=f'PT @ {px:.0f} m')
    
    ax.set_xlabel("Position (m)")
    ax.set_ylabel("Diameter (mm)")
    profile_type = st.session_state.result_data.get('profile_type', '') if st.session_state.result_data else \
                  st.session_state.initial_simulation.get('profile_type', 'initial')
    ax.set_title(f"{'Optimized' if is_optimized else 'Initial'} Diameter Profile ({st.session_state.n_segments} segments)", 
                 fontweight='bold')
    ax.legend()
    ax.grid(True, alpha=0.3)
    
    fig.tight_layout()
    st.pyplot(fig)
    
    # Show elevation profile if available
    if st.session_state.elevation_profile is not None:
        st.subheader("⛰ Elevation Profile")
        
        fig2, ax2 = plt.subplots(figsize=(12, 4))
        ep = st.session_state.elevation_profile
        ax2.plot(ep[:, 0], ep[:, 1], '-o', lw=2, ms=4, color='saddlebrown')
        ax2.fill_between(ep[:, 0], ep[:, 1].min(), ep[:, 1], alpha=0.25, color='saddlebrown')
        ax2.axvline(vx, color='purple', ls=':', lw=1.5)
        ax2.axvline(px, color='blue', ls=':', lw=1.5)
        ax2.set_xlabel("Distance (m)")
        ax2.set_ylabel("Elevation (m)")
        ax2.set_title("Pipeline Elevation Profile")
        ax2.legend()
        ax2.grid(True, alpha=0.3)
        
        fig2.tight_layout()
        st.pyplot(fig2)


def render_pressure_match_tab():
    """Render the pressure match tab."""
    st.header("🎯 Pressure Match")
    
    if st.session_state.result_data is None and st.session_state.initial_simulation is None:
        st.info("💡 Run a simulation or optimization to see pressure match.")
        return
    
    fig, ax = plt.subplots(figsize=(12, 6))
    
    # Plot PT data
    ax.plot(st.session_state.t_pt, st.session_state.p_pt, 'o', ms=2, alpha=0.6, 
            label='PT Data (downstream)', color='blue')
    
    # Plot initial simulation if available
    if st.session_state.initial_simulation:
        init = st.session_state.initial_simulation
        ax.plot(init['t_model'], init['p_model'], '--', lw=2, alpha=0.7, 
                label=f'Initial ({init["profile_type"]})', color='orange')
    
    # Plot optimized if available
    if st.session_state.result_data:
        res = st.session_state.result_data
        ax.plot(res['t_model'], res['p_model'], '-', lw=2, label='Optimized', color='red')
    
    ax.set_xlabel("Time (s)")
    ax.set_ylabel("Pressure (bar)")
    ax.set_title("Downstream Pressure Match — Diameter Optimization", fontweight='bold')
    ax.legend()
    ax.grid(True, alpha=0.3)
    
    fig.tight_layout()
    st.pyplot(fig)
    
    # Show metrics
    if st.session_state.result_data:
        res = st.session_state.result_data
        col1, col2 = st.columns(2)
        with col1:
            st.metric("Optimized RMSE", f"{res['rmse']*1000:.3f} mbar")
        with col2:
            if st.session_state.initial_simulation:
                improvement = (st.session_state.initial_simulation['rmse'] - res['rmse']) * 1000
                st.metric("Improvement", f"{improvement:.3f} mbar")


def render_error_analysis_tab():
    """Render the error analysis tab."""
    st.header("📊 Error Analysis")
    
    if st.session_state.result_data is None and st.session_state.initial_simulation is None:
        st.info("💡 Run a simulation or optimization to see error analysis.")
        return
    
    # Create figure
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 8))
    
    # Error vs time
    if st.session_state.result_data:
        res = st.session_state.result_data
        err_o = res['error'] * 1000
        ax1.plot(res['t_pt'], err_o, '-', lw=1.5, color='red', label='Optimized Error')
        ax1.fill_between(res['t_pt'], err_o, alpha=0.3, color='red')
    
    if st.session_state.initial_simulation:
        init = st.session_state.initial_simulation
        err_i = (init['p_interp'] - st.session_state.p_pt) * 1000
        ax1.plot(init['t_pt'], err_i, '-', lw=1.5, color='orange', alpha=0.7, label='Initial Error')
        ax1.fill_between(init['t_pt'], err_i, alpha=0.2, color='orange')
    
    ax1.axhline(0, color='k', lw=0.8, ls='--')
    ax1.set_ylabel("Error (mbar)")
    ax1.set_title("Model Error Comparison")
    ax1.legend()
    ax1.grid(True, alpha=0.3)
    
    # Error distribution
    if st.session_state.result_data:
        res = st.session_state.result_data
        err_o = res['error'] * 1000
        ax2.hist(err_o, bins=30, alpha=0.5, color='red', label='Optimized', edgecolor='black')
        if st.session_state.initial_simulation:
            init = st.session_state.initial_simulation
            err_i = (init['p_interp'] - st.session_state.p_pt) * 1000
            ax2.hist(err_i, bins=30, alpha=0.5, color='orange', label='Initial', edgecolor='black')
        ax2.axvline(0, color='k', lw=1.5, ls='--')
        ax2.axvline(err_o.mean(), color='red', lw=1.5, ls='--', 
                    label=f'Mean = {err_o.mean():.2f} mbar')
        ax2.set_xlabel("Error (mbar)")
        ax2.set_ylabel("Frequency")
        ax2.set_title("Error Distribution")
        ax2.legend()
        ax2.grid(True, alpha=0.3, axis='y')
    
    fig.tight_layout()
    st.pyplot(fig)


# =============================================================================
#  EXPORT FUNCTIONS
# =============================================================================

def export_results_csv():
    """Export simulation/optimization results to CSV."""
    if st.session_state.result_data is None:
        st.warning("⚠️ No results to export")
        return
    
    res = st.session_state.result_data
    
    df = pd.DataFrame({
        'time_s': res['t_pt'],
        'pressure_pt_bar': res['p_pt'],
        'pressure_model_bar': res['p_interp'],
        'error_mbar': res['error'] * 1000,
    })
    
    csv_str = df.to_csv(index=False)
    st.download_button(
        label="📥 Export Results CSV",
        data=csv_str,
        file_name=f"results_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
        mime="text/csv",
    )


def export_diameters_csv():
    """Export segment diameters to CSV."""
    if st.session_state.result_data is None and st.session_state.initial_simulation is None:
        st.warning("⚠️ No results to export")
        return
    
    # Use whichever is available
    res = st.session_state.result_data or st.session_state.initial_simulation
    
    if st.session_state.result_data:
        x = st.session_state.result_data['x_segments']
        D_n = st.session_state.result_data['D_nom'] * 1e3
        D_o = st.session_state.result_data['D_opt_array'] * 1e3
        is_optimized = True
    else:
        cfg = st.session_state.config
        x = np.linspace(0, float(cfg['L']), st.session_state.n_segments)
        D_n = float(cfg['D_nom']) * 1e3
        D_o = st.session_state.initial_simulation['D_array'] * 1e3
        is_optimized = False
    
    elev_arr = None
    if st.session_state.result_data:
        elev_arr = st.session_state.result_data.get('elevation_arr', None)
    
    if elev_arr is not None and len(elev_arr) == len(x) + 1:
        elev_seg = 0.5 * (elev_arr[:-1] + elev_arr[1:])
    elif elev_arr is not None and len(elev_arr) == len(x):
        elev_seg = elev_arr
    else:
        elev_seg = np.zeros(len(x))
    
    D_i = (st.session_state.D_initial_profile * 1e3
           if st.session_state.D_initial_profile is not None
           else np.full(len(x), D_n))
    
    df = pd.DataFrame({
        'segment': np.arange(1, len(D_o) + 1),
        'position_m': x,
        'elevation_m': elev_seg,
        'nominal_D_mm': D_n,
        'initial_D_mm': D_i,
    })
    
    if is_optimized:
        df['optimized_D_mm'] = D_o
        df['change_pct'] = (D_o - D_n) / D_n * 100
    else:
        df['simulation_D_mm'] = D_o
        df['deviation_pct'] = (D_o - D_n) / D_n * 100
    
    csv_str = df.to_csv(index=False)
    filename = "diameters" if is_optimized else "simulation_diameters"
    st.download_button(
        label=f"📥 Export {'Optimized Diameters' if is_optimized else 'Simulation Diameters'} CSV",
        data=csv_str,
        file_name=f"{filename}_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
        mime="text/csv",
    )


# =============================================================================
#  MAIN ENTRY POINT
# =============================================================================

if __name__ == "__main__":
    # Set matplotlib style
    plt.style.use('seaborn-v0_8')
    
    # Configure matplotlib for better display in Streamlit
    matplotlib.rcParams['figure.figsize'] = (10, 6)
    matplotlib.rcParams['axes.labelsize'] = 12
    matplotlib.rcParams['axes.titlesize'] = 14
    matplotlib.rcParams['legend.fontsize'] = 10
    
    # Run the Streamlit app
    main()
