"""Background scheduler for automated tasks."""

import asyncio
from datetime import datetime
from typing import Optional, Callable, Awaitable
import pytz


class BackgroundScheduler:
    """Simple async scheduler for background tasks."""

    def __init__(self):
        self.tasks: dict[str, asyncio.Task] = {}
        self.running = False
        self._price_update_callback: Optional[Callable[[], Awaitable]] = None
        self._alert_check_callback: Optional[Callable[[], Awaitable]] = None
        self._broadcast_callback: Optional[Callable[[dict], Awaitable]] = None

    def set_callbacks(
        self,
        price_update: Optional[Callable[[], Awaitable]] = None,
        alert_check: Optional[Callable[[], Awaitable]] = None,
        broadcast: Optional[Callable[[dict], Awaitable]] = None
    ):
        """Set callback functions for scheduled tasks."""
        if price_update:
            self._price_update_callback = price_update
        if alert_check:
            self._alert_check_callback = alert_check
        if broadcast:
            self._broadcast_callback = broadcast

    def is_market_hours(self) -> tuple[bool, str]:
        """Check if US stock market is currently open."""
        try:
            eastern = pytz.timezone('US/Eastern')
            now = datetime.now(eastern)
            weekday = now.weekday()

            if weekday >= 5:
                return False, 'closed'

            hour = now.hour
            minute = now.minute
            current_time = hour * 60 + minute

            pre_market_start = 4 * 60
            market_open = 9 * 60 + 30
            market_close = 16 * 60
            post_market_end = 20 * 60

            if pre_market_start <= current_time < market_open:
                return True, 'pre'
            elif market_open <= current_time < market_close:
                return True, 'regular'
            elif market_close <= current_time < post_market_end:
                return True, 'post'
            else:
                return False, 'closed'
        except Exception:
            return False, 'unknown'

    async def _price_update_loop(self):
        """Background loop for auto price updates during market hours."""
        while self.running:
            try:
                is_open, session = self.is_market_hours()

                if is_open and self._price_update_callback:
                    # Update prices
                    result = await self._price_update_callback()

                    # Broadcast update to WebSocket clients
                    if self._broadcast_callback and result:
                        await self._broadcast_callback({
                            'type': 'price_update',
                            'data': result,
                            'session': session
                        })

                    # Run alert checks after price update
                    if self._alert_check_callback:
                        alerts = await self._alert_check_callback()
                        if alerts and alerts.get('total_created', 0) > 0:
                            if self._broadcast_callback:
                                await self._broadcast_callback({
                                    'type': 'new_notifications',
                                    'count': alerts['total_created']
                                })

                # Sleep interval based on market session
                if session == 'regular':
                    await asyncio.sleep(15 * 60)  # 15 minutes during regular hours
                elif session in ('pre', 'post'):
                    await asyncio.sleep(30 * 60)  # 30 minutes during extended hours
                else:
                    await asyncio.sleep(60 * 60)  # 1 hour when closed

            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"[Scheduler] Price update error: {e}")
                await asyncio.sleep(60)  # Wait 1 minute on error

    async def _alert_check_loop(self):
        """Background loop for periodic alert checks."""
        while self.running:
            try:
                if self._alert_check_callback:
                    alerts = await self._alert_check_callback()
                    if alerts and alerts.get('total_created', 0) > 0:
                        if self._broadcast_callback:
                            await self._broadcast_callback({
                                'type': 'new_notifications',
                                'count': alerts['total_created']
                            })

                # Check alerts every 5 minutes
                await asyncio.sleep(5 * 60)

            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"[Scheduler] Alert check error: {e}")
                await asyncio.sleep(60)

    def start(self):
        """Start background tasks."""
        if self.running:
            return

        self.running = True
        self.tasks['price_update'] = asyncio.create_task(self._price_update_loop())
        self.tasks['alert_check'] = asyncio.create_task(self._alert_check_loop())
        print("[Scheduler] Started background tasks")

    def stop(self):
        """Stop all background tasks."""
        self.running = False
        for name, task in self.tasks.items():
            task.cancel()
        self.tasks.clear()
        print("[Scheduler] Stopped background tasks")


# Global scheduler instance
scheduler = BackgroundScheduler()
