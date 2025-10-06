# ui/pages/settings.py

import streamlit as st
import asyncio
from config import load_config, save_config, get_broker_url
from mqtt_client import connect, disconnect
from auth import add_or_update_user, list_users, delete_user, get_user_count, ensure_default_admin
from streamlit.runtime.scriptrunner import RerunException, RerunData

def render_settings():
    st.header("Settings")

    # Load config
    cfg = load_config()
    
    # General Configuration (displayed first)
    st.subheader("General Configuration")
    st.caption("Fleet client identification settings")
    
    # General settings
    manufacturer = st.text_input("Manufacturer", value=cfg["general"]["manufacturer"])
    serial_number = st.text_input("Serial Number", value=cfg["general"]["serial_number"])
    
    if st.button("💾 Save General Settings"):
        # Update general settings
        new_cfg = cfg.copy()
        new_cfg["general"]["manufacturer"] = manufacturer
        new_cfg["general"]["serial_number"] = serial_number
        
        # Save only the general settings
        general_config = {
            "general": new_cfg["general"]
        }
        save_config(general_config)
        
        # Check what was changed to show appropriate message
        mqtt_related_changed = (
            manufacturer != cfg["general"]["manufacturer"] or 
            serial_number != cfg["general"]["serial_number"]
        )
        
        st.success("General settings saved.")
        
        if mqtt_related_changed:
            st.info("⚠️ Manufacturer/Serial Number changes will take effect after MQTT reconnection.")

    st.markdown("---")
    
    # Map Configuration
    st.subheader("Map Configuration")
    st.caption("Configure map display settings for all maps in the application")
    
    map_style = st.selectbox(
        "Map Style",
        options=["default", "mapbox_satellite"],
        index=0 if cfg["general"].get("map", {}).get("style", "default") == "default" else 1,
        help="Choose between default map or Mapbox satellite imagery",
        key="map_style_select"
    )
    
    default_zoom = st.slider(
        "Default Zoom Level",
        min_value=1,
        max_value=20,
        value=cfg["general"].get("map", {}).get("default_zoom", 15),
        help="Default zoom level for all maps (1=world view, 20=building level)",
        key="default_zoom_slider"
    )
    
    # Add zoom level reference
    st.caption("📏 **Zoom Reference:** 1=World • 5=Country • 10=City • 15=Street • 20=Building (Max)")
    
    # Show Mapbox API key field only if satellite is selected
    mapbox_api_key = ""
    if map_style == "mapbox_satellite":
        mapbox_api_key = st.text_input(
            "Mapbox API Key", 
            value=cfg["general"].get("map", {}).get("mapbox_api_key", ""),
            type="password",
            help="Required: Enter your Mapbox API key to use satellite imagery",
            key="mapbox_api_key"
        )
        
        if not mapbox_api_key:
            st.warning("⚠️ Mapbox API key is required for satellite imagery")
    else:
        # Use existing API key if available, but don't require it
        mapbox_api_key = cfg["general"].get("map", {}).get("mapbox_api_key", "")
    
    if st.button("🗺️ Save Map Settings"):
        # Validate Mapbox configuration
        if map_style == "mapbox_satellite" and not mapbox_api_key:
            st.error("❌ Mapbox API key is required for satellite imagery")
            return
        
        # Update map configuration
        new_cfg = cfg.copy()
        if "map" not in new_cfg["general"]:
            new_cfg["general"]["map"] = {}
        new_cfg["general"]["map"]["style"] = map_style
        new_cfg["general"]["map"]["mapbox_api_key"] = mapbox_api_key
        new_cfg["general"]["map"]["default_zoom"] = default_zoom
        
        # Save only the map settings
        map_config = {
            "general": {
                "map": new_cfg["general"]["map"]
            }
        }
        save_config(map_config)
        
        st.success("Map settings saved.")
        st.info("🗺️ Maps will use the new configuration immediately.")

    st.markdown("---")
    
    # Broker Configuration
    st.subheader("Broker Configuration")
    host = st.text_input("Broker Host", value=cfg["broker"]["host"])
    port = st.number_input("Broker Port", value=cfg["broker"]["port"])
    use_tls = st.checkbox("Use TLS", value=cfg["broker"]["use_tls"])
    buser = st.text_input("Broker Username", value=cfg["broker"]["user"])
    bpass = st.text_input("Broker Password", type="password", value=cfg["broker"]["password"])

    if st.button("💾 Save & Reconnect"):
        # Update broker settings in nested structure
        new_cfg = cfg.copy()
        new_cfg["broker"]["host"] = host
        new_cfg["broker"]["port"] = port
        new_cfg["broker"]["use_tls"] = use_tls
        new_cfg["broker"]["user"] = buser
        new_cfg["broker"]["password"] = bpass
        
        # Save only the broker settings (not the full config)
        broker_config = {
            "broker": new_cfg["broker"]
        }
        save_config(broker_config)

        # Reconnect MQTT synchronously
        try:
            asyncio.run(disconnect())
            asyncio.run(connect(get_broker_url(new_cfg), buser, bpass, client_id="MowbotFleet"))
        except Exception as e:
            st.error(f"Reconnection failed: {e}")
            # Continue anyway to save the config

        st.success("Broker settings saved and reconnected.")
        # Rerun to update header
        raise RerunException(RerunData())

    st.markdown("---")
    
    # User Management Section
    st.subheader("User Management")
    st.caption("Manage system users with full CRUD operations")
    
    # Ensure default admin user exists
    ensure_default_admin()
    
    # Display current users table
    st.markdown("### 👥 Current Users")
    
    users = list_users()
    user_count = get_user_count()
    
    if user_count > 0:
        # Create user table with actions
        for i, (username, created_at, updated_at) in enumerate(users):
            col1, col2, col3, col4, col5 = st.columns([2, 2, 2, 1, 1])
            
            with col1:
                st.write(f"**{username}**")
                if username == "admin":
                    st.caption("🔑 Default admin user")
            
            with col2:
                st.write(f"Created: {created_at}")
            
            with col3:
                st.write(f"Updated: {updated_at}")
            
            with col4:
                # Edit user button
                if st.button("✏️", key=f"edit_{username}", help="Edit user"):
                    st.session_state[f"editing_{username}"] = True
            
            with col5:
                # Delete user button (disabled for admin)
                if username == "admin":
                    st.button("🔒", key=f"delete_{username}", disabled=True, help="Cannot delete admin user")
                else:
                    if st.button("🗑️", key=f"delete_{username}", help="Delete user"):
                        st.session_state["user_to_delete"] = username
            
            # Edit user form (shown when edit button is clicked)
            if st.session_state.get(f"editing_{username}", False):
                st.markdown(f"#### ✏️ Editing User: {username}")
                
                col1, col2 = st.columns(2)
                with col1:
                    new_password = st.text_input(
                        f"New Password for {username}",
                        type="password",
                        key=f"new_pass_{username}",
                        placeholder="Enter new password"
                    )
                
                with col2:
                    st.write("")  # Spacing
                    col2_1, col2_2 = st.columns(2)
                    with col2_1:
                        if st.button("💾 Save", key=f"save_{username}"):
                            if new_password:
                                if add_or_update_user(username, new_password):
                                    st.success(f"Password updated for {username}")
                                    st.session_state[f"editing_{username}"] = False
                                    st.rerun()
                                else:
                                    st.error(f"Failed to update password for {username}")
                            else:
                                st.error("Password cannot be empty")
                    
                    with col2_2:
                        if st.button("❌ Cancel", key=f"cancel_{username}"):
                            st.session_state[f"editing_{username}"] = False
                            st.rerun()
            
            # Delete confirmation (shown when delete button is clicked)
            if st.session_state.get("user_to_delete") == username:
                st.error(f"⚠️ Are you sure you want to delete user '{username}'?")
                col1, col2 = st.columns(2)
                with col1:
                    if st.button("✅ Yes, Delete", key=f"confirm_delete_{username}"):
                        if delete_user(username):
                            st.success(f"User '{username}' deleted successfully")
                            st.session_state["user_to_delete"] = None
                            st.rerun()
                        else:
                            st.error(f"Failed to delete user '{username}'")
                
                with col2:
                    if st.button("❌ Cancel", key=f"cancel_delete_{username}"):
                        st.session_state["user_to_delete"] = None
                        st.rerun()
        
        st.markdown("---")
    
    # Add new user section
    st.markdown("### ➕ Add New User")
    
    col1, col2 = st.columns(2)
    with col1:
        new_user = st.text_input("Username", key="new_user", placeholder="Enter username")
    
    with col2:
        new_pass = st.text_input("Password", type="password", key="new_pass", placeholder="Enter password")
    
    if st.button("➕ Add User", type="primary"):
        if not new_user or not new_pass:
            st.error("Username and password cannot be empty.")
        elif new_user.strip() == "":
            st.error("Username cannot be empty or just spaces.")
        else:
            if add_or_update_user(new_user.strip(), new_pass):
                st.success(f"User '{new_user}' added successfully!")
                st.rerun()
            else:
                st.error(f"Failed to add user '{new_user}'. User may already exist.")
    
    # User management info
    st.info(f"📊 **Total Users:** {user_count} | 🔑 **Admin User:** Always available | 🛡️ **Admin Protection:** Cannot be deleted")
