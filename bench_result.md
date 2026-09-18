# Benchmark Result

## Method

- Questions: 5
- Sources per question: 3
- Simulated I/O delay per source: 300 ms
- Cache cleared before execution: yes
- Network access: none

## Results

| Mode | Duration (s) | Sources fetched | Relative speed |
|---|---:|---:|---:|
| Sequential | 4.523 | 15 | 1.00x |
| Parallel (`fetch_all`) | 2.643 | 15 | 1.71x |

## Device and Runtime

| Metric | Value |
|---|---|
| Operating system | Windows-10-10.0.19045-SP0 |
| Machine | AMD64 |
| Processor | Intel64 Family 6 Model 142 Stepping 10, GenuineIntel |
| Logical CPU count | 8 |
| Python version | 3.13.3 |
| Python implementation | CPython |

## Interpretation

Each question performs three independent simulated I/O operations. Sequential execution waits for all three delays, whereas `fetch_all` overlaps them. A speedup close to 3x is therefore expected.
