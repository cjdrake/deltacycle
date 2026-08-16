"""Task: coroutine wrapper"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections import Counter
from collections.abc import Coroutine, Generator
from enum import IntEnum
from types import TracebackType
from typing import Any, ClassVar, Iterator, Literal, Self, cast

from ._kernel_if import KernelIf

type TaskCoro[ResultType] = Coroutine[None, Blocking | None, ResultType]

type TaskArgs = (
    tuple[Literal[Task.Command.START]]
    | tuple[Literal[Task.Command.RESUME]]
    | tuple[Literal[Task.Command.RESUME], Blocking]
    | tuple[Literal[Task.Command.SIGNAL], BaseException]
)


class Interrupt(Exception):
    """Interrupt task."""


class Kill(BaseException):
    """Kill task."""


class SupportsDropTask(ABC):
    @abstractmethod
    def drop(self, task: Task[Any]) -> None:
        """Drop task from object's waiting queue."""


class Blocking(ABC):
    """Object capable of blocking task forward progress"""

    @abstractmethod
    def try_block(self, task: Task[Any]) -> bool:
        """Attempt to block task; return True if successful."""

    @abstractmethod
    def unblock(self, task: Task[Any]) -> None:
        """Unblock task."""


class _SuspendResume:
    """Suspend/Resume current task.

    Use case:
    1. Current task A suspends itself: RUNNING => WAITING
    2. Kernel chooses PENDING tasks ..., T
    3. ... Task T wakes up task A with value X: WAITING => PENDING
    4. Kernel chooses PENDING tasks ..., A: PENDING => RUNNING
    5. Task A resumes with value X

    The value X can be used to pass information to the task.
    """

    def __await__(self) -> Generator[None, Blocking | None, Blocking | None]:
        # Suspend
        value = yield
        # Resume
        return value


class _Condition(KernelIf):
    def __init__(self, fst: Blocking, *rst: Blocking):
        args = (fst, *rst)
        # Uniquify arguments
        self._bs = list(dict.fromkeys(args))


class AllOf(_Condition):
    def __await__(self) -> Generator[None, Blocking, None]:
        task = self._kernel.check_task()

        while True:
            blocking: list[Blocking] = []
            nonblocking: list[Blocking] = []

            for b in self._bs:
                if b.try_block(task):
                    blocking.append(b)
                else:
                    nonblocking.append(b)

            if not blocking:
                break

            self._kernel._forks.set(task, *blocking)
            yield from task.switch_gen()


class AnyOf(_Condition):
    def __await__(self) -> Generator[None, Blocking, Blocking]:
        task = self._kernel.check_task()

        blocking: list[Blocking] = []

        for b in self._bs:
            if b.try_block(task):
                blocking.append(b)
            else:
                while blocking:
                    x = blocking.pop()
                    x.unblock(task)
                return b

        self._kernel._forks.set(task, *blocking)
        x = yield from task.switch_gen()
        return x


class _WaitQ(SupportsDropTask):
    """Tasks wait for event trigger."""

    def __init__(self):
        self._items: dict[Task[Any], tuple[Task[Any] | None, Task[Any] | None]] = {}

    def drop(self, task: Task[Any]):
        del self._items[task]
        task._unlink(tq=self)

    def push(self, task: Task[Any], join: Task[Any] | None, send: Task[Any] | None):
        task._link(tq=self)
        self._items[task] = (join, send)

    def pop(self) -> Iterator[tuple[Task[Any], Task[Any] | None, Task[Any] | None]]:
        items = list(self._items.items())
        for task, (join, send) in items:
            self.drop(task)
            yield task, join, send


