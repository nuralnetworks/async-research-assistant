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
| Sequential | 4.645 | 15 | 1.00x |
| Parallel (`fetch_all`) | 2.671 | 15 | 1.74x |

## Device and Runtime

| Metric | Value |
|---|---|
| Operating system | Windows-10-10.0.26200-SP0 |
| Machine | AMD64 |
| Processor | Intel64 Family 6 Model 154 Stepping 4, GenuineIntel |
| Logical CPU count | 12 |
| Python version | 3.11.9 |
| Python implementation | CPython |

## Interpretation

Each question performs three independent simulated I/O operations. Sequential execution waits for all three delays, whereas `fetch_all` overlaps them. A speedup close to 3x is therefore expected.
