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
| Sequential | 4.661 | 15 | 1.00x |
| Parallel (`fetch_all`) | 3.202 | 15 | 1.46x |

## Device and Runtime

| Metric | Value |
|---|---|
| Operating system | Windows-11-10.0.26200-SP0 |
| Machine | AMD64 |
| Processor | AMD64 Family 25 Model 68 Stepping 1, AuthenticAMD |
| Logical CPU count | 12 |
| Python version | 3.12.10 |
| Python implementation | CPython |

## Interpretation

Each question performs three independent simulated I/O operations. Sequential execution waits for all three delays, whereas `fetch_all` overlaps them. A speedup close to 3x is therefore expected.
