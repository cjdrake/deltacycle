"""Test dining philosophers."""

import random
from enum import Enum, auto

from pytest import CaptureFixture

from deltacycle import Lock, create_task, now, run, sleep

# Number of philosophers
N = 5


# Philosopher state
class State(Enum):
    INITIAL = auto()
    THINKING = auto()
    HUNGRY = auto()
    EATING = auto()


# Eat [min, max] time
EAT_TICKS = (50, 100)

# Think [min, max] time
THINK_TICKS = (50, 100)

# Simulation time
T = 1000


# Optional mask to filter print output
# If pmask & (1<<i), print philosopher state updates.
_pmask = (1 << N) - 1


# Philosophers and Forks
state = [State.INITIAL for _ in range(N)]
forks = [Lock() for _ in range(N)]


def init(pmask: int = (1 << N) - 1):
    """Initialize all philosophers and forks."""
    global _pmask, state, forks
    _pmask = pmask
    state = [State.INITIAL for _ in range(N)]
    forks = [Lock() for _ in range(N)]


def _update(i: int, ns: State):
    """Update philosopher[i] state."""
    if _pmask & (1 << i):
        print(f"[{now():08}] P{i} {state[i].name:8} => {ns.name:8}")
    state[i] = ns


async def think(i: int):
    """Philosopher[i] thinks for a random amount of time."""
    _update(i, State.THINKING)
    await sleep(random.randint(*THINK_TICKS))


async def pick_up_forks(i: int):
    """Philosopher[i] is hungry. Pick up left/right forks."""
    _update(i, State.HUNGRY)

    # Wait on forks in (left, right) order
    first, second = i, (i + 1) % N

    while True:
        # Wait until first fork is available
        await forks[first].get()

        # If second fork is available, get it.
        if forks[second].try_get():
            break

        # Second fork is NOT available:
        # 1. Release the first fork
        forks[first].put()
        # 2. Swap which fork we're waiting on first
        first, second = second, first


async def eat(i: int):
    """Philosopher[i] eats for a random amount of time."""
    _update(i, State.EATING)
    await sleep(random.randint(*EAT_TICKS))


def put_down_forks(i: int):
    """Philosopher[i] is not hungry. Put down left/right forks."""
    first, second = i, (i + 1) % N
    forks[first].put()
    forks[second].put()


async def philosopher(i: int):
    while True:
        await think(i)
        await pick_up_forks(i)
        await eat(i)
        put_down_forks(i)


async def main():
    for i in range(N):
        create_task(philosopher(i))


OUTPUT = """\
[00000000] P0 INITIAL  => THINKING
[00000000] P1 INITIAL  => THINKING
[00000000] P2 INITIAL  => THINKING
[00000000] P3 INITIAL  => THINKING
[00000000] P4 INITIAL  => THINKING
[00000051] P2 THINKING => HUNGRY
[00000051] P2 HUNGRY   => EATING
[00000057] P1 THINKING => HUNGRY
[00000067] P4 THINKING => HUNGRY
[00000067] P4 HUNGRY   => EATING
[00000090] P0 THINKING => HUNGRY
[00000097] P3 THINKING => HUNGRY
[00000116] P2 EATING   => THINKING
[00000116] P1 HUNGRY   => EATING
[00000131] P4 EATING   => THINKING
[00000131] P3 HUNGRY   => EATING
[00000174] P2 THINKING => HUNGRY
[00000187] P4 THINKING => HUNGRY
[00000213] P1 EATING   => THINKING
[00000213] P0 HUNGRY   => EATING
[00000224] P3 EATING   => THINKING
[00000224] P2 HUNGRY   => EATING
[00000279] P3 THINKING => HUNGRY
[00000297] P0 EATING   => THINKING
[00000297] P4 HUNGRY   => EATING
[00000310] P1 THINKING => HUNGRY
[00000311] P2 EATING   => THINKING
[00000311] P1 HUNGRY   => EATING
[00000349] P4 EATING   => THINKING
[00000349] P3 HUNGRY   => EATING
[00000362] P2 THINKING => HUNGRY
[00000366] P1 EATING   => THINKING
[00000374] P0 THINKING => HUNGRY
[00000374] P0 HUNGRY   => EATING
[00000412] P4 THINKING => HUNGRY
[00000413] P3 EATING   => THINKING
[00000413] P2 HUNGRY   => EATING
[00000448] P1 THINKING => HUNGRY
[00000462] P0 EATING   => THINKING
[00000462] P4 HUNGRY   => EATING
[00000464] P3 THINKING => HUNGRY
[00000498] P2 EATING   => THINKING
[00000498] P1 HUNGRY   => EATING
[00000524] P0 THINKING => HUNGRY
[00000557] P4 EATING   => THINKING
[00000557] P3 HUNGRY   => EATING
[00000589] P2 THINKING => HUNGRY
[00000592] P1 EATING   => THINKING
[00000592] P0 HUNGRY   => EATING
[00000633] P3 EATING   => THINKING
[00000633] P2 HUNGRY   => EATING
[00000641] P4 THINKING => HUNGRY
[00000656] P1 THINKING => HUNGRY
[00000670] P0 EATING   => THINKING
[00000670] P4 HUNGRY   => EATING
[00000700] P2 EATING   => THINKING
[00000700] P1 HUNGRY   => EATING
[00000720] P3 THINKING => HUNGRY
[00000720] P0 THINKING => HUNGRY
[00000760] P2 THINKING => HUNGRY
[00000768] P4 EATING   => THINKING
[00000768] P3 HUNGRY   => EATING
[00000794] P1 EATING   => THINKING
[00000794] P0 HUNGRY   => EATING
[00000839] P3 EATING   => THINKING
[00000839] P2 HUNGRY   => EATING
[00000845] P4 THINKING => HUNGRY
[00000853] P0 EATING   => THINKING
[00000853] P4 HUNGRY   => EATING
[00000861] P1 THINKING => HUNGRY
[00000902] P3 THINKING => HUNGRY
[00000909] P4 EATING   => THINKING
[00000924] P0 THINKING => HUNGRY
[00000924] P0 HUNGRY   => EATING
[00000937] P2 EATING   => THINKING
[00000937] P3 HUNGRY   => EATING
[00000964] P4 THINKING => HUNGRY
[00000993] P2 THINKING => HUNGRY
[00000998] P0 EATING   => THINKING
[00000998] P1 HUNGRY   => EATING
"""


def test_dp(capsys: CaptureFixture[str]):
    """This is a random algorithm, so we're only doing some basic checks."""
    random.seed(42)
    init()
    run(main(), until=T)
    out, _ = capsys.readouterr()
    out = "\n".join(line.rstrip() for line in out.splitlines()) + "\n"
    assert out == OUTPUT
