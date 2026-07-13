# CrashAudit

A reproducible framework for auditing the reliability of a national road
crash database, applied to the Accident Research Institute (ARI, BUET)
crash database for Bangladesh, 2006-2015.

## Structure

| File | Purpose |
|---|---|
| `room1_rule_engine.py` | Logical consistency checks against Form 403Q legal code sets |
| `room2_anomaly_detection.py` | Four-detector unsupervised anomaly ensemble |
| `room3_reliability_score.py` | Composite reliability scoring with weighting sensitivity |
| `room4_downstream_impact.py` | Raw-vs-cleaned comparison with placebo control |
| `shield1_synthetic_injection.py` | Synthetic error-injection validation benchmark |
| `shield2_adjudication_generator.py` | Blind human adjudication sample generator and scorer |
| `shield3_external_comparison.py` | Comparison against GBD, WHO, and official police statistics |

## Requirements

```
pip install -r requirements.txt
```

## Data availability

The underlying ARI crash database is held under restricted access and is
not distributed with this repository. Each script expects the source
workbook and intermediate CSV outputs at user-specified paths (see the
`PATH` constants at the top of each file). Users with authorised access
to the ARI database can reproduce all results in the associated
manuscript by running the scripts in numerical order.

## Citation

If you use this framework, please cite the associated manuscript
[citation to be added on publication].

## License

MIT License.
