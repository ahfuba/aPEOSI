"""
scheduler.py
-------------
aPEOSI System Scheduler / Clock Interrupt Simulator

Generates ticks at fixed intervals, updating global simulation time.
"""

import threading
import time
from core import global_vars as g


class Ticker(threading.Thread):
    """
    Core system ticker.
    Emits ticks at fixed intervals, updating global simulation time.
    """

    def __init__(self, io_manager):
        super().__init__()
        self.daemon = True             # Program kapanınca thread otomatik sonlansın
        self.io = io_manager           # IOManager referansı
        self.tick = 0                  # İç sayaç
        self.running = False           # Thread aktif mi?

    def run(self):
        """Thread başlatıldığında çalışan ana döngü"""
        self.running = True
        self.io.output("[TICKER] Ticker started.")

        while self.running and not g.terminate:
            # Mevcut global tick değerini hesapla
            g.current_tick = self.tick + g.current_tick

            # Sayaç artışı
            self.tick += 1

            # CPU'yu yormamak için bekle
            time.sleep(g.tick_precision)

        self.io.output("[TICKER] Ticker stopped.")

    def stop(self):
        """Ticker'ı güvenli biçimde durdurur."""
        self.running = False
