# Architecture Cost Comparison

- Baseline SHA: `5a1bb34c9efa269ca6159217827f1742faa95d20`
- Candidate SHA: `71dd343e0f9876d972434101e90bdb5f88fd29e6`
- Baseline: Linux Python 3.12.3 aarch64
- Candidate: Linux Python 3.12.3 aarch64

## Results

| Metric | Baseline (ms) | Candidate (ms) | Delta | % Change | Status |
|--------|---------------|----------------|-------|----------|--------|
| cli_help | 827.69 | 887.75 | +60.06 | +7.3% | OK |
| import_eggcalc | 4471.99 | 4785.36 | +313.37 | +7.0% | OK |
| import_evaluate | 4414.25 | 4798.38 | +384.14 | +8.7% | OK |
| normal_expression | 4461.42 | 4842.12 | +380.70 | +8.5% | OK |
| unit_parse_normal | 4555.25 | 4755.61 | +200.36 | +4.4% | OK |
| unit_registry | 4544.37 | 4804.67 | +260.30 | +5.7% | OK |
| unitvalue_arithmetic | 4434.86 | 4828.81 | +393.95 | +8.9% | OK |

## No Regressions

All metrics within 15% threshold.
