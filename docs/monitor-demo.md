# Monitor Mode Demo

This notebook uses **monitor mode** for execution. The mrmd-monitor process
handles all code execution, so long-running code survives browser disconnects.

## Python (via monitor)

```python
print("Hello from Python!")
import time
for i in range(5):
    print(f"Count: {i}")
    time.sleep(1)
print("Done!")
```

## Python with input

```python
name = input("What is your name? ")
print(f"Hello, {name}!")
```

Press **Shift+Enter** to run a cell. Watch the monitor terminal to see it claim and execute.


```python
x
```

```output:exec-1768147552799-uzg2r
Out[2]: 42
```

```python

```
