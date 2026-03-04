#!/bin/bash
# UFC Scrape Progress Checker
# Usage: ./check_ufc_progress.sh

echo "=========================================="
echo "📊 UFC COMPREHENSIVE SCRAPE PROGRESS"
echo "=========================================="
echo ""

# Check if process is running
PID=$(pgrep -f "comprehensive_scrape.py" | head -1)
if [ -n "$PID" ]; then
    echo "✅ Process RUNNING (PID: $PID)"
    echo "⏱️  Runtime: $(ps -o etime= -p $PID 2>/dev/null || echo 'N/A')"
else
    echo "⚠️  Process NOT RUNNING"
fi
echo ""

# Check database stats
echo "📁 Database Stats:"
sqlite3 ~/.openclaw/workspace/theaibet-sports-build/data/ufc.db << 'EOF' 2>/dev/null | column -t -s'|'
SELECT 'Metric' as metric, 'Count' as count
UNION ALL
SELECT '----------------', '--------'
UNION ALL
SELECT 'Total Fighters', COUNT(*) FROM fighters
UNION ALL
SELECT 'Fighters w/ Stats', COUNT(*) FROM fighters WHERE slpm IS NOT NULL
UNION ALL
SELECT 'Events', COUNT(*) FROM events
UNION ALL
SELECT 'Fights', COUNT(*) FROM fights
UNION ALL
SELECT 'Fight Stats', COUNT(*) FROM fight_stats
UNION ALL
SELECT 'Odds', COUNT(*) FROM odds;
EOF

echo ""
echo "📜 Recent Log Activity:"
echo "----------------------"

LOG_FILE=~/.openclaw/workspace/theaibet-sports-build/comprehensive_live.log
if [ -f "$LOG_FILE" ]; then
    # Show last milestone or progress
    tail -20 "$LOG_FILE" 2>/dev/null | grep -E "(MILESTONE|PROGRESS|Progress:|Phase|COMPLETE)" | tail -5
    echo ""
    echo "📝 Full log: $LOG_FILE"
else
    echo "No log file found yet"
fi

echo ""
echo "=========================================="
