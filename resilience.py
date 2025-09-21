import time, functools, threading

class CircuitBreaker:
    def __init__(self, max_failures=5, reset_after=60):
        self.max_failures=max_failures
        self.reset_after=reset_after
        self.failures=0
        self.open_until=0.0
        self.lock=threading.Lock()
    def allow(self):
        with self.lock:
            now=time.time()
            if now < self.open_until: return False
            return True
    def on_success(self):
        with self.lock:
            self.failures=0; self.open_until=0.0
    def on_failure(self):
        with self.lock:
            self.failures+=1
            if self.failures>=self.max_failures:
                self.open_until=time.time()+self.reset_after
                self.failures=0
def retry(fn=None, tries=3, delay=0.5, backoff=2.0):
    if fn is None:
        return lambda f: retry(f, tries=tries, delay=delay, backoff=backoff)
    @functools.wraps(fn)
    def wrapper(*a, **k):
        _tries=tries; _delay=delay
        while _tries>0:
            try:
                return fn(*a, **k)
            except Exception as e:
                _tries-=1
                if _tries<=0: raise
                time.sleep(_delay); _delay*=backoff
    return wrapper
