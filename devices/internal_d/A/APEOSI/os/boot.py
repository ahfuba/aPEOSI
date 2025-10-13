from core.io_manager import IOManager
from kernel.scheduler import Ticker
from core import global_vars as g
import threading

io = IOManager()
ticker = Ticker(io)
ticker.start()  # ticker kendi thread’inde çalışıyor

def terminal_loop():
    while not g.terminate:
        user_input = io.input()  # input() main thread’de bloklayacak
        if g.terminate:
            break

# terminal loop’u kendi thread’inde çalıştırabilirsin de
terminal_thread = threading.Thread(target=terminal_loop)
terminal_thread.start()

terminal_thread.join()
ticker.stop()
