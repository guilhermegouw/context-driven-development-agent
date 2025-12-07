#!/bin/bash

# Colors for output
BLUE='\033[0;34m'
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[0;33m'
NC='\033[0m' # No Color

echo -e "${BLUE}Setting up git hooks...${NC}"

# Check if we're in a git repository
if [ ! -d .git ]; then
    echo -e "${RED}✗ Not a git repository${NC}"
    exit 1
fi

# Check if pre-commit is installed
if ! command -v pre-commit &> /dev/null; then
    echo -e "${BLUE}Installing pre-commit...${NC}"

    # Try to install with poetry if available
    if command -v poetry &> /dev/null; then
        poetry add --group dev pre-commit
    # Otherwise try pip
    elif command -v pip &> /dev/null; then
        pip install pre-commit
    else
        echo -e "${RED}✗ Cannot install pre-commit (no poetry or pip found)${NC}"
        echo -e "${YELLOW}Install manually: pip install pre-commit${NC}"
        exit 1
    fi
    echo -e "${GREEN}✓ pre-commit installed${NC}"
fi

# Install pre-commit hooks (idempotent - safe to run multiple times)
pre-commit install --install-hooks > /dev/null 2>&1

echo -e "${GREEN}✓ Git hooks configured${NC}"
echo ""
echo -e "Pre-commit will run ${BLUE}make qa${NC} before each commit"
echo -e "To skip: ${YELLOW}git commit --no-verify${NC}"
