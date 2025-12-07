#!/bin/bash

# ============================================================================
# DoclingServer API Test Script
# ============================================================================
# Tests the containerized API endpoints and validates functionality
#
# Usage:
#   ./test/test_api.sh
#
# Requirements:
#   - Docker container running (docker-compose up -d)
#   - curl installed
#   - jq installed (optional, for pretty JSON output)

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
API_URL="http://localhost:8000"
TEST_PDF="../data/Managerial-economics.pdf"

# Helper functions
print_header() {
    echo -e "\n${BLUE}========================================${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}========================================${NC}\n"
}

print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

print_error() {
    echo -e "${RED}✗ $1${NC}"
}

print_info() {
    echo -e "${YELLOW}→ $1${NC}"
}

# Check if jq is installed
HAS_JQ=false
if command -v jq &> /dev/null; then
    HAS_JQ=true
fi

# ============================================================================
# Test 1: Container Health
# ============================================================================
print_header "Test 1: Container Health"

print_info "Checking if container is running..."
if docker ps | grep -q docling-api; then
    print_success "Container is running"
else
    print_error "Container is not running!"
    echo "Run: docker-compose up -d"
    exit 1
fi

# ============================================================================
# Test 2: Health Endpoint
# ============================================================================
print_header "Test 2: Health Endpoint"

print_info "Testing GET /health..."
HEALTH_RESPONSE=$(curl -s -w "\n%{http_code}" "$API_URL/health")
HTTP_CODE=$(echo "$HEALTH_RESPONSE" | tail -n1)
RESPONSE_BODY=$(echo "$HEALTH_RESPONSE" | sed '$d')

if [ "$HTTP_CODE" -eq 200 ]; then
    print_success "Health check passed (HTTP $HTTP_CODE)"
    if [ "$HAS_JQ" = true ]; then
        echo "$RESPONSE_BODY" | jq '.'
    else
        echo "$RESPONSE_BODY"
    fi
else
    print_error "Health check failed (HTTP $HTTP_CODE)"
    exit 1
fi

# ============================================================================
# Test 3: Readiness Endpoint
# ============================================================================
print_header "Test 3: Readiness Endpoint"

print_info "Testing GET /ready..."
READY_RESPONSE=$(curl -s -w "\n%{http_code}" "$API_URL/ready")
HTTP_CODE=$(echo "$READY_RESPONSE" | tail -n1)
RESPONSE_BODY=$(echo "$READY_RESPONSE" | sed '$d')

if [ "$HTTP_CODE" -eq 200 ]; then
    print_success "Readiness check passed (HTTP $HTTP_CODE)"
    if [ "$HAS_JQ" = true ]; then
        echo "$RESPONSE_BODY" | jq '.'
    else
        echo "$RESPONSE_BODY"
    fi
else
    print_error "Readiness check failed (HTTP $HTTP_CODE)"
    echo "$RESPONSE_BODY"
fi

# ============================================================================
# Test 4: Root Endpoint
# ============================================================================
print_header "Test 4: Root Endpoint"

print_info "Testing GET /..."
ROOT_RESPONSE=$(curl -s -w "\n%{http_code}" "$API_URL/")
HTTP_CODE=$(echo "$ROOT_RESPONSE" | tail -n1)
RESPONSE_BODY=$(echo "$ROOT_RESPONSE" | sed '$d')

if [ "$HTTP_CODE" -eq 200 ]; then
    print_success "Root endpoint passed (HTTP $HTTP_CODE)"
    if [ "$HAS_JQ" = true ]; then
        echo "$RESPONSE_BODY" | jq '.'
    else
        echo "$RESPONSE_BODY"
    fi
else
    print_error "Root endpoint failed (HTTP $HTTP_CODE)"
fi

# ============================================================================
# Test 5: API Documentation
# ============================================================================
print_header "Test 5: API Documentation"

print_info "Testing GET /docs..."
DOCS_RESPONSE=$(curl -s -w "\n%{http_code}" "$API_URL/docs")
HTTP_CODE=$(echo "$DOCS_RESPONSE" | tail -n1)

if [ "$HTTP_CODE" -eq 200 ]; then
    print_success "API docs accessible (HTTP $HTTP_CODE)"
    print_info "View at: $API_URL/docs"
