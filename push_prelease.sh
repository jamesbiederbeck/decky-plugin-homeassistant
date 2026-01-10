#!/bin/bash
set -e
git tag -d preview 2>/dev/null || true && git push --delete origin preview && git tag preview && git push origin preview
