#!/bin/sh
# Copy the public CV from the private Resumes folder into the site.
# Usage: ./sync-cv.sh [resume_name]   (default: resume_ai_research)
set -e
name="${1:-resume_ai_research}"
src="$(dirname "$0")/../Resumes/$name.pdf"
cp "$src" "$(dirname "$0")/cv.pdf" && echo "cv.pdf <- $src"
