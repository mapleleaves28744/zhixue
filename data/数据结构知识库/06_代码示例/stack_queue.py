from collections import deque

class Stack:
    def __init__(self):
        self._data = []

    def push(self, x):
        self._data.append(x)

    def pop(self):
        if not self._data:
            raise IndexError("pop from empty stack")
        return self._data.pop()

    def top(self):
        if not self._data:
            raise IndexError("top from empty stack")
        return self._data[-1]

    def is_empty(self):
        return len(self._data) == 0


class Queue:
    def __init__(self):
        self._data = deque()

    def enqueue(self, x):
        self._data.append(x)

    def dequeue(self):
        if not self._data:
            raise IndexError("dequeue from empty queue")
        return self._data.popleft()

    def is_empty(self):
        return len(self._data) == 0