class Task[ResultType](KernelIf, Blocking):
    """Manage the life cycle of a coroutine.

    Do NOT instantiate a Task directly.
    Use ``create_task`` function, or (better) ``TaskGroup.create_task`` method.
    """

    class Command(IntEnum):
        START = 0b00
        RESUME = 0b01
        SIGNAL = 0b10

    class State(IntEnum):
        """
        Transitions::

                    PENDING
                       |
            INIT -> RUNNING -> RETURNED
                            -> EXCEPTED
        """

        # Initialized
        INIT = 0b001

        # Currently running
        RUNNING = 0b010

        # Suspended
        PENDING = 0b011

        # Done: returned a result
        RETURNED = 0b100
        # Done: raised an exception
        EXCEPTED = 0b101

    _done = State.RETURNED & State.EXCEPTED

    _state_transitions: ClassVar = {
        State.INIT: {
            State.RUNNING,
        },
        State.RUNNING: {
            State.PENDING,
            State.RETURNED,
            State.EXCEPTED,
        },
        State.PENDING: {
            State.RUNNING,
        },
    }

    def __init__(
        self,
        coro: TaskCoro[ResultType],
        index: int,
        name: str,
    ):
        self._state = self.State.INIT

        # Attributes
        self._coro = coro
        self._index = index
        self._name = name

        # Set if created within a group
        self._group: TaskGroup | None = None

        # Keep track of all queues containing this task
        self._refcnts: Counter[SupportsDropTask] = Counter()

        # Other tasks waiting for this task to complete
        self._waitq = _WaitQ()

        # Flag to avoid multiple signals
        self._signal = False

        # Outputs
        self._result: ResultType | None = None
        self._exception: BaseException | None = None

        self._result_returned = False
        self._exception_raised = False

    @property
    def coro(self) -> TaskCoro[ResultType]:
        """Wrapped coroutine."""
        return self._coro

    @property
    def index(self) -> int:
        return self._index

    @property
    def name(self) -> str:
        """Task name.

        Primarily for debug; no functional effect.
        There are no rules or restrictions for valid names.
        Give tasks unique and recognizable names to help identify them.

        If not provided to the create_task function,
        a default name of ``Task-{index}`` will be assigned,
        where ``index`` is a monotonically increasing integer value,
        starting from 0.
        """
        return self._name

    def _get_group(self) -> TaskGroup | None:
        """Return TaskGroup, or None.

        If the task was started by a TaskGroup's create_task method,
        it will assign this property to point to the TaskGroup instance.
        """
        return self._group

    def _set_group(self, group: TaskGroup):
        self._group = group

    group = property(fget=_get_group, fset=_set_group)

    def _set_state(self, state: State):
        assert state in self._state_transitions[self._state]
        self._state = state

    def state(self) -> State:
        return self._state

    def _link(self, tq: SupportsDropTask):
        assert self._refcnts[tq] >= 0
        self._refcnts[tq] += 1

    def _unlink(self, tq: SupportsDropTask):
        assert self._refcnts[tq] > 0
        self._refcnts[tq] -= 1
        if not self._refcnts[tq]:
            del self._refcnts[tq]

    def _renege(self):
        tqs = set(self._refcnts.keys())
        while tqs:
            tq = tqs.pop()
            while self._refcnts[tq]:
                tq.drop(task=self)
            del self._refcnts[tq]

    async def switch_coro(self) -> Blocking | None:
        self._set_state(Task.State.PENDING)

        # Suspend
        value = await _SuspendResume()

        # Resume
        return value

    def switch_gen(self) -> Generator[None, Blocking, Blocking]:
        self._set_state(self.State.PENDING)

        # Suspend
        value = yield

        # Resume
        return value

    def do_run(self, args: TaskArgs):
        self._set_state(self.State.RUNNING)

        match args:
            case (self.Command.START,):
                self._coro.send(None)
            case (self.Command.RESUME,):
                self._coro.send(None)
            case (self.Command.RESUME, Blocking() as x):
                self._coro.send(x)
            case (self.Command.SIGNAL, BaseException() as x):
                self._signal = False
                self._coro.throw(x)
            case _:  # pragma: no cover
                raise TypeError(f"Invalid task command: {args}")

    def _set(self):
        for task, join, send in self._waitq.pop():
            if join is not None:
                self._kernel._forks.clr(task, join)
            if send is not None:
                self._kernel.call_soon(task, args=(self.Command.RESUME, send))
            else:
                self._kernel.call_soon(task, args=(self.Command.RESUME,))

    def do_result(self, exc: StopIteration):
        self._result = exc.value
        self._set_state(self.State.RETURNED)
        self._set()
        assert self._refcnts.total() == 0

    def do_except(self, exc: BaseException):
        self._exception = exc
        self._set_state(self.State.EXCEPTED)
        self._set()
        assert self._refcnts.total() == 0

    def done(self) -> bool:
        """Return True if the task is done.

        A task that is "done" either:

        * Completed normally, or
        * Raised an exception.
        """
        return bool(self._state & self._done)

    def result(self) -> ResultType:
        """Return the task's result, or raise an exception.

        Returns:
            If the task ran to completion, return its result.

        Raises:
            Exception: If the task raise any other type of exception.
            RuntimeError: If the task is not done.
        """
        if self._state is self.State.RETURNED:
            assert self._exception is None
            self._result_returned = True
            return cast(ResultType, self._result)
        if self._state is self.State.EXCEPTED:
            assert self._result is None and self._exception is not None
            self._exception_raised = True
            raise self._exception
        raise RuntimeError("Task is not done")

    def exception(self) -> BaseException | None:
        """Return the task's exception.

        Returns:
            If the task raised an exception, return it.
            Otherwise, return None.

        Raises:
            RuntimeError: If the task is not done.
        """
        if self._state is self.State.RETURNED:
            assert self._exception is None
            return self._exception
        if self._state is self.State.EXCEPTED:
            assert self._result is None and self._exception is not None
            return self._exception
        raise RuntimeError("Task is not done")

    def interrupt(self, *args: Any) -> bool:
        """Interrupt task.

        If a task is already done: return False.

        If a task is pending:

        1. Renege from all queues
        2. Reschedule to raise Interrupt in the current time slot
        3. Return True

        If a task is running, immediately raise Interrupt.

        Args:
            args: Arguments passed to Interrupt instance

        Returns:
            bool success indicator

        Raises:
            Interrupt: If the task interrupts itself
        """
        # Already done; do nothing
        if self._signal or self.done():
            return False

        irq = Interrupt(*args)

        # Task is interrupting itself. Weird, but legal.
        if self is self._kernel.task():
            raise irq

        # Pending tasks must first renege from queues
        self._renege()

        # Reschedule
        self._signal = True
        self._kernel.call_soon(self, args=(self.Command.SIGNAL, irq))

        # Success
        return True

    def _kill(self) -> bool:
        # Already done; do nothing
        if self._signal or self.done():
            return False

        # Task cannot kill itself
        assert self is not self._kernel.task()

        # Pending tasks must first renege from queues
        self._renege()

        # Reschedule
        self._signal = True
        self._kernel.call_soon(self, args=(self.Command.SIGNAL, Kill()))

        # Success
        return True

    def _blocking(self) -> bool:
        return not self.done()

    def __await__(self) -> Generator[None, Self, ResultType]:
        """Await task done."""
        if self._blocking():
            task = self._kernel.check_task()
            self._waitq.push(task, join=None, send=None)
            y = yield from task.switch_gen()
            assert y is None

        # NOTE: This propagates exceptions to parent task
        return self.result()

    # Blocking
    def try_block(self, task: Task[Any]) -> bool:
        if self._blocking():
            self._waitq.push(task, join=self, send=self)
            return True
        return False

    def unblock(self, task: Task[Any]):
        self._waitq.drop(task)


