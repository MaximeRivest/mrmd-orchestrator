# Minimal Full Stack Demo (Monitor Mode)

This is mrmd with **monitor mode** enabled. Python executions are routed through
mrmd-monitor, so long-running code survives browser disconnects.

## JavaScript (local execution)

JavaScript runs directly in the browser:

```javascript
const items = ["apple", "banana", "cherry"];
const data = { count: items.length, first: items[0] };
console.log("Items:", items.join(", "));
data
```

```output:exec-1768147541401-635yd
Items: apple, banana, cherry
{
  "count": 3,
  "first": "apple"
}
```

After running, try typing `data.` to see **runtime completions**.

## Python (via monitor)

Python runs through mrmd-monitor (check the status bar above):

```python
import math
x = 42
print(f"The answer is {x}")
math.sqrt(x)
```

```output:exec-1768147544455-2byu4
The answer is 42
Out[1]: 6.48074069840786
```

## Python with input

```python
name = input("What is your name? ")
print(f"Hello, {name}!")
```

## Long-running Python

Try disconnecting the browser while this runs - the monitor keeps it going:

```python
import time
for i in range(10):
    print(f"Step {i+1}/10...")
    time.sleep(1)
print("Done!")
```

---

**Monitor Mode**: Executions go through mrmd-monitor instead of directly to the runtime.
This means long-running code survives browser disconnects.

Press **Shift+Enter** to run a code cell, or click the **play button**.
# Minimal Full Stack Demo (Monitor Mode)

This is mrmd with **monitor mode** enabled. Python executions are routed through
mrmd-monitor, so long-running code survives browser disconnects.

## JavaScript (local execution)

JavaScript runs directly in the browser:

```javascript
items = ['apple', 'banana', 'cherry'];
data = { count: items.length, first: items[0] };
console.log('Items:', items.join(', '));
data;
```

```output:exec-1768147196826-px9oe
Items: apple, banana, cherry
{
  "count": 3,
  "first": "apple"
}
```

After running, try typing `data.` to see **runtime completions**.

## Python (via monitor)

Python runs through mrmd-monitor (check the status bar above):

```python
import math
x = 423
print(f"The answer is {x}")
math.sqrt(x)
```

```output:exec-1768147461812-5x6wp
The answer is 423
Out[8]: 20.566963801203133
```

## Python with input

```python
name = input("What is your name? ")
print(f"Hello, {name}!")
```

```output:exec-1768146549451-thjkl
What is your name? max
Hello, max!
```



## Long-running Python

Try disconnecting the browser while this runs - the monitor keeps it going:

```python
import time
for i in range(10):
    print(f"Step {i+1}/10...")
    time.sleep(1)
print("Done!")
```

---

**Monitor Mode**: Executions go through mrmd-monitor instead of directly to the runtime.
This means long-running code survives browser disconnects.

Press **Shift+Enter** to run a code cell, or click the **play button**.
