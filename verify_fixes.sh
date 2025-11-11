#!/bin/bash
# Quick verification script to confirm all cookie parser fixes are in place

echo "🔍 Verifying Cookie Parser Fixes..."
echo "========================================"
echo ""

# Check current branch
echo "1. Checking git branch..."
BRANCH=$(git branch --show-current)
echo "   Current branch: $BRANCH"
if [[ "$BRANCH" == *"claude/auto-cookie-parsing-extraction"* ]]; then
    echo "   ✅ On correct branch"
else
    echo "   ⚠️  Not on fix branch. Expected: claude/auto-cookie-parsing-extraction-011CV2rG2wPXKSpTUQwTWiZA"
fi
echo ""

# Check latest commit
echo "2. Checking latest commit..."
COMMIT=$(git log --oneline -1)
echo "   $COMMIT"
if [[ "$COMMIT" == *"Robust cookie parsing"* ]] || [[ "$COMMIT" == *"9dfd35b"* ]]; then
    echo "   ✅ Latest fix commit present"
else
    echo "   ⚠️  Latest commit doesn't match. Run: git pull origin claude/auto-cookie-parsing-extraction-011CV2rG2wPXKSpTUQwTWiZA"
fi
echo ""

# Check parser uses regex split
echo "3. Checking cookie parser (regex split)..."
if grep -q "re.split(r'\\\t+\|\\\s{2,}', line)" handlers/cookie_manager.py; then
    echo "   ✅ Flexible delimiter parsing (tabs & spaces) - ACTIVE"
else
    echo "   ❌ Old parser still in use! Code needs update."
fi
echo ""

# Check parser supports 6+ fields
echo "4. Checking field count support..."
if grep -q "if len(parts) >= 6:" handlers/cookie_manager.py; then
    echo "   ✅ Variable field support (6-8 fields) - ACTIVE"
else
    echo "   ❌ Old strict 7-field requirement still in use!"
fi
echo ""

# Check re module import
echo "5. Checking regex module import..."
if grep -q "^import re" handlers/cookie_manager.py; then
    echo "   ✅ 're' module imported"
else
    echo "   ❌ 're' module not imported! Parser will fail."
fi
echo ""

# Check UI reset messages
echo "6. Checking UI state reset handlers..."
RESET_COUNT=$(grep -c "تم إعادة تعيين الحالة" handlers/admin.py)
echo "   Found $RESET_COUNT UI reset messages"
if [ "$RESET_COUNT" -ge 4 ]; then
    echo "   ✅ All 4 error handlers have UI reset"
else
    echo "   ⚠️  Expected 4 reset messages, found $RESET_COUNT"
fi
echo ""

# Check navigation buttons
echo "7. Checking navigation buttons..."
BUTTON_COUNT=$(grep -c "العودة للمنصات" handlers/admin.py)
echo "   Found $BUTTON_COUNT 'Back to Platforms' buttons"
if [ "$BUTTON_COUNT" -ge 8 ]; then
    echo "   ✅ Navigation buttons present"
else
    echo "   ⚠️  Some navigation buttons may be missing"
fi
echo ""

# Check HttpOnly handling
echo "8. Checking #HttpOnly_ prefix handling..."
if grep -q "if line.startswith('#HttpOnly_'):" handlers/cookie_manager.py; then
    echo "   ✅ HttpOnly prefix detection - ACTIVE"
else
    echo "   ❌ HttpOnly prefix handling missing!"
fi
echo ""

# Summary
echo "========================================"
echo "📊 VERIFICATION SUMMARY"
echo "========================================"

CHECKS_PASSED=0
CHECKS_TOTAL=8

# Run checks
grep -q "re.split(r'\\\t+\|\\\s{2,}', line)" handlers/cookie_manager.py && ((CHECKS_PASSED++))
grep -q "if len(parts) >= 6:" handlers/cookie_manager.py && ((CHECKS_PASSED++))
grep -q "^import re" handlers/cookie_manager.py && ((CHECKS_PASSED++))
[ "$RESET_COUNT" -ge 4 ] && ((CHECKS_PASSED++))
[ "$BUTTON_COUNT" -ge 8 ] && ((CHECKS_PASSED++))
grep -q "if line.startswith('#HttpOnly_'):" handlers/cookie_manager.py && ((CHECKS_PASSED++))
[[ "$BRANCH" == *"claude/auto-cookie-parsing-extraction"* ]] && ((CHECKS_PASSED++))
[[ "$COMMIT" == *"Robust cookie parsing"* ]] || [[ "$COMMIT" == *"9dfd35b"* ]] && ((CHECKS_PASSED++))

echo ""
echo "Checks passed: $CHECKS_PASSED / $CHECKS_TOTAL"
echo ""

if [ "$CHECKS_PASSED" -eq "$CHECKS_TOTAL" ]; then
    echo "✅ ALL FIXES VERIFIED - Ready for production!"
    echo ""
    echo "🚀 Next steps:"
    echo "   1. Restart your bot: sudo systemctl restart telegram-bot"
    echo "   2. Test with Safari cookie sample"
    echo "   3. Verify admin buttons work after errors"
elif [ "$CHECKS_PASSED" -ge 6 ]; then
    echo "⚠️  MOSTLY READY - Minor issues detected"
    echo ""
    echo "🔧 Recommended action:"
    echo "   - Review warnings above"
    echo "   - Restart bot anyway and test"
else
    echo "❌ FIXES NOT PROPERLY APPLIED"
    echo ""
    echo "🔧 Required action:"
    echo "   1. Pull latest code: git pull origin claude/auto-cookie-parsing-extraction-011CV2rG2wPXKSpTUQwTWiZA"
    echo "   2. Run this script again"
    echo "   3. If still failing, check DEPLOYMENT_GUIDE.md"
fi

echo ""
echo "========================================"
