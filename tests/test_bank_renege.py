"""Test Bank Renege Example

The following is a copy/rewrite of the "Bank Renege" example, by Team SimPy.
The purpose is to test similarities/differences with DeltaCycle.
See SimPy license for copyright details.

Reference:
* https://simpy.readthedocs.io/en/latest/about/license.html
* https://simpy.readthedocs.io/en/latest/examples/bank_renege.html
"""

import random

from deltacycle import AnyOf, Lock, create_task, now, run, sleep

RANDOM_SEED = 42
NEW_CUSTOMERS = 5  # Number of customers
INTERVAL_CUSTOMERS = 10.0  # Generate new customers roughly every x seconds
MIN_PATIENCE = 1.0  # Min customer patience
MAX_PATIENCE = 3.0  # Max customer patience

TIME_IN_BANK = 12.0

TIMESCALE = 1_000_000.0


def tprint(s: str):
    print(f"{now() / TIMESCALE:7.4f} {s}")


async def customer(name: str, counter: Lock):
    """Customer arrives, is served and leaves."""
    arrive = now()
    tprint(f"{name}: Here I am")

    patience = random.uniform(MIN_PATIENCE, MAX_PATIENCE)

    # Wait for the counter or abort at the end of our tether
    timeout = create_task(sleep(round(patience * TIMESCALE)))
    y = await AnyOf(counter.req(), timeout)
    wait = now() - arrive

    if y is counter:
        # We got to the counter
        tprint(f"{name}: Waited {wait / TIMESCALE:<7.3f}")
        t = random.expovariate(1.0 / TIME_IN_BANK)
        await sleep(round(t * TIMESCALE))
        tprint(f"{name}: Finished")
        assert isinstance(y, Lock)
        y.put()
    else:
        # We reneged
        tprint(f"{name}: RENEGED after {wait / TIMESCALE:<7.3f}")


async def main(n: int, interval: float, counter: Lock):
    """Generate customers randomly."""
    for i in range(n):
        c = customer(f"Customer{i:02d}", counter)
        create_task(c)
        t = random.expovariate(1.0 / interval)
        await sleep(round(t * TIMESCALE))


OUTPUT = """\
Bank Renege
 0.0000 Customer00: Here I am
 0.0000 Customer00: Waited 0.000
 3.8595 Customer00: Finished
10.2006 Customer01: Here I am
10.2006 Customer01: Waited 0.000
12.7265 Customer02: Here I am
13.9003 Customer02: RENEGED after 1.174
23.7507 Customer01: Finished
34.9993 Customer03: Here I am
34.9993 Customer03: Waited 0.000
37.9599 Customer03: Finished
40.4798 Customer04: Here I am
40.4798 Customer04: Waited 0.000
43.1401 Customer04: Finished
"""


def test_bank_renege(capsys):
    # Setup and start the simulation
    print("Bank Renege")
    random.seed(RANDOM_SEED)

    # Start processes and run
    counter = Lock()
    run(main(NEW_CUSTOMERS, INTERVAL_CUSTOMERS, counter))
    out, _ = capsys.readouterr()
    out = "\n".join(line.rstrip() for line in out.splitlines()) + "\n"
    assert out == OUTPUT