else
    print_error "API docs failed (HTTP $HTTP_CODE)"
fi

# ============================================================================
# Test 6: PDF Analysis (if test PDF exists)
# ============================================================================
print_header "Test 6: PDF Analysis"

if [ ! -f "$TEST_PDF" ]; then
    print_error "Test PDF not found at: $TEST_PDF"
    print_info "Skipping PDF analysis test"
    print_info "To test PDF analysis, place a PDF at: $TEST_PDF"
else
    print_info "Testing POST /api/v1/analyze with test PDF..."
    print_info "This may take 30-60 seconds..."

    ANALYZE_RESPONSE=$(curl -s -w "\n%{http_code}" \
        -X POST "$API_URL/api/v1/analyze" \
        -F "file=@$TEST_PDF" \
        --max-time 300)

    HTTP_CODE=$(echo "$ANALYZE_RESPONSE" | tail -n1)
    RESPONSE_BODY=$(echo "$ANALYZE_RESPONSE" | sed '$d')

    if [ "$HTTP_CODE" -eq 200 ]; then
        print_success "PDF analysis completed (HTTP $HTTP_CODE)"

        if [ "$HAS_JQ" = true ]; then
            echo "$RESPONSE_BODY" | jq '.'

            # Extract job details
            JOB_ID=$(echo "$RESPONSE_BODY" | jq -r '.job_id')
            STATUS=$(echo "$RESPONSE_BODY" | jq -r '.status')
            PROCESSING_TIME=$(echo "$RESPONSE_BODY" | jq -r '.processing_time_seconds')

            echo ""
            print_success "Job ID: $JOB_ID"
            print_success "Status: $STATUS"
            print_success "Processing time: ${PROCESSING_TIME}s"

            # Check for output files
            MARKDOWN_PATH=$(echo "$RESPONSE_BODY" | jq -r '.results.markdown_path')
            SUMMARY_PATH=$(echo "$RESPONSE_BODY" | jq -r '.results.summary_path')

            echo ""
            print_info "Generated files:"
            echo "  - Markdown: $MARKDOWN_PATH"
            echo "  - Summary: $SUMMARY_PATH"
        else
            echo "$RESPONSE_BODY"
        fi
    else
        print_error "PDF analysis failed (HTTP $HTTP_CODE)"
        echo "$RESPONSE_BODY"
    fi
fi

# ============================================================================
# Test 7: Invalid File Type
# ============================================================================
print_header "Test 7: Invalid File Type (Error Handling)"

print_info "Testing with invalid file type (should fail)..."

# Create a temporary text file
echo "This is not a PDF" > /tmp/test_invalid.txt

INVALID_RESPONSE=$(curl -s -w "\n%{http_code}" \
    -X POST "$API_URL/api/v1/analyze" \
    -F "file=@/tmp/test_invalid.txt")

HTTP_CODE=$(echo "$INVALID_RESPONSE" | tail -n1)
RESPONSE_BODY=$(echo "$INVALID_RESPONSE" | sed '$d')

if [ "$HTTP_CODE" -eq 400 ]; then
    print_success "Correctly rejected invalid file type (HTTP $HTTP_CODE)"
    if [ "$HAS_JQ" = true ]; then
        echo "$RESPONSE_BODY" | jq '.'
    else
        echo "$RESPONSE_BODY"
    fi
else
    print_error "Expected HTTP 400, got HTTP $HTTP_CODE"
fi

# Cleanup
rm -f /tmp/test_invalid.txt

# ============================================================================
# Test 8: Container Logs
# ============================================================================
print_header "Test 8: Container Logs"

print_info "Checking recent container logs..."
docker logs --tail 20 docling-api 2>&1 | head -20

# ============================================================================
# Summary
# ============================================================================
print_header "Test Summary"

print_success "All basic tests completed!"
echo ""
print_info "Container Status:"
docker ps --filter name=docling-api --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"

echo ""
print_info "Next steps:"
echo "  1. View API docs: $API_URL/docs"
echo "  2. Check logs: docker-compose logs -f api"
echo "  3. Test with your own PDF: curl -X POST $API_URL/api/v1/analyze -F 'file=@your.pdf'"
echo "  4. Stop container: docker-compose down"
echo ""
