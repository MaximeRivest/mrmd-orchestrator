# Exploring python plots for mrmd rendering

```python
%pip install matplotlib
```

```output:exec-1768326146382-zzn5y
Running: uv pip install matplotlib
--------------------------------------------------
[2mResolved [1m11 packages[0m [2min 164ms[0m
[2mInstalled [1m10 packages[0m [2min 63ms[0m
 [32m+[0m [1mcontourpy[0;2m==1.3.3[0m
 [32m+[0m [1mcycler[0;2m==0.12.1[0m
 [32m+[0m [1mfonttools[0;2m==4.61.1[0m
 [32m+[0m [1mkiwisolver[0;2m==1.4.9[0m
 [32m+[0m [1mmatplotlib[0;2m==3.10.8[0m
 [32m+[0m [1mnumpy[0;2m==2.4.1[0m
 [32m+[0m [1mpillow[0;2m==12.1.0[0m
 [32m+[0m [1mpyparsing[0;2m==3.3.1[0m
 [32m+[0m [1mpython-dateutil[0;2m==2.9.0.post0[0m
 [32m+[0m [1msix[0;2m==1.17.0[0m
--------------------------------------------------
Note: Restart kernel to use newly installed packages.
```


```python
import matplotlib.pyplot as plt
import numpy as np

# Simple line plot example
x = np.linspace(0, 10, 100)
y = np.sin(x)

plt.figure(figsize=(8, 4))
plt.plot(x, y, label='sin(x)')
plt.title('Basic Line Plot for MRMD Rendering')
plt.xlabel('x')
plt.ylabel('y')
plt.legend()
plt.show()
```

```output:exec-1768326154746-flp75
<ipython-input-3-1baff863ed9d>:14: UserWarning: FigureCanvasAgg is non-interactive, and thus cannot be shown
  plt.show()
```

```python
# here is the path to the sys executable
import sys
print(sys.executable)
```

```output:exec-1768329495564-ma2if
/home/maxime/Projects/notemrmd/.venv/bin/python
```

```python

```














This notebook explores how Python plots render in MRMD environments, testing various plot types and configurations.
