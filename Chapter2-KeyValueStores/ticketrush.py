import random
import time
import uuid
from concurrent.futures import ThreadPoolExecutor

import redis

r = redis.Redis(host="localhost", port=6379, decode_responses=True)


def race(fn, n=50):
    with ThreadPoolExecutor(max_workers=n) as pool:
        return list(pool.map(fn, range(n)))


def hold_naive(event, seat, user):
    key = f"hold:{event}:{seat}"
    if r.get(key) is None:
        time.sleep(0.01)
        r.set(key, user, ex=300)
        return True
    return False


def hold_nx(event, seat, user, ttl=300):
    return bool(r.set(f"hold:{event}:{seat}", user, nx=True, ex=ttl))


HOLD = r.register_script("""
if redis.call('SISMEMBER', KEYS[2], ARGV[2]) == 1 then return 0 end
if redis.call('SET', KEYS[1], ARGV[1], 'NX', 'EX', ARGV[3]) then return 1 end
return 0
""")

CONFIRM = r.register_script("""
if redis.call('GET', KEYS[1]) == ARGV[1] then
    redis.call('SADD', KEYS[2], ARGV[2])
    redis.call('DEL', KEYS[1])
    return 1
end
return 0
""")

RELEASE = r.register_script("""
if redis.call('GET', KEYS[1]) == ARGV[1] then
    return redis.call('DEL', KEYS[1])
end
return 0
""")


def hold(event, seat, user, ttl=300):
    return bool(HOLD(
        keys=[f"hold:{event}:{seat}", f"sold:{event}"],
        args=[user, seat, ttl]
    ))


def confirm(event, seat, user):
    return bool(CONFIRM(
        keys=[f"hold:{event}:{seat}", f"sold:{event}"],
        args=[user, seat]
    ))


def release(event, seat, user):
    return bool(RELEASE(keys=[f"hold:{event}:{seat}"], args=[user]))


def seat_map(event, seats):
    sold = r.smembers(f"sold:{event}")
    return {
        seat: "sold" if seat in sold else "held" if r.exists(f"hold:{event}:{seat}") else "free"
        for seat in seats
    }


def buy_general(event, user):
    left = r.decr(f"stock:{event}")
    if left < 0:
        r.incr(f"stock:{event}")
        return False
    r.sadd(f"buyers:{event}", user)
    return True


def allow_fixed(user, limit=5, window=10):
    key = f"rl:fixed:{user}:{int(time.time() // window)}"
    pipe = r.pipeline()
    pipe.incr(key)
    pipe.expire(key, window, nx=True)
    count, _ = pipe.execute()
    return count <= limit


SLIDING = r.register_script("""
local now, window, limit = tonumber(ARGV[1]), tonumber(ARGV[2]), tonumber(ARGV[3])
redis.call('ZREMRANGEBYSCORE', KEYS[1], 0, now - window)
if redis.call('ZCARD', KEYS[1]) < limit then
    redis.call('ZADD', KEYS[1], now, ARGV[4])
    redis.call('PEXPIRE', KEYS[1], window)
    return 1
end
return 0
""")


def allow_sliding(user, limit=5, window_ms=10_000):
    now = int(time.time() * 1000)
    return bool(SLIDING(
        keys=[f"rl:sliding:{user}"],
        args=[now, window_ms, limit, uuid.uuid4().hex]
    ))


def try_hold(event, seat, user):
    if not allow_sliding(user):
        return "rate_limited"
    return "ok" if hold(event, seat, user) else "taken"


def join_queue(event, user):
    r.zadd(f"queue:{event}", {user: time.time()}, nx=True)
    return r.zrank(f"queue:{event}", user) + 1


def admit(event, n):
    return [user for user, _ in r.zpopmin(f"queue:{event}", n)]


if __name__ == "__main__":
    r.ping()

    print("Step 1")
    r.flushdb()
    wins = race(lambda i: hold_naive("c1", "A1", f"user{i}"))
    print("naive winners:", sum(wins))

    r.flushdb()
    wins = race(lambda i: hold_nx("c1", "A1", f"user{i}"))
    print("NX winners:", sum(wins))

    print("Step 2")
    r.flushdb()
    print(hold("c1", "A1", "linh"))
    print(hold("c1", "A1", "nam"))
    print(confirm("c1", "A1", "nam"))
    print(confirm("c1", "A1", "linh"))
    print(hold("c1", "A1", "nam"))
    print(seat_map("c1", ["A1", "A2"]))

    print("Step 3")
    r.flushdb()
    r.set("stock:g1", 100)
    ok = race(lambda i: buy_general("g1", f"user{i}"), n=500)
    print(sum(ok), r.get("stock:g1"), r.scard("buyers:g1"))

    print("Step 4")
    r.flushdb()
    print([allow_fixed("linh") for _ in range(8)])

    time.sleep((10 - time.time() % 10 - 0.2) % 10)
    first = [allow_fixed("bot") for _ in range(5)]
    time.sleep(0.4)
    second = [allow_fixed("bot") for _ in range(5)]
    print("fixed boundary:", first + second)

    time.sleep((10 - time.time() % 10 - 0.2) % 10)
    first = [allow_sliding("bot") for _ in range(5)]
    time.sleep(0.4)
    second = [allow_sliding("bot") for _ in range(5)]
    print("sliding boundary:", first + second)

    print("Step 5")
    r.flushdb()
    for name in ["u1", "u2", "u3"]:
        print(name, join_queue("c1", name))
    print(join_queue("c1", "u1"))
    print(admit("c1", 2))
    print(join_queue("c1", "u3"))

    print("Step 6")
    r.flushdb()
    SEATS = [f"S{i}" for i in range(1, 21)]

    def buyer(i):
        user = f"user{i}"
        for seat in SEATS:
            if hold("c1", seat, user):
                time.sleep(random.random() * 0.05)
                if confirm("c1", seat, user):
                    return seat
        return None

    got = [seat for seat in race(buyer, n=100) if seat]
    print(len(got), len(set(got)), r.scard("sold:c1"))
