"""
Garden World Scheduler
Runs daily world advancement and Mira's autonomous routine.
Single-player only — no multi-player mode.
"""

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from day_cron import advance_world_day
from mira_system import mira_daily_routine
import atexit

_llm_fn = None
_narrator_fn = None
_photo_fn = None
_parse_tags_fn = None


def run_daily():
    """
    Runs at midnight (or when manually triggered):
    1. Advance the world day (plants grow, health degrades)
    2. Mira takes her autonomous daily routine
    """
    print("\n⏰ === DAILY CYCLE TRIGGERED ===")

    advance_world_day()

    print("\n🤖 Running Mira's daily autonomous routine")
    if _llm_fn and _narrator_fn:
        mira_daily_routine(
            llm_fn=_llm_fn,
            narrator_fn=_narrator_fn,
            photo_fn=_photo_fn,
            parse_tags_fn=_parse_tags_fn
        )
    else:
        print("⚠️  LLM or narrator function not set — skipping Mira's routine")

    print("✅ Daily cycle complete\n")


def init_scheduler(app, llm_fn, narrator_fn, photo_fn=None, parse_tags_fn=None):
    global _llm_fn, _narrator_fn, _photo_fn, _parse_tags_fn
    _llm_fn = llm_fn
    _narrator_fn = narrator_fn
    _photo_fn = photo_fn
    _parse_tags_fn = parse_tags_fn

    scheduler = BackgroundScheduler()
    scheduler.add_job(
        func=run_daily,
        trigger=CronTrigger(hour=20, minute=10),
        id='daily_advancement',
        name='Advance world + Mira daily routine',
        replace_existing=True
    )
    scheduler.start()
    atexit.register(lambda: scheduler.shutdown())
    app.logger.info("✅ Scheduler initialized — daily cycle runs at 20:10")
    return scheduler


def manual_advance():
    """Manually trigger a daily cycle (for testing / UI button)."""
    print("\n🔧 Manual day advancement triggered")
    result = advance_world_day()
    if _llm_fn and _narrator_fn:
        print("\n🤖 Running Mira's daily routine")
        mira_daily_routine(llm_fn=_llm_fn, narrator_fn=_narrator_fn,
                           photo_fn=_photo_fn, parse_tags_fn=_parse_tags_fn)
    return result