class TaskGroup(KernelIf):
    """Group of tasks."""

    class State(IntEnum):
        INIT = 0
        ENTERED = 2
        EXITED = 3
        EXCEPTED = 4
        RETURNED = 5

    def __init__(self):
        self._state = self.State.INIT

        task = self._kernel.check_task()
        self._parent = task

        # Tasks started in the with block
        self._setup_tasks: set[Task[Any]] = set()

        # Tasks in running/pending/killing state
        self._todo: set[Task[Any]] = set()

    async def _quiesce(self):
        for child in self._todo:
            child._kill()
        while self._todo:
            child = cast(typ=Task[Any], val=(await self._parent.switch_coro()))
            self._todo.remove(child)

    async def __aenter__(self) -> Self:
        self._state = self.State.ENTERED
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ):
        self._state = self.State.EXITED

        done: set[Task[Any]] = set()

        while self._setup_tasks:
            child = self._setup_tasks.pop()
            if child.done():
                done.add(child)
            else:
                child._waitq.push(self._parent, join=None, send=child)
                self._todo.add(child)

        # Parent raised an exception:
        if exc is not None:
            # Ignore DONE children; Kill NOT DONE children; suppress exceptions
            await self._quiesce()
            # Re-raise parent exception
            self._state = self.State.EXCEPTED
            return False

        # Parent did NOT raise an exception:
        child_excs: list[BaseException] = []

        # Search DONE children for exceptions
        while done:
            child = done.pop()
            exc = child.exception()
            # NOTE: If child exception was raised, parent already handled it.
            if exc is not None and not child._exception_raised:
                child_excs.append(exc)

        # DONE children raised exceptions
        if child_excs:
            # Kill NOT DONE children; suppress exceptions
            await self._quiesce()
            # Re-raise child exceptions
            self._state = self.State.EXCEPTED
            raise BaseExceptionGroup("Child task(s) raised exception(s)", child_excs)

        # DONE children did NOT raise any exceptions:

        # Await NOT DONE / NEW children; collect exceptions
        killed: set[Task[Any]] = set()
        while self._todo:
            child = cast(typ=Task[Any], val=(await self._parent.switch_coro()))
            self._todo.remove(child)
            if child in killed:
                continue
            exc = child.exception()
            if exc is not None:
                child_excs.append(exc)
                killed.update(c for c in self._todo if c._kill())

        # Re-raise child exceptions
        if child_excs:
            self._state = self.State.EXCEPTED
            raise BaseExceptionGroup("Child task(s) raised exception(s)", child_excs)

        self._state = self.State.RETURNED
        return

    def create_task[ResultType](
        self,
        coro: TaskCoro[ResultType],
        name: str | None = None,
        **kwargs: Any,
    ) -> Task[ResultType]:
        if self._state is self.State.ENTERED:
            child: Task[ResultType] = self._kernel.create_task(coro, name, **kwargs)
            child.group = self
            self._setup_tasks.add(child)
            return child

        if self._state is self.State.EXITED:
            child: Task[ResultType] = self._kernel.create_task(coro, name, **kwargs)
            child.group = self
            child._waitq.push(self._parent, join=None, send=child)
            self._todo.add(child)
            return child

        # TODO(cjdrake): Handle this scenario
        assert False  # pragma: no cover
