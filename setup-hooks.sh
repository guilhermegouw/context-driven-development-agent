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

# Check if pre-commit is installed (via Poetry or system)
if command -v poetry &> /dev/null && poetry run pre-commit --version &> /dev/null; then
    PRE_COMMIT="poetry run pre-commit"
elif command -v pre-commit &> /dev/null; then
    PRE_COMMIT="pre-commit"
else
    echo -e "${BLUE}Installing pre-commit...${NC}"
    if command -v poetry &> /dev/null; then
        poetry add --group dev pre-commit
        PRE_COMMIT="poetry run pre-commit"
    elif command -v pip &> /dev/null; then
        pip install pre-commit
        PRE_COMMIT="pre-commit"
    else
        echo -e "${RED}✗ Cannot install pre-commit (no poetry or pip found)${NC}"
        echo -e "${YELLOW}Install manually: pip install pre-commit${NC}"
        exit 1
    fi
    echo -e "${GREEN}✓ pre-commit installed${NC}"
fi

# Install pre-commit hooks (idempotent - safe to run multiple times)
OUTPUT=$($PRE_COMMIT install --install-hooks 2>&1)
if [ $? -ne 0 ]; then
    echo -e "${RED}✗ Failed to install pre-commit hooks${NC}"
    echo "$OUTPUT"
    exit 1
fi

echo -e "${GREEN}✓ Git hooks configured${NC}"
echo ""
echo -e "Pre-commit will run ${BLUE}make qa${NC} before each commit"
echo -e "To skip: ${YELLOW}git commit --no-verify${NC}"
# test change
