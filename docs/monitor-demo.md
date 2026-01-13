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

```output:exec-1768150608188-zroe1
What is your name? max
Hello, max!
```



Press **Shift+Enter** to run a cell. Watch the monitor terminal to see it claim and execute.


```python
x = 6 +2
x
```

```output:exec-1768310058375-0anaq
Out[3]: 8
```

```python
x
```

```output:exec-1768310053017-kpvc0
Out[2]: 2
```

```python

```
