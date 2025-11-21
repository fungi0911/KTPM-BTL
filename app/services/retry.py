import time

def retry_call(func, attempts=3, backoff=0.3, multiplier=2.0, exceptions=(Exception,)):
    last_err = None
    delay = float(backoff)
    for i in range(int(attempts)):
        try:
            return func()
        except exceptions as e:
            last_err = e
            if i == attempts - 1:
                break
            time.sleep(delay)
            delay *= multiplier
    raise last_err