#!/bin/bash

# cleanup.sh - Intelligent cleanup script for ML pipeline stages
# Usage: ./cleanup.sh [stage]
# Stages: datamart, training, inference, monitoring, all

set -e  # Exit on error

# Get the directory where this script is located
CLEANUP_SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SCRIPT_DIR="${CLEANUP_SCRIPT_DIR}/scripts"

# Color codes for output (using $'...' syntax for escape sequences)
RED=$'\033[0;31m'
GREEN=$'\033[0;32m'
YELLOW=$'\033[1;33m'
BLUE=$'\033[0;34m'
NC=$'\033[0m' # No Color

print_header() {
    echo -e "${BLUE}================================================${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}================================================${NC}"
}

print_info() {
    echo -e "${GREEN}✓${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}⚠${NC}  $1"
}

print_error() {
    echo -e "${RED}✗${NC} $1"
}

cleanup_monitoring() {
    print_header "Cleaning: Model Monitoring Outputs"

    if [ -d "$SCRIPT_DIR/datamart/gold/monitoring" ]; then
        rm -rf "$SCRIPT_DIR/datamart/gold/monitoring"/*
        print_info "Removed monitoring metrics"
    else
        print_warning "Monitoring directory doesn't exist yet"
    fi
}

cleanup_inference() {
    print_header "Cleaning: Model Inference + Downstream"

    # Clean predictions
    if [ -d "$SCRIPT_DIR/datamart/gold/predictions" ]; then
        rm -rf "$SCRIPT_DIR/datamart/gold/predictions"/*
        print_info "Removed prediction outputs"
    else
        print_warning "Predictions directory doesn't exist yet"
    fi

    # Cascade: Clean monitoring too
    cleanup_monitoring
}

cleanup_training() {
    print_header "Cleaning: Model Training + Downstream"

    # Clean model artifacts
    if [ -d "$SCRIPT_DIR/model_store/model_1" ]; then
        rm -rf "$SCRIPT_DIR/model_store/model_1"/*
        print_info "Removed Model 1 artifacts"
    fi

    if [ -d "$SCRIPT_DIR/model_store/model_2" ]; then
        rm -rf "$SCRIPT_DIR/model_store/model_2"/*
        print_info "Removed Model 2 artifacts"
    fi

    # Cascade: Clean inference and monitoring too
    cleanup_inference
}

cleanup_datamart() {
    print_header "Cleaning: Datamart (Bronze/Silver/Gold) + ALL Downstream"

    # Clean bronze layer
    if [ -d "$SCRIPT_DIR/datamart/bronze" ]; then
        rm -rf "$SCRIPT_DIR/datamart/bronze"/*
        print_info "Removed bronze layer data"
    fi

    # Clean silver layer
    if [ -d "$SCRIPT_DIR/datamart/silver" ]; then
        rm -rf "$SCRIPT_DIR/datamart/silver"/*
        print_info "Removed silver layer data"
    fi

    # Clean gold layer (features and labels, NOT predictions/monitoring yet)
    if [ -d "$SCRIPT_DIR/datamart/gold/feature_store" ]; then
        rm -rf "$SCRIPT_DIR/datamart/gold/feature_store"/*
        print_info "Removed gold feature store"
    fi

    if [ -d "$SCRIPT_DIR/datamart/gold/label_store" ]; then
        rm -rf "$SCRIPT_DIR/datamart/gold/label_store"/*
        print_info "Removed gold label store"
    fi

    # Clean quarantine
    if [ -d "$SCRIPT_DIR/datamart/quarantine" ]; then
        rm -rf "$SCRIPT_DIR/datamart/quarantine"/*
        print_info "Removed quarantine data"
    fi

    # Cascade: Clean training, inference, and monitoring
    cleanup_training
}

cleanup_all() {
    print_header "Cleaning: EVERYTHING (Full Pipeline Reset)"
    cleanup_datamart
}

show_usage() {
    echo ""
    echo "Usage: ./cleanup.sh [stage]"
    echo ""
    echo "Stages (with automatic downstream cleanup):"
    echo "  ${GREEN}datamart${NC}    - Clean bronze/silver/gold data + training + inference + monitoring"
    echo "  ${GREEN}training${NC}    - Clean model artifacts + inference + monitoring"
    echo "  ${GREEN}inference${NC}   - Clean predictions + monitoring"
    echo "  ${GREEN}monitoring${NC}  - Clean monitoring metrics only"
    echo "  ${GREEN}all${NC}         - Clean everything (same as datamart)"
    echo ""
    echo "Examples:"
    echo "  ./cleanup.sh datamart    # Changed feature engineering? Clean datamart"
    echo "  ./cleanup.sh training    # Changed model hyperparameters? Clean training"
    echo "  ./cleanup.sh inference   # Changed inference logic? Clean inference"
    echo "  ./cleanup.sh monitoring  # Changed monitoring metrics? Clean monitoring"
    echo ""
}

confirm_cleanup() {
    local stage=$1
    echo ""
    print_warning "You are about to clean: ${YELLOW}${stage}${NC}"
    print_warning "This will remove output files and may require DAG rerun."
    echo ""
    read -p "Are you sure? (y/N) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        print_error "Cleanup cancelled"
        exit 1
    fi
}

# Main execution
if [ $# -eq 0 ]; then
    show_usage
    exit 1
fi

STAGE=$1

case $STAGE in
    monitoring)
        confirm_cleanup "monitoring only"
        cleanup_monitoring
        ;;
    inference)
        confirm_cleanup "inference + monitoring"
        cleanup_inference
        ;;
    training)
        confirm_cleanup "training + inference + monitoring"
        cleanup_training
        ;;
    datamart)
        confirm_cleanup "datamart + training + inference + monitoring"
        cleanup_datamart
        ;;
    all)
        confirm_cleanup "EVERYTHING"
        cleanup_all
        ;;
    *)
        print_error "Unknown stage: $STAGE"
        show_usage
        exit 1
        ;;
esac

echo ""
print_header "Cleanup Complete!"
echo ""
print_info "Pipeline stage ${GREEN}${STAGE}${NC} and downstream outputs have been cleaned"
print_info "Ready for DAG rerun"
echo ""
