#!/bin/bash

# Home Assistant MQTT Plugin Installer for Steam Deck
# Installs the Decky plugin from a local zip file or GitHub URL

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Plugin directory
PLUGIN_DIR="$HOME/homebrew/plugins"
PLUGIN_NAME="decky-plugin-homeassistant"

# Function to print colored messages
print_error() {
    echo -e "${RED}ERROR: $1${NC}" >&2
}

print_success() {
    echo -e "${GREEN}SUCCESS: $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}WARNING: $1${NC}"
}

print_info() {
    echo -e "$1"
}

# Function to check if a command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Function to download file
download_file() {
    local url="$1"
    local output="$2"
    
    if command_exists curl; then
        curl -fsSL -o "$output" "$url"
    elif command_exists wget; then
        wget -q -O "$output" "$url"
    else
        print_error "Neither curl nor wget is available. Please install one of them."
        exit 1
    fi
}

# Main installation function
install_plugin() {
    local source="$1"
    local temp_zip=""
    local cleanup_zip=false
    
    # Check if source is provided
    if [ -z "$source" ]; then
        print_error "No zip file or URL provided."
        echo ""
        echo "Usage: $0 <zip-file-or-url>"
        echo ""
        echo "Examples:"
        echo "  $0 /path/to/decky-plugin-homeassistant-v1.0.1.zip"
        echo "  $0 https://github.com/jamesbiederbeck/decky-plugin-homeassistant/releases/download/v1.0.1/decky-plugin-homeassistant-v1.0.1.zip"
        exit 1
    fi
    
    # Determine if source is a URL or local file
    if [[ "$source" =~ ^https?:// ]]; then
        print_info "Downloading plugin from URL..."
        temp_zip="/tmp/${PLUGIN_NAME}-$(date +%s).zip"
        cleanup_zip=true
        
        if ! download_file "$source" "$temp_zip"; then
            print_error "Failed to download file from $source"
            exit 1
        fi
        
        print_success "Downloaded successfully"
    else
        # Local file
        if [ ! -f "$source" ]; then
            print_error "File not found: $source"
            exit 1
        fi
        temp_zip="$source"
    fi
    
    # Verify it's a zip file
    if ! file "$temp_zip" | grep -q "Zip archive"; then
        print_error "File is not a valid zip archive: $temp_zip"
        [ "$cleanup_zip" = true ] && rm -f "$temp_zip"
        exit 1
    fi
    
    # Check if unzip is available
    if ! command_exists unzip; then
        print_error "unzip command not found. Please install unzip."
        [ "$cleanup_zip" = true ] && rm -f "$temp_zip"
        exit 1
    fi
    
    # Create plugin directory if it doesn't exist
    if [ ! -d "$PLUGIN_DIR" ]; then
        print_warning "Plugin directory does not exist: $PLUGIN_DIR"
        print_info "Creating directory..."
        mkdir -p "$PLUGIN_DIR"
    fi
    
    # Check if plugin already exists
    if [ -d "$PLUGIN_DIR/$PLUGIN_NAME" ]; then
        print_warning "Plugin already exists at $PLUGIN_DIR/$PLUGIN_NAME"
        read -p "Do you want to overwrite it? (y/N): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            print_info "Installation cancelled."
            [ "$cleanup_zip" = true ] && rm -f "$temp_zip"
            exit 0
        fi
        print_info "Removing existing plugin..."
        rm -rf "$PLUGIN_DIR/$PLUGIN_NAME"
    fi
    
    # Extract zip file
    print_info "Extracting plugin to $PLUGIN_DIR..."
    if ! unzip -q "$temp_zip" -d "$PLUGIN_DIR"; then
        print_error "Failed to extract zip file"
        [ "$cleanup_zip" = true ] && rm -f "$temp_zip"
        exit 1
    fi
    
    # Verify installation
    if [ -d "$PLUGIN_DIR/$PLUGIN_NAME" ] && [ -f "$PLUGIN_DIR/$PLUGIN_NAME/main.py" ]; then
        print_success "Plugin installed successfully!"
        echo ""
        print_info "Plugin location: $PLUGIN_DIR/$PLUGIN_NAME"
        echo ""
        print_info "To complete the installation:"
        print_info "  1. Restart Decky Loader (or restart your Steam Deck)"
        print_info "  2. Open the Decky menu (... button)"
        print_info "  3. Look for 'Home Assistant MQTT' in the plugin list"
        echo ""
    else
        print_error "Plugin installation verification failed"
        print_error "Expected files not found in $PLUGIN_DIR/$PLUGIN_NAME"
        [ "$cleanup_zip" = true ] && rm -f "$temp_zip"
        exit 1
    fi
    
    # Cleanup
    if [ "$cleanup_zip" = true ]; then
        rm -f "$temp_zip"
    fi
}

# Check if running as root
if [ "$EUID" -eq 0 ]; then
    print_warning "This script should not be run as root"
    print_info "Please run as the deck user"
    exit 1
fi

# Run installation
install_plugin "$1"
