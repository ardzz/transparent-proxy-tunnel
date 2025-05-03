#!/bin/bash

VENV_DIR="venv"  # Default virtual environment directory

# Function to create virtual environment if it doesn't exist
setup_venv() {
    if [ ! -d "$VENV_DIR" ]; then
        python3 -m venv "$VENV_DIR"
        echo "Virtual environment created at $VENV_DIR."
    else
        echo "Virtual environment already exists at $VENV_DIR."
    fi
}

# Function to activate virtual environment
activate_venv() {
    if [ -d "$VENV_DIR" ]; then
        source "$VENV_DIR/bin/activate"
        echo "Virtual environment activated."
    else
        echo "Virtual environment not found. Please run 'setup' first."
    fi
}

# Function to deactivate virtual environment
deactivate_venv() {
    if [ -n "$VIRTUAL_ENV" ]; then
        deactivate
        echo "Virtual environment deactivated."
    else
        echo "No virtual environment is currently active."
    fi
}

# Main script logic
case "$1" in
    setup)
        setup_venv
        ;;
    activate)
        activate_venv
        ;;
    deactivate)
        deactivate_venv
        ;;
    *)
        echo "Usage: $0 {setup|activate|deactivate}"
        exit 1
        ;;
esac